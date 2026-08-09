"""
Execution Orchestrator for INFRA-AGAIN — Phase 2A.1 HARDENED.

Full pipeline with SQLite persistence, ownership tracking,
explicit state machine, evidence persistence, and restart/resume.

Fixes from 2A.1:
- Idempotency: EXECUTING/OBSERVING/VALIDATING do NOT return SUCCESS
- Persisted final InfrastructureResult for exact idempotent retrieval
- Destroy bypass removed: only explicit ownership allows AUTO destroy
- Missing/unknown ownership → ASK (never AUTO)
- Restart from EXECUTING → REQUIRES_RECONCILIATION
- Validation failure → FAILED run state (not partial success)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
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
    ChangeAction,
    ChangeSet,
    Evidence,
    ExecutionMode,
    ExecutionState,
    ExecutionTarget,
    ExecutionTargetType,
    InfrastructurePlan,
    OwnedResource,
    Platform,
    Provider,
    ResourceOwnership,
    TargetScope,
    ValidationResult,
    can_transition,
    VALID_TRANSITIONS,
)
from ..core.persistence import RunStore
from ..providers.interface import ProviderAdapter
from ..platforms.interface import PlatformAdapter


class ActionPolicy(str, Enum):
    AUTO = "AUTO"
    ASK = "ASK"
    BLOCK = "BLOCK"


class IdempotencyStatus:
    """Truthful idempotent response status — never fakes SUCCESS."""

    ACTIVE_STATES = {
        ExecutionState.EXECUTING.value,
        ExecutionState.OBSERVING.value,
        ExecutionState.VALIDATING.value,
        ExecutionState.REQUIRES_RECONCILIATION.value,
    }
    TERMINAL_GOOD = {ExecutionState.COMPLETED.value}
    TERMINAL_BAD = {
        ExecutionState.FAILED.value,
        ExecutionState.BLOCKED.value,
        ExecutionState.CANCELLED.value,
    }

    @staticmethod
    def classify(state: str) -> str:
        if state in IdempotencyStatus.TERMINAL_GOOD:
            return "COMPLETED"
        if state in IdempotencyStatus.TERMINAL_BAD:
            return "TERMINAL_NON_SUCCESS"
        if state in IdempotencyStatus.ACTIVE_STATES:
            return "IN_PROGRESS"
        return "OTHER"


@dataclass
class PolicyDecision:
    action: str
    policy: ActionPolicy
    reason: str
    requires_approval: bool
    approval_id: str | None = None
    decided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PolicyEngine:
    """AIRLOCK policy engine — ownership-aware, no shortcuts."""

    @staticmethod
    def evaluate(
        action: str,
        target: ExecutionTarget,
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        ctx = context or {}

        if target.mode == ExecutionMode.PRODUCTION:
            if action in ("apply", "destroy", "modify"):
                return PolicyDecision(
                    action=action, policy=ActionPolicy.BLOCK,
                    reason="Production mutation requires explicit approval gate",
                    requires_approval=True)

        if ctx.get("fallback_provider"):
            return PolicyDecision(action=action, policy=ActionPolicy.BLOCK,
                                  reason="Hidden provider fallback is blocked", requires_approval=True)

        if action == "unrestricted_admin":
            return PolicyDecision(action=action, policy=ActionPolicy.BLOCK,
                                  reason="Unrestricted cloud admin is blocked", requires_approval=True)

        if action == "destroy":
            return PolicyEngine._evaluate_destroy(target, ctx)

        if action == "apply":
            if target.mode in (ExecutionMode.SANDBOX, ExecutionMode.CONTROLLED_REAL):
                return PolicyDecision(action=action, policy=ActionPolicy.ASK,
                                      reason=f"Apply to {target.mode.value} requires approval",
                                      requires_approval=True)

        if action in ("read", "plan", "inspect", "plan_only", "validate_schema", "discover"):
            return PolicyDecision(action=action, policy=ActionPolicy.AUTO,
                                  reason=f"'{action}' is safe — AUTO", requires_approval=False)

        if action == "apply" and target.mode == ExecutionMode.SIMULATED and target.is_safe:
            return PolicyDecision(action=action, policy=ActionPolicy.AUTO,
                                  reason="SIMULATED apply on safe target — AUTO",
                                  requires_approval=False)

        if action == "local_lab_execute" and target.is_safe:
            return PolicyDecision(action=action, policy=ActionPolicy.AUTO,
                                  reason="Local lab execution AUTO within safe targets",
                                  requires_approval=False)

        return PolicyDecision(action=action, policy=ActionPolicy.ASK,
                              reason=f"Action '{action}' requires approval by default",
                              requires_approval=True)

    @staticmethod
    def _evaluate_destroy(target: ExecutionTarget, ctx: dict[str, Any]) -> PolicyDecision:
        """Ownership-only destroy evaluation — no bypass shortcuts."""
        resource_id = ctx.get("resource_id", "unknown")
        ownership = ctx.get("ownership")
        current_run_id = ctx.get("current_run_id", "")

        # Production: always BLOCK
        if target.mode == ExecutionMode.PRODUCTION:
            return PolicyDecision(action="destroy", policy=ActionPolicy.BLOCK,
                                  reason="Production destroy requires explicit approval",
                                  requires_approval=True)

        # Ownership present: strict rule
        if ownership is not None:
            if ownership.is_auto_destroy_allowed(current_run_id):
                return PolicyDecision(action="destroy", policy=ActionPolicy.AUTO,
                                      reason=f"AUTO destroy: owned ephemeral ISOLATED {resource_id}",
                                      requires_approval=False)
            reasons = []
            if ownership.managed_by != "INFRA_AGAIN":
                reasons.append(f"managed_by={ownership.managed_by}")
            if ownership.created_by_run_id != current_run_id:
                reasons.append("not owned by current run")
            if not ownership.ephemeral:
                reasons.append("not ephemeral")
            if ownership.target_scope != TargetScope.ISOLATED:
                reasons.append(f"scope={ownership.target_scope.value}")
            return PolicyDecision(action="destroy", policy=ActionPolicy.ASK,
                                  reason=f"Destroy requires approval: {'; '.join(reasons)}",
                                  requires_approval=True)

        # No ownership → ASK (never AUTO, regardless of target mode)
        return PolicyDecision(action="destroy", policy=ActionPolicy.ASK,
                              reason="Destroy requires ownership verification — ownership unknown",
                              requires_approval=True)


EVIDENCE_DIR = ".ai/infra-runs"


@dataclass
class OrchestrationContext:
    run_id: str = field(default_factory=lambda: f"run-{uuid4().hex[:8]}")
    request: InfrastructureRequest | None = None
    state: ExecutionState = ExecutionState.DRAFT
    plan: InfrastructurePlan | None = None
    target: ExecutionTarget | None = None
    change_set: ChangeSet | None = None
    evidence: Evidence = field(default_factory=Evidence)
    policy_decisions: list[PolicyDecision] = field(default_factory=list)
    owned_resources: list[OwnedResource] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ExecutionOrchestrator:
    """Orchestrator with SQLite persistence, ownership, state machine."""

    def __init__(
        self,
        provider_adapter: ProviderAdapter | None = None,
        platform_adapter: PlatformAdapter | None = None,
        store: RunStore | None = None,
    ):
        self.provider_adapter = provider_adapter
        self.platform_adapter = platform_adapter
        self.policy_engine = PolicyEngine()
        self.store = store or RunStore()
        self._ctx: OrchestrationContext | None = None

    # ------------------------------------------------------------------
    # Main Pipeline
    # ------------------------------------------------------------------

    async def process(
        self,
        request: InfrastructureRequest,
        target: ExecutionTarget | None = None,
        idempotency_key: str | None = None,
    ) -> InfrastructureResult:
        # Idempotency: check for existing run
        if idempotency_key:
            existing = self.store.get_run_by_idempotency(idempotency_key)
            if existing:
                return self._handle_idempotent(existing)

        ctx = OrchestrationContext(request=request, target=target)
        ctx.started_at = datetime.now(timezone.utc)
        self._ctx = ctx

        self.store.create_run(
            run_id=ctx.run_id, correlation_id=request.correlationId,
            work_package_id=request.workPackageId,
            infrastructure_request_id=request.infrastructureRequestId,
            idempotency_key=idempotency_key)

        try:
            await self._transition(ctx, ExecutionState.NORMALIZING)
            normalized = self._normalize_intent(request)
            self._persist_file(ctx, "normalized-intent.json", normalized)

            if target is None:
                target = self._resolve_target(request)
                ctx.target = target
            self._persist_target(ctx, target)

            decision = self.policy_engine.evaluate("plan", target)
            ctx.policy_decisions.append(decision)
            if decision.policy == ActionPolicy.BLOCK:
                await self._transition(ctx, ExecutionState.BLOCKED, decision.reason)
                return self._finalize(ctx, InfrastructureStatus.FAILED,
                    extra_evidence=[EvidenceItem(type=EvidenceType.PLAN_APPROVAL,
                        source="infrastructure-again", reference="airlock",
                        summary=f"BLOCKED: {decision.reason}",
                        timestamp=datetime.now(timezone.utc))])

            await self._transition(ctx, ExecutionState.PLANNING)
            if self.provider_adapter:
                capabilities = self._to_capability_requirements(normalized)
                ctx.plan = await self.provider_adapter.plan(capabilities, target)
            else:
                ctx.plan = self._generate_plan_only(request, target)
            ctx.plan.correlation_id = request.correlationId
            ctx.plan.request_id = request.infrastructureRequestId
            self._persist_plan(ctx)
            await self._transition(ctx, ExecutionState.PLAN_READY)

            if self.provider_adapter:
                warnings = await self.provider_adapter.validate_plan(ctx.plan)
                if warnings:
                    ctx.errors.extend(warnings)

            if target.mode == ExecutionMode.PLAN_ONLY:
                await self._transition(ctx, ExecutionState.COMPLETED, "PLAN_ONLY — no mutation")
                ctx.evidence.plan = ctx.plan
                ctx.evidence.limitations.append("PLAN_ONLY mode — no infrastructure mutation")
                return self._finalize(ctx, InfrastructureStatus.SUCCESS)

            await self._transition(ctx, ExecutionState.WAITING_FOR_APPROVAL)
            exec_decision = self.policy_engine.evaluate("apply", target)
            ctx.policy_decisions.append(exec_decision)
            self._persist_file(ctx, "policy.json", {
                "action": "apply", "policy": exec_decision.policy.value,
                "reason": exec_decision.reason})

            if exec_decision.policy in (ActionPolicy.BLOCK, ActionPolicy.ASK):
                await self._transition(ctx, ExecutionState.BLOCKED, exec_decision.reason)
                return self._finalize(ctx, InfrastructureStatus.PARTIAL,
                    extra_evidence=[EvidenceItem(type=EvidenceType.PLAN_APPROVAL,
                        source="infrastructure-again", reference="policy-gate",
                        summary=f"Requires approval: {exec_decision.reason}",
                        timestamp=datetime.now(timezone.utc))])

            await self._transition(ctx, ExecutionState.EXECUTING)
            if self.provider_adapter:
                ctx.change_set = await self.provider_adapter.apply(ctx.plan, target)
                for change in (ctx.change_set.changes if ctx.change_set else []):
                    if change.action == ChangeAction.CREATE:
                        resource = OwnedResource(
                            resource_id=change.resource_id, resource_type=change.resource_type,
                            provider=target.provider.value,
                            ownership=ResourceOwnership(
                                managed_by="INFRA_AGAIN", created_by_run_id=ctx.run_id,
                                ephemeral=True, target_scope=TargetScope.ISOLATED))
                        ctx.owned_resources.append(resource)
                        self.store.register_resource(resource)
            self._persist_file(ctx, "execution.json", {
                "target": target.mode.value,
                "change_summary": ctx.change_set.summary if ctx.change_set else "N/A"})

            await self._transition(ctx, ExecutionState.OBSERVING)
            if self.provider_adapter:
                observed = await self.provider_adapter.observe(target)
                ctx.evidence.observed_resources.append(observed)
                self._persist_file(ctx, "observed-state.json", observed)
                for resource in ctx.owned_resources:
                    r_obs = observed.get(resource.resource_id)
                    if r_obs:
                        self.store.update_resource_observed(resource.resource_id, {resource.resource_id: r_obs})
                        self.store.update_resource_state(resource.resource_id, r_obs)

            await self._transition(ctx, ExecutionState.VALIDATING)
            validation_failed = False
            if self.provider_adapter and ctx.plan:
                desired = self._plan_to_desired_state(ctx.plan)
                obs = ctx.evidence.observed_resources[-1] if ctx.evidence.observed_resources else {}
                validations = await self.provider_adapter.validate(desired, obs)
                ctx.evidence.validation_results = validations
                self._persist_file(ctx, "validation.json", {
                    "results": [{"resource_id": v.resource_id, "matches": v.matches,
                                 "drift_detected": v.drift_detected} for v in validations]})
                all_match = all(v.matches for v in validations if v.matches is not None)
                if not all_match:
                    validation_failed = True
                    ctx.errors.append("VALIDATION FAIL: desired != observed")

            # Validation failure → FAILED state, not SUCCESS
            if validation_failed or ctx.errors:
                await self._transition(ctx, ExecutionState.FAILED,
                    "; ".join(ctx.errors) if ctx.errors else "Validation failed")
                return self._finalize(ctx, InfrastructureStatus.FAILED)

            await self._transition(ctx, ExecutionState.COMPLETED)
            status = InfrastructureStatus.SUCCESS

        except Exception as e:
            try:
                await self._transition(ctx, ExecutionState.FAILED, str(e))
            except RuntimeError:
                pass
            ctx.errors.append(str(e))
            status = InfrastructureStatus.FAILED

        return self._finalize(ctx, status)

    # ------------------------------------------------------------------
    # Idempotency handling
    # ------------------------------------------------------------------

    def _handle_idempotent(self, existing: dict[str, Any]) -> InfrastructureResult:
        """Handle duplicate idempotency key truthfully."""
        state = existing["state"]
        run_id = existing["run_id"]
        classification = IdempotencyStatus.classify(state)

        if classification == "COMPLETED":
            # Return the EXACT persisted result
            persisted = self.store.get_final_result(run_id)
            if persisted:
                try:
                    return InfrastructureResult.model_validate_json(persisted)
                except Exception:
                    pass
            # Fallback: reconstruct from context
            ctx = self._load_context(run_id)
            if ctx:
                self._ctx = ctx
                return self._build_result(ctx, InfrastructureStatus.SUCCESS)

        if classification == "TERMINAL_NON_SUCCESS":
            persisted = self.store.get_final_result(run_id)
            if persisted:
                try:
                    return InfrastructureResult.model_validate_json(persisted)
                except Exception:
                    pass
            ctx = self._load_context(run_id)
            if ctx:
                self._ctx = ctx
                return self._build_result(ctx, InfrastructureStatus.FAILED)

        # IN_PROGRESS (EXECUTING, OBSERVING, VALIDATING, REQUIRES_RECONCILIATION)
        # Do NOT return SUCCESS — return truthful status
        ctx = self._load_context(run_id)
        if ctx:
            self._ctx = ctx
            if state == ExecutionState.REQUIRES_RECONCILIATION.value:
                return self._build_result(ctx, InfrastructureStatus.FAILED, extra_evidence=[
                    EvidenceItem(type=EvidenceType.PLAN_APPROVAL, source="infrastructure-again",
                                 reference=f"run-{run_id}",
                                 summary=f"Run requires reconciliation — state={state}",
                                 timestamp=datetime.now(timezone.utc))])
            return self._build_result(ctx, InfrastructureStatus.PARTIAL, extra_evidence=[
                EvidenceItem(type=EvidenceType.PLAN_APPROVAL, source="infrastructure-again",
                             reference=f"run-{run_id}",
                             summary=f"Run in progress — state={state}",
                             timestamp=datetime.now(timezone.utc))])

        # OTHER / fallback
        return InfrastructureResult(
            correlationId=existing.get("correlation_id", ""),
            workPackageId=existing.get("work_package_id", ""),
            infrastructureRequestId=existing.get("infrastructure_request_id", ""),
            status=InfrastructureStatus.PARTIAL,
            provider=existing.get("provider", Provider.AWS.value),
            platform=existing.get("platform", Platform.NATIVE_VM.value),
            evidence=[EvidenceItem(type=EvidenceType.PLAN_APPROVAL,
                source="infrastructure-again", reference=f"run-{run_id}",
                summary=f"Idempotent — state={state}",
                timestamp=datetime.now(timezone.utc))],
            completedAt=datetime.now(timezone.utc))

    # ------------------------------------------------------------------
    # Restart / Resume
    # ------------------------------------------------------------------

    def load_run(self, run_id: str) -> OrchestrationContext | None:
        ctx = self._load_context(run_id)
        if ctx:
            # Safety: if restarting during EXECUTING, mark for reconciliation
            if ctx.state == ExecutionState.EXECUTING:
                self.store.transition_state(
                    run_id, ExecutionState.REQUIRES_RECONCILIATION,
                    "Restarted while EXECUTING — manual reconciliation required")
                ctx.state = ExecutionState.REQUIRES_RECONCILIATION
        return ctx

    def _load_context(self, run_id: str) -> OrchestrationContext | None:
        run = self.store.get_run(run_id)
        if run is None:
            return None
        ctx = OrchestrationContext(run_id=run_id)
        ctx.state = ExecutionState(run["state"])

        # Reconstruct target
        if run.get("execution_target_type"):
            ctx.target = ExecutionTarget(
                mode=ExecutionMode(run["execution_mode"]) if run.get("execution_mode") else ExecutionMode.PLAN_ONLY,
                provider=Provider(run["provider"]) if run.get("provider") else Provider.AWS,
                platform=Platform(run["platform"]) if run.get("platform") else Platform.NATIVE_VM,
                target_type=ExecutionTargetType(run["execution_target_type"]),
                endpoint=run.get("execution_target_endpoint"))

        # Reconstruct plan
        if run.get("plan"):
            try:
                plan_data = json.loads(run["plan"])
                ctx.plan = InfrastructurePlan(
                    plan_id=plan_data.get("plan_id", ""),
                    correlation_id=run.get("correlation_id", ""),
                    request_id=run.get("infrastructure_request_id", ""),
                    provider=Provider(run["provider"]) if run.get("provider") else None,
                    platform=Platform(run["platform"]) if run.get("platform") else None,
                    execution_target=ctx.target,
                    risk_assessment=plan_data.get("risk_assessment", ""))
            except Exception:
                pass

        # Reconstruct owned resources
        for r in self.store.get_resources_for_run(run_id):
            ctx.owned_resources.append(OwnedResource(
                resource_id=r["resource_id"], resource_type=r["resource_type"],
                provider=r["provider"],
                ownership=ResourceOwnership(
                    managed_by=r["managed_by"], created_by_run_id=r["created_by_run_id"],
                    ephemeral=bool(r["ephemeral"]),
                    target_scope=TargetScope(r["target_scope"]))))

        # Reconstruct policy decisions from evidence
        for ev in self.store.get_evidence(run_id):
            if ev.get("summary") and "policy" in ev.get("summary", "").lower():
                ctx.policy_decisions.append(PolicyDecision(
                    action="recorded", policy=ActionPolicy.ASK,
                    reason=ev.get("summary", ""), requires_approval=True))

        return ctx

    # ------------------------------------------------------------------
    # Destroy (ownership-aware)
    # ------------------------------------------------------------------

    async def destroy_resource(
        self, run_id: str, resource_id: str, target: ExecutionTarget,
    ) -> tuple[bool, str]:
        """Destroy a resource — ownership-gated."""
        ownership = ResourceOwnership()
        resource = self.store.get_resource(resource_id)
        if resource:
            ownership = ResourceOwnership(
                managed_by=resource["managed_by"], created_by_run_id=resource["created_by_run_id"],
                ephemeral=bool(resource["ephemeral"]),
                target_scope=TargetScope(resource["target_scope"]))

        decision = self.policy_engine.evaluate("destroy", target, context={
            "resource_id": resource_id, "ownership": ownership if resource else None,
            "current_run_id": run_id})

        if decision.policy == ActionPolicy.BLOCK:
            return False, f"BLOCKED: {decision.reason}"
        if decision.policy == ActionPolicy.ASK:
            return False, f"ASK: {decision.reason}"

        # AUTO only
        if self.provider_adapter:
            cs = await self.provider_adapter.destroy(target, [resource_id])
            self.store.log_apply(run_id=run_id, resource_id=resource_id,
                                 operation="DESTROY", endpoint=target.endpoint or "unknown",
                                 response_data={"change_summary": cs.summary})
            return True, f"Destroyed {resource_id}: {cs.summary}"
        return False, "No provider adapter"

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    async def _transition(self, ctx: OrchestrationContext, to: ExecutionState, reason: str = ""):
        if not can_transition(ctx.state, to):
            raise RuntimeError(
                f"Illegal transition: {ctx.state.value} → {to.value}. "
                f"Valid: {[s.value for s in VALID_TRANSITIONS.get(ctx.state, set())]}")
        ctx.state = to
        self.store.transition_state(ctx.run_id, to, reason)

    # ------------------------------------------------------------------
    # Finalize
    # ------------------------------------------------------------------

    def _finalize(
        self, ctx: OrchestrationContext, status: InfrastructureStatus,
        extra_evidence: list[EvidenceItem] | None = None,
    ) -> InfrastructureResult:
        ctx.completed_at = datetime.now(timezone.utc)
        result = self._build_result(ctx, status, extra_evidence)

        # Persist the exact result for idempotent retrieval
        result_json = result.model_dump_json()
        self.store.persist_final_result(ctx.run_id, result_json)
        self._persist_file(ctx, "final-result.json", json.loads(result_json))

        return result

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist_target(self, ctx: OrchestrationContext, target: ExecutionTarget):
        self.store.update_run(ctx.run_id,
                              provider=target.provider.value, platform=target.platform.value,
                              execution_mode=target.mode.value,
                              execution_target_type=target.target_type.value if target.target_type else None,
                              execution_target_endpoint=target.endpoint)

    def _persist_plan(self, ctx: OrchestrationContext):
        if ctx.plan:
            data = {"plan_id": ctx.plan.plan_id,
                    "provider": ctx.plan.provider.value if ctx.plan.provider else None,
                    "platform": ctx.plan.platform.value if ctx.plan.platform else None,
                    "risk_assessment": ctx.plan.risk_assessment}
            self.store.update_run(ctx.run_id, plan=json.dumps(data))
            self._persist_file(ctx, "plan.json", data)

    def _persist_file(self, ctx: OrchestrationContext, filename: str, data: Any):
        evidence_path = Path(EVIDENCE_DIR) / ctx.run_id
        evidence_path.mkdir(parents=True, exist_ok=True)
        with open(evidence_path / filename, "w") as f:
            json.dump(data, f, default=str, indent=2)
        self.store.add_evidence(run_id=ctx.run_id, evidence_type="FILE",
                                source="infrastructure-again",
                                reference=str(evidence_path / filename),
                                summary=filename, data={"filename": filename})

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _normalize_intent(self, request: InfrastructureRequest) -> dict[str, Any]:
        req = request.requirements
        intent: dict[str, Any] = {}
        if req.database:
            intent["database"] = {
                "engine": req.database.engine, "version": req.database.version,
                "availability": req.database.availability.value if req.database.availability else None,
                "backup_required": req.database.backup.required if req.database.backup else False,
                "encryption_required": bool(req.database.encryption and (req.database.encryption.atRest or req.database.encryption.inTransit)),
                "storage": req.database.storage}
        if req.applicationRuntime:
            intent["application_runtime"] = {
                "containerized": req.applicationRuntime.containerized,
                "replicas": req.applicationRuntime.replicas,
                "https": req.applicationRuntime.https, "port": req.applicationRuntime.port}
        if req.networking:
            intent["networking"] = {"public": req.networking.public,
                                    "https_only": req.networking.httpsOnly,
                                    "domain": req.networking.domain}
        intent["provider_hint"] = req.providerHint.value if req.providerHint else None
        return intent

    def _to_capability_requirements(self, normalized: dict[str, Any]) -> list[Any]:
        from ..core.domain import CapabilityCategory, CapabilityRequirement
        caps: list[CapabilityRequirement] = []
        if "database" in normalized:
            caps.append(CapabilityRequirement(category=CapabilityCategory.DATABASE, name="database", properties=normalized["database"]))
        if "application_runtime" in normalized:
            caps.append(CapabilityRequirement(category=CapabilityCategory.COMPUTE, name="application_runtime", properties=normalized["application_runtime"]))
        if "networking" in normalized:
            caps.append(CapabilityRequirement(category=CapabilityCategory.NETWORKING, name="networking", properties=normalized["networking"]))
        return caps

    def _resolve_target(self, request: InfrastructureRequest) -> ExecutionTarget:
        hint = request.requirements.providerHint
        provider = Provider(hint.value) if hint else Provider.AWS
        return ExecutionTarget(mode=ExecutionMode.PLAN_ONLY, provider=provider,
                               platform=Platform.NATIVE_VM, target_type=None,
                               fidelity_notes={"Execution": "PLAN_ONLY", "Real Provisioning": "NOT_TESTED"})

    def _generate_plan_only(self, request: InfrastructureRequest, target: ExecutionTarget) -> InfrastructurePlan:
        return InfrastructurePlan(request_id=request.infrastructureRequestId,
                                  correlation_id=request.correlationId,
                                  provider=target.provider, platform=target.platform,
                                  execution_target=target)

    def _plan_to_desired_state(self, plan: InfrastructurePlan) -> dict[str, Any]:
        desired: dict[str, Any] = {}
        for m in plan.capability_mappings:
            desired[m.resource_type] = m.resource_properties
        return desired

    def _build_result(self, ctx: OrchestrationContext, status: InfrastructureStatus,
                      extra_evidence: list[EvidenceItem] | None = None) -> InfrastructureResult:
        target = ctx.target or ExecutionTarget(
            mode=ExecutionMode.PLAN_ONLY, provider=Provider.AWS,
            platform=Platform.NATIVE_VM, target_type=None)

        evidence_items = ctx.evidence.to_canonical_evidence_items()
        if extra_evidence:
            evidence_items.extend([{
                "type": e.type.value, "source": e.source, "reference": e.reference,
                "summary": e.summary,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None} for e in extra_evidence])

        return InfrastructureResult(
            correlationId=ctx.request.correlationId if ctx.request else "",
            workPackageId=ctx.request.workPackageId if ctx.request else "",
            infrastructureRequestId=ctx.request.infrastructureRequestId if ctx.request else "",
            status=status,
            provider=target.provider.value,
            platform=target.platform.value,
            evidence=[EvidenceItem(
                type=EvidenceType.ARCHITECTURE_PLAN, source="infrastructure-again",
                reference=item.get("reference", ""), summary=item.get("summary", ""),
                timestamp=datetime.fromisoformat(item["timestamp"]) if item.get("timestamp") else None)
                for item in evidence_items if item.get("type")],
            completedAt=ctx.completed_at or datetime.now(timezone.utc))
