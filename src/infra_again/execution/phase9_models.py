"""Phase 9 — Controlled Real Readiness Models.

Formal promotion model for:
  LOCAL → SANDBOX → CONTROLLED_REAL → PRODUCTION

Phase 9 does NOT enable CONTROLLED_REAL or PRODUCTION execution.
It builds the governance architecture required before those can be permitted.

Current policy at Phase 9 completion:
  SANDBOX = ASK
  CONTROLLED_REAL = BLOCK
  PRODUCTION = BLOCK
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


# ============================================================================
# Enums
# ============================================================================


class EnvironmentClassification(str, Enum):
    LOCAL = "LOCAL"
    SANDBOX = "SANDBOX"
    CONTROLLED_REAL = "CONTROLLED_REAL"
    PRODUCTION = "PRODUCTION"


class BlastRadius(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class PromotionGateState(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"


class UATState(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    REQUIRED = "REQUIRED"
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_EXECUTED = "NOT_EXECUTED"


class ChangeWindowType(str, Enum):
    MAINTENANCE = "MAINTENANCE"
    EMERGENCY = "EMERGENCY"
    DEPLOYMENT = "DEPLOYMENT"


class SeparationRole(str, Enum):
    PLANNER = "PLANNER"
    EXECUTOR = "EXECUTOR"
    OBSERVER = "OBSERVER"
    VALIDATOR = "VALIDATOR"
    VERIFIER = "VERIFIER"
    APPROVER = "APPROVER"


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class EnvironmentTarget:
    """Explicit environment identity for promotion model."""
    environment_id: str = field(default_factory=lambda: f"ENV-{uuid4().hex[:8].upper()}")
    name: str = ""
    classification: EnvironmentClassification = EnvironmentClassification.SANDBOX
    provider: str = "aws"
    account_id: str = ""
    region: str = ""
    allowed_services: list[str] = field(default_factory=list)
    resource_scope: str = ""
    blast_radius: BlastRadius = BlastRadius.UNKNOWN
    cost_ceiling: float = 0.0
    maintenance_window: str = ""
    credential_policy: str = "TEMPORARY_LEAST_PRIVILEGE"
    approval_policy: str = "EXPLICIT_IMMUTABLE"
    retention_policy: str = "EPHEMERAL_TTL"
    production: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "environmentId": self.environment_id,
            "name": self.name,
            "classification": self.classification.value,
            "provider": self.provider,
            "accountId": self.account_id,
            "region": self.region,
            "allowedServices": self.allowed_services,
            "resourceScope": self.resource_scope,
            "blastRadius": self.blast_radius.value,
            "costCeiling": self.cost_ceiling,
            "maintenanceWindow": self.maintenance_window,
            "credentialPolicy": self.credential_policy,
            "approvalPolicy": self.approval_policy,
            "retentionPolicy": self.retention_policy,
            "production": self.production,
        }


@dataclass
class PromotionGate:
    """Individual gate for promotion readiness."""
    gate_id: str = ""
    name: str = ""
    state: PromotionGateState = PromotionGateState.PENDING
    description: str = ""
    required_by: list[EnvironmentClassification] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gateId": self.gate_id,
            "name": self.name,
            "state": self.state.value,
            "description": self.description,
            "requiredBy": [r.value for r in self.required_by],
        }


@dataclass
class MaintenanceWindow:
    """Change window for controlled execution."""
    window_id: str = field(default_factory=lambda: f"WIN-{uuid4().hex[:8].upper()}")
    window_type: ChangeWindowType = ChangeWindowType.MAINTENANCE
    start_time: str = ""
    end_time: str = ""
    timezone: str = "UTC"
    approved_by: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "windowId": self.window_id,
            "windowType": self.window_type.value,
            "startTime": self.start_time,
            "endTime": self.end_time,
            "timezone": self.timezone,
            "approvedBy": self.approved_by,
        }

    def is_active(self) -> bool:
        """Check if current time falls within the window."""
        if not self.start_time or not self.end_time:
            return False
        try:
            now = datetime.now(timezone.utc)
            start = datetime.fromisoformat(self.start_time.replace("Z", "+00:00"))
            end = datetime.fromisoformat(self.end_time.replace("Z", "+00:00"))
            return start <= now <= end
        except (ValueError, TypeError):
            return False


@dataclass
class RollbackPlan:
    """Required rollback plan for controlled execution."""
    plan_id: str = field(default_factory=lambda: f"RBP-{uuid4().hex[:8].upper()}")
    description: str = ""
    steps: list[str] = field(default_factory=list)
    failure_owner: str = ""
    estimated_recovery_time: str = ""
    validation_after_rollback: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "planId": self.plan_id,
            "description": self.description,
            "steps": self.steps,
            "failureOwner": self.failure_owner,
            "estimatedRecoveryTime": self.estimated_recovery_time,
            "validationAfterRollback": self.validation_after_rollback,
        }

    @property
    def is_defined(self) -> bool:
        return bool(self.description and self.steps and self.failure_owner)


@dataclass
class PromotionPackage:
    """Binds sandbox verification to target environment promotion."""
    package_id: str = field(default_factory=lambda: f"PROMO-{uuid4().hex[:8].upper()}")
    source_execution_id: str = ""
    source_design_checksum: str = ""
    source_plan_checksum: str = ""
    source_implementation_checksum: str = ""
    evidence_checksum: str = ""
    target_environment: EnvironmentTarget = field(default_factory=EnvironmentTarget)
    change_set: dict[str, Any] = field(default_factory=dict)
    gates: list[PromotionGate] = field(default_factory=list)
    uat_state: UATState = UATState.NOT_EXECUTED
    rollback_plan: RollbackPlan = field(default_factory=RollbackPlan)
    maintenance_window: MaintenanceWindow = field(default_factory=MaintenanceWindow)
    approvers: list[str] = field(default_factory=list)
    executor: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "packageId": self.package_id,
            "sourceExecutionId": self.source_execution_id,
            "sourceDesignChecksum": self.source_design_checksum,
            "sourcePlanChecksum": self.source_plan_checksum,
            "sourceImplementationChecksum": self.source_implementation_checksum,
            "evidenceChecksum": self.evidence_checksum,
            "targetEnvironment": self.target_environment.to_dict(),
            "changeSet": self.change_set,
            "gates": [g.to_dict() for g in self.gates],
            "uatState": self.uat_state.value,
            "rollbackPlan": self.rollback_plan.to_dict(),
            "maintenanceWindow": self.maintenance_window.to_dict(),
            "approvers": self.approvers,
            "executor": self.executor,
            "createdAt": self.created_at,
        }

    def check_readiness(self) -> tuple[bool, list[str]]:
        """Check all promotion gates. Returns (ready, blockers)."""
        blockers: list[str] = []

        if self.target_environment.classification == EnvironmentClassification.PRODUCTION:
            blockers.append("PRODUCTION_BLOCKED — not yet enabled in Phase 9")

        if self.target_environment.classification == EnvironmentClassification.CONTROLLED_REAL:
            blockers.append("CONTROLLED_REAL_BLOCKED — not yet enabled in Phase 9")

        if self.target_environment.blast_radius == BlastRadius.UNKNOWN:
            blockers.append("BLAST_RADIUS_UNKNOWN — must be declared")

        if not self.rollback_plan.is_defined:
            blockers.append("ROLLBACK_PLAN_MISSING — required for promotion")

        if not self.maintenance_window.start_time:
            blockers.append("MAINTENANCE_WINDOW_MISSING — required for promotion")

        if not self.approvers:
            blockers.append("NO_APPROVERS — separation of duties required")

        if self.executor and self.executor in self.approvers:
            blockers.append("EXECUTOR_CANNOT_SELF_APPROVE — separation of duties")

        if self.target_environment.classification in (
            EnvironmentClassification.CONTROLLED_REAL,
            EnvironmentClassification.PRODUCTION,
        ):
            if self.uat_state != UATState.PASSED:
                blockers.append(f"UAT_NOT_PASSED — {self.uat_state.value}")

        for gate in self.gates:
            if gate.state == PromotionGateState.FAIL:
                blockers.append(f"GATE_FAILED: {gate.name}")
            elif gate.state == PromotionGateState.BLOCKED:
                blockers.append(f"GATE_BLOCKED: {gate.name}")

        return len(blockers) == 0, blockers


# ============================================================================
# Phase 9 Policy Constants
# ============================================================================

PHASE9_POLICY = {
    "SANDBOX": "ASK",
    "CONTROLLED_REAL": "BLOCK",
    "PRODUCTION": "BLOCK",
    "note": (
        "Phase 9 builds governance/control architecture for CONTROLLED_REAL "
        "and PRODUCTION but does NOT enable execution. These remain BLOCKED "
        "until explicit future phases."
    ),
}

REQUIRED_PROMOTION_GATES = [
    {"id": "SANDBOX_VERIFIED", "name": "Sandbox Execution Verified"},
    {"id": "DESIGN_VALID", "name": "Design Still Valid"},
    {"id": "PLAN_VALID", "name": "Implementation Plan Still Valid"},
    {"id": "QA_EVIDENCE", "name": "QA Evidence Available"},
    {"id": "UAT_REQUIREMENTS", "name": "UAT Requirements Defined"},
    {"id": "TARGET_IDENTITY", "name": "Target Environment Identity Known"},
    {"id": "COST_ACCEPTED", "name": "Cost Estimate Accepted"},
    {"id": "ROLLBACK_DEFINED", "name": "Rollback Plan Defined"},
    {"id": "MAINTENANCE_WINDOW", "name": "Maintenance Window Defined"},
    {"id": "APPROVERS_DEFINED", "name": "Approvers Identified"},
    {"id": "SEPARATION_OF_DUTIES", "name": "Separation of Duties Verified"},
    {"id": "BLAST_RADIUS", "name": "Blast Radius Declared"},
]


def create_sandbox_environment(account_id: str = "", region: str = "") -> EnvironmentTarget:
    """Create a SANDBOX environment target."""
    return EnvironmentTarget(
        name="INFRA-AGAIN Sandbox",
        classification=EnvironmentClassification.SANDBOX,
        provider="aws",
        account_id=account_id,
        region=region,
        allowed_services=["s3"],
        resource_scope="S3 bucket (empty, ephemeral)",
        blast_radius=BlastRadius.LOW,
        cost_ceiling=0.10,
        production=False,
    )


def create_controlled_real_target(account_id: str = "", region: str = "") -> EnvironmentTarget:
    """Create a CONTROLLED_REAL environment target (NOT executable in Phase 9)."""
    return EnvironmentTarget(
        name="INFRA-AGAIN Controlled Real",
        classification=EnvironmentClassification.CONTROLLED_REAL,
        provider="aws",
        account_id=account_id,
        region=region,
        allowed_services=[],
        resource_scope="NOT YET DEFINED",
        blast_radius=BlastRadius.UNKNOWN,
        cost_ceiling=0.0,
        production=False,
    )
