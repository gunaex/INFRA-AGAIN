"""
Execution Orchestrator for INFRA-AGAIN.

Manages the full infrastructure pipeline:
    InfrastructureRequest → Plan → Approval → Execute → Observe → Validate → Result

Implements the safety ladder:
    LEVEL 0: PLAN_ONLY
    LEVEL 1: SIMULATED / LOCAL_RUNTIME
    LEVEL 2: SANDBOX
    LEVEL 3: CONTROLLED_REAL
    LEVEL 4: PRODUCTION

Destructive operations are BLOCKED by default.
Production is never an implicit continuation from local testing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from ..contracts import (
    EvidenceItem,
    EvidenceType,
    InfrastructureRequest,
    InfrastructureResult,
    InfrastructureStatus,
)
from ..core.domain import (
    ChangeSet,
    Evidence,
    ExecutionMode,
    ExecutionState,
    ExecutionTarget,
    InfrastructurePlan,
    Platform,
    Provider,
    TruthStatus,
    ValidationResult,
)
from ..providers.interface import ProviderAdapter
from ..platforms.interface import PlatformAdapter


# ============================================================================
# Action Policy (AIRLOCK)
# ============================================================================


class ActionPolicy(str, Enum):
    """Safety policy for actions."""
    AUTO = "AUTO"    # Safe to execute automatically
    ASK = "ASK"      # Requires user approval
    BLOCK = "BLOCK"  # Blocked by default


@dataclass
class PolicyDecision:
    """Result of a policy evaluation."""
    action: str
    policy: ActionPolicy
    reason: str
    requires_approval: bool
    approval_id: str | None = None
    decided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PolicyEngine:
    """
    AIRLOCK policy engine.

    AUTO candidates:
    - read local repo
    - inspect provider metadata
    - build plan
    - validate schemas
    - run PLAN_ONLY
    - execute approved Local Lab operations

    ASK:
    - install dependencies
    - create external cloud resources
    - access cloud credentials
    - apply IaC against sandbox
    - delete managed infrastructure
    - modify shared environments

    BLOCK by default:
    - sudo without explicit approval path
    - unrestricted cloud admin
    - secret exfiltration
    - destructive operations outside managed scope
    - production mutation without explicit approval
    - hidden provider fallback
    """

    @staticmethod
    def evaluate(action: str, target: ExecutionTarget, context: dict[str, Any] | None = None) -> PolicyDecision:
        """Evaluate whether an action is allowed."""

        # BLOCK: Production mutation without explicit approval
        if target.mode == ExecutionMode.PRODUCTION:
            if action in ("apply", "destroy", "modify"):
                return PolicyDecision(
                    action=action,
                    policy=ActionPolicy.BLOCK,
                    reason="Production mutation requires explicit approval gate",
                    requires_approval=True,
                )

        # BLOCK: Destructive operations by default
        # AUTO: destroy in simulated/local is safe (no real infrastructure)
        if action == "destroy":
            if target.mode in (ExecutionMode.SIMULATED, ExecutionMode.LOCAL_RUNTIME):
                return PolicyDecision(
                    action=action,
                    policy=ActionPolicy.AUTO,
                    reason="Destroy in simulated/local is safe — no real infrastructure",
                    requires_approval=False,
                )
            return PolicyDecision(
                action=action,
                policy=ActionPolicy.BLOCK,
                reason="Destructive operations blocked by default outside simulated/local",
                requires_approval=True,
            )

        # BLOCK: Hidden provider fallback
        if context and context.get("fallback_provider"):
            return PolicyDecision(
                action=action,
                policy=ActionPolicy.BLOCK,
                reason="Hidden provider fallback is blocked",
                requires_approval=True,
            )

        # BLOCK: Unrestricted production access
        if action == "unrestricted_admin":
            return PolicyDecision(
                action=action,
                policy=ActionPolicy.BLOCK,
                reason="Unrestricted cloud admin is blocked",
                requires_approval=True,
            )

        # ASK: Apply to sandbox or controlled real
        if action == "apply":
            if target.mode in (ExecutionMode.SANDBOX, ExecutionMode.CONTROLLED_REAL):
                return PolicyDecision(
                    action=action,
                    policy=ActionPolicy.ASK,
                    reason=f"Apply to {target.mode.value} requires approval",
                    requires_approval=True,
                )

        # ASK: Create external resources
        if action == "create_external":
            return PolicyDecision(
                action=action,
                policy=ActionPolicy.ASK,
                reason="Creating external cloud resources requires approval",
                requires_approval=True,
            )

        # AUTO: Read, plan, inspect, PLAN_ONLY
        if action in ("read", "plan", "inspect", "plan_only", "validate_schema", "discover"):
            return PolicyDecision(
                action=action,
                policy=ActionPolicy.AUTO,
                reason=f"'{action}' is safe — AUTO approved",
                requires_approval=False,
            )

        # AUTO: Local lab operations (if approved upstream)
        if action == "local_lab_execute":
            if target.is_safe:
                return PolicyDecision(
                    action=action,
                    policy=ActionPolicy.AUTO,
                    reason="Local lab execution is AUTO within safe targets",
                    requires_approval=False,
                )

        # Default: ASK
        return PolicyDecision(
            action=action,
            policy=ActionPolicy.ASK,
            reason=f"Action '{action}' requires approval by default",
            requires_approval=True,
        )


# ============================================================================
# Execution Orchestrator
# ============================================================================


@dataclass
class OrchestrationContext:
    """Holds the full state of an infrastructure execution."""
    context_id: str = field(default_factory=lambda: f"ctx-{uuid4().hex[:8]}")
    request: InfrastructureRequest | None = None
    state: ExecutionState = ExecutionState.DRAFT
    plan: InfrastructurePlan | None = None
    target: ExecutionTarget | None = None
    change_set: ChangeSet | None = None
    evidence: Evidence = field(default_factory=Evidence)
    policy_decisions: list[PolicyDecision] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ExecutionOrchestrator:
    """
    Orchestrates the full infrastructure pipeline.

    Responsibilities:
    - Receive InfrastructureRequest
    - Normalize intent
    - Resolve capabilities
    - Choose execution target
    - Generate plan
    - Policy check
    - Execute (if approved)
    - Observe
    - Validate
    - Produce InfrastructureResult with evidence
    """

    def __init__(
        self,
        provider_adapter: ProviderAdapter | None = None,
        platform_adapter: PlatformAdapter | None = None,
    ):
        self.provider_adapter = provider_adapter
        self.platform_adapter = platform_adapter
        self.policy_engine = PolicyEngine()
        self._context: OrchestrationContext | None = None

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    async def process(
        self,
        request: InfrastructureRequest,
        target: ExecutionTarget | None = None,
    ) -> InfrastructureResult:
        """Full pipeline: Request → Plan → Execute → Observe → Validate → Result."""
        ctx = OrchestrationContext(request=request, target=target)
        ctx.started_at = datetime.now(timezone.utc)
        self._context = ctx

        try:
            # Step 1: Normalize intent
            ctx.state = ExecutionState.NORMALIZING
            normalized = self._normalize_intent(request)

            # Step 2: Resolve target
            if target is None:
                target = self._resolve_target(request)
                ctx.target = target

            # Step 3: Policy check — can we plan?
            decision = self.policy_engine.evaluate("plan", target)
            ctx.policy_decisions.append(decision)
            if decision.policy == ActionPolicy.BLOCK:
                return self._blocked_result(ctx, decision.reason)

            # Step 4: Generate plan
            ctx.state = ExecutionState.PLANNING
            if self.provider_adapter:
                # Convert to capability requirements
                capabilities = self._to_capability_requirements(normalized)
                ctx.plan = await self.provider_adapter.plan(capabilities, target)
            else:
                ctx.plan = self._generate_plan_only(request, target)
            ctx.plan.correlation_id = request.correlationId
            ctx.plan.request_id = request.infrastructureRequestId

            ctx.state = ExecutionState.PLAN_READY

            # Step 5: Validate plan
            if self.provider_adapter:
                plan_warnings = await self.provider_adapter.validate_plan(ctx.plan)
                if plan_warnings:
                    ctx.errors.extend(plan_warnings)

            # Step 6: PLAN_ONLY → skip execution
            if target.mode == ExecutionMode.PLAN_ONLY:
                ctx.state = ExecutionState.COMPLETED
                ctx.evidence.plan = ctx.plan
                ctx.evidence.limitations.append("PLAN_ONLY mode — no infrastructure mutation")
                return self._build_result(ctx, InfrastructureStatus.SUCCESS)

            # Step 7: Approval check for execution
            ctx.state = ExecutionState.WAITING_FOR_APPROVAL
            exec_decision = self.policy_engine.evaluate("apply", target)
            ctx.policy_decisions.append(exec_decision)
            if exec_decision.policy in (ActionPolicy.BLOCK, ActionPolicy.ASK):
                ctx.evidence.plan = ctx.plan
                ctx.evidence.policy_decision = exec_decision.reason
                return self._build_result(
                    ctx,
                    InfrastructureStatus.PARTIAL,
                    extra_evidence=[EvidenceItem(
                        type=EvidenceType.PLAN_APPROVAL,
                        source="infrastructure-again",
                        reference="policy-gate",
                        summary=f"Execution blocked/awaiting approval: {exec_decision.reason}",
                        timestamp=datetime.now(timezone.utc),
                    )],
                )

            # Step 8: Execute
            ctx.state = ExecutionState.EXECUTING
            if self.provider_adapter:
                ctx.change_set = await self.provider_adapter.apply(ctx.plan, target)
            ctx.evidence.plan = ctx.plan
            ctx.evidence.execution_logs.append(f"Applied to {target.mode.value}")

            # Step 9: Observe
            ctx.state = ExecutionState.OBSERVING
            if self.provider_adapter:
                observed = await self.provider_adapter.observe(target)
                ctx.evidence.observed_resources.append(observed)

            # Step 10: Validate
            ctx.state = ExecutionState.VALIDATING
            if self.provider_adapter and ctx.plan:
                desired = self._plan_to_desired_state(ctx.plan)
                observed = ctx.evidence.observed_resources[-1] if ctx.evidence.observed_resources else {}
                validations = await self.provider_adapter.validate(desired, observed)
                ctx.evidence.validation_results = validations

            ctx.state = ExecutionState.COMPLETED

        except Exception as e:
            ctx.state = ExecutionState.FAILED
            ctx.errors.append(str(e))

        ctx.completed_at = datetime.now(timezone.utc)
        return self._build_result(ctx, InfrastructureStatus.SUCCESS if not ctx.errors else InfrastructureStatus.PARTIAL)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _normalize_intent(self, request: InfrastructureRequest) -> dict[str, Any]:
        """Normalize InfrastructureRequest into provider-neutral intent."""
        req = request.requirements
        intent: dict[str, Any] = {}

        if req.database:
            intent["database"] = {
                "engine": req.database.engine,
                "version": req.database.version,
                "availability": req.database.availability.value if req.database.availability else None,
                "backup_required": req.database.backup.required if req.database.backup else False,
                "encryption_required": bool(req.database.encryption and (req.database.encryption.atRest or req.database.encryption.inTransit)),
                "storage": req.database.storage,
            }

        if req.applicationRuntime:
            intent["application_runtime"] = {
                "containerized": req.applicationRuntime.containerized,
                "replicas": req.applicationRuntime.replicas,
                "https": req.applicationRuntime.https,
                "port": req.applicationRuntime.port,
            }

        if req.networking:
            intent["networking"] = {
                "public": req.networking.public,
                "https_only": req.networking.httpsOnly,
                "domain": req.networking.domain,
            }

        intent["provider_hint"] = req.providerHint.value if req.providerHint else None

        return intent

    def _to_capability_requirements(self, normalized: dict[str, Any]) -> list[Any]:
        """Convert normalized intent to capability requirements."""
        from ..core.domain import CapabilityCategory, CapabilityRequirement
        capabilities: list[CapabilityRequirement] = []

        if "database" in normalized:
            capabilities.append(CapabilityRequirement(
                category=CapabilityCategory.DATABASE,
                name="database",
                properties=normalized["database"],
            ))

        if "application_runtime" in normalized:
            capabilities.append(CapabilityRequirement(
                category=CapabilityCategory.COMPUTE,
                name="application_runtime",
                properties=normalized["application_runtime"],
            ))

        if "networking" in normalized:
            capabilities.append(CapabilityRequirement(
                category=CapabilityCategory.NETWORKING,
                name="networking",
                properties=normalized["networking"],
            ))

        return capabilities

    def _resolve_target(self, request: InfrastructureRequest) -> ExecutionTarget:
        """Resolve execution target from request hints."""
        provider_hint = request.requirements.providerHint
        provider = Provider(provider_hint.value) if provider_hint else Provider.AWS
        return ExecutionTarget(
            mode=ExecutionMode.PLAN_ONLY,
            provider=provider,
            platform=Platform.NATIVE_VM,
            target_type=None,  # type: ignore[arg-type]
            fidelity_notes={
                "Execution": "PLAN_ONLY",
                "Real Provisioning": "NOT_TESTED",
            },
        )

    def _generate_plan_only(
        self,
        request: InfrastructureRequest,
        target: ExecutionTarget,
    ) -> InfrastructurePlan:
        """Generate a PLAN_ONLY infrastructure plan without a provider adapter."""
        plan = InfrastructurePlan(
            request_id=request.infrastructureRequestId,
            correlation_id=request.correlationId,
            provider=target.provider,
            platform=target.platform,
            execution_target=target,
        )
        return plan

    def _plan_to_desired_state(self, plan: InfrastructurePlan) -> dict[str, Any]:
        """Convert plan to desired state dict for validation."""
        desired: dict[str, Any] = {}
        for mapping in plan.capability_mappings:
            desired[mapping.resource_type] = mapping.resource_properties
        return desired

    def _blocked_result(self, ctx: OrchestrationContext, reason: str) -> InfrastructureResult:
        ctx.state = ExecutionState.BLOCKED
        ctx.completed_at = datetime.now(timezone.utc)
        return self._build_result(
            ctx,
            InfrastructureStatus.FAILED,
            extra_evidence=[EvidenceItem(
                type=EvidenceType.PLAN_APPROVAL,
                source="infrastructure-again",
                reference="airlock",
                summary=f"BLOCKED: {reason}",
                timestamp=datetime.now(timezone.utc),
            )],
        )

    def _build_result(
        self,
        ctx: OrchestrationContext,
        status: InfrastructureStatus,
        extra_evidence: list[EvidenceItem] | None = None,
    ) -> InfrastructureResult:
        """Build canonical InfrastructureResult from orchestration context."""
        target = ctx.target or ExecutionTarget(
            mode=ExecutionMode.PLAN_ONLY,
            provider=Provider.AWS,
            platform=Platform.NATIVE_VM,
            target_type=None,  # type: ignore[arg-type]
        )

        evidence_items = ctx.evidence.to_canonical_evidence_items()
        if extra_evidence:
            evidence_items.extend([{
                "type": e.type.value,
                "source": e.source,
                "reference": e.reference,
                "summary": e.summary,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            } for e in extra_evidence])

        result = InfrastructureResult(
            correlationId=ctx.request.correlationId if ctx.request else "",
            workPackageId=ctx.request.workPackageId if ctx.request else "",
            infrastructureRequestId=ctx.request.infrastructureRequestId if ctx.request else "",
            status=status,
            provider=target.provider.value,  # type: ignore[arg-type]
            platform=target.platform.value,  # type: ignore[arg-type]
            evidence=[EvidenceItem(
                type=EvidenceType.ARCHITECTURE_PLAN,
                source="infrastructure-again",
                reference=item.get("reference", ""),
                summary=item.get("summary", ""),
                timestamp=datetime.fromisoformat(item["timestamp"]) if item.get("timestamp") else None,
            ) for item in evidence_items if item.get("type")],
            completedAt=ctx.completed_at or datetime.now(timezone.utc),
        )

        return result
