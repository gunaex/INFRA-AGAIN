"""Implementation Planning — domain models for Phase 6.

Deterministic, rule-based planning from accepted BASELINE_FROZEN designs.
No LLM required for core plan generation.
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


class WorkPackageType(str, Enum):
    INFRASTRUCTURE = "INFRASTRUCTURE"
    NETWORK = "NETWORK"
    SECURITY = "SECURITY"
    PLATFORM = "PLATFORM"
    APPLICATION = "APPLICATION"
    DATABASE = "DATABASE"
    DATA = "DATA"
    INTEGRATION = "INTEGRATION"
    OBSERVABILITY = "OBSERVABILITY"
    MIGRATION = "MIGRATION"
    TESTING = "TESTING"
    DEPLOYMENT = "DEPLOYMENT"
    DOCUMENTATION = "DOCUMENTATION"


class TaskStatus(str, Enum):
    PLANNED = "PLANNED"
    READY = "READY"
    BLOCKED = "BLOCKED"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AutomationEligibility(str, Enum):
    AUTO = "AUTO"
    ASK = "ASK"
    MANUAL = "MANUAL"
    BLOCKED = "BLOCKED"


class PlanStatus(str, Enum):
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"
    REVIEW_READY = "REVIEW_READY"
    CHANGE_REQUESTED = "CHANGE_REQUESTED"
    APPROVED_FOR_EXECUTION = "APPROVED_FOR_EXECUTION"
    BASELINE_INVALIDATED = "BASELINE_INVALIDATED"
    COMPLETED = "COMPLETED"


class ReadinessState(str, Enum):
    NOT_READY = "NOT_READY"
    PARTIALLY_READY = "PARTIALLY_READY"
    READY_FOR_LOCAL_IMPLEMENTATION = "READY_FOR_LOCAL_IMPLEMENTATION"
    READY_FOR_SANDBOX = "READY_FOR_SANDBOX"
    READY_FOR_CONTROLLED_REAL = "READY_FOR_CONTROLLED_REAL"
    READY_FOR_PRODUCTION = "READY_FOR_PRODUCTION"


class GateState(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    PASS = "PASS"
    BLOCKED = "BLOCKED"


class RiskSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EstimateSource(str, Enum):
    RULE_BASED = "RULE_BASED"
    USER_PROVIDED = "USER_PROVIDED"
    HISTORICAL = "HISTORICAL"
    UNKNOWN = "UNKNOWN"


class EffortUnit(str, Enum):
    HOURS = "HOURS"
    PERSON_DAYS = "PERSON_DAYS"
    CALENDAR_DAYS = "CALENDAR_DAYS"


class DeliveryStage(str, Enum):
    UR = "UR"
    DR = "DR"
    PU = "PU"
    IFT = "IFT"
    BUT = "BUT"
    UAT = "UAT"
    IP = "IP"


class EvidenceType(str, Enum):
    COMMAND_OUTPUT = "COMMAND_OUTPUT"
    API_RESPONSE = "API_RESPONSE"
    CONFIG_SNAPSHOT = "CONFIG_SNAPSHOT"
    SCREENSHOT = "SCREENSHOT"
    TEST_RESULT = "TEST_RESULT"
    LOG = "LOG"
    METRIC = "METRIC"
    APPROVAL = "APPROVAL"
    ARCHITECTURE_DIFF = "ARCHITECTURE_DIFF"


class RiskCategory(str, Enum):
    NETWORK = "NETWORK"
    SECURITY = "SECURITY"
    DATA = "DATA"
    INTEGRATION = "INTEGRATION"
    SCHEDULE = "SCHEDULE"
    COST = "COST"
    DEPENDENCY = "DEPENDENCY"
    MIGRATION = "MIGRATION"


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class ImplementationEstimate:
    effort_value: float = 0.0
    effort_unit: EffortUnit = EffortUnit.PERSON_DAYS
    source: EstimateSource = EstimateSource.RULE_BASED
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "effortValue": self.effort_value, "effortUnit": self.effort_unit.value,
            "source": self.source.value, "confidence": self.confidence,
        }


@dataclass
class ImplementationRisk:
    risk_id: str = ""
    title: str = ""
    description: str = ""
    severity: RiskSeverity = RiskSeverity.MEDIUM
    probability: float = 0.5
    impact: float = 0.5
    mitigation: str = ""
    category: RiskCategory = RiskCategory.INTEGRATION
    affected_tasks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "riskId": self.risk_id, "title": self.title,
            "description": self.description, "severity": self.severity.value,
            "probability": self.probability, "impact": self.impact,
            "mitigation": self.mitigation, "category": self.category.value,
            "affectedTasks": self.affected_tasks,
        }


@dataclass
class ImplementationBlocker:
    blocker_id: str = ""
    severity: RiskSeverity = RiskSeverity.HIGH
    description: str = ""
    affected_tasks: list[str] = field(default_factory=list)
    resolution_required: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "blockerId": self.blocker_id, "severity": self.severity.value,
            "description": self.description, "affectedTasks": self.affected_tasks,
            "resolutionRequired": self.resolution_required,
        }


@dataclass
class ImplementationGate:
    gate_id: str = ""
    name: str = ""
    state: GateState = GateState.PENDING
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "gateId": self.gate_id, "name": self.name,
            "state": self.state.value, "description": self.description,
        }


@dataclass
class ImplementationMilestone:
    milestone_id: str = ""
    name: str = ""
    description: str = ""
    depends_on: list[str] = field(default_factory=list)
    completed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "milestoneId": self.milestone_id, "name": self.name,
            "description": self.description, "dependsOn": self.depends_on,
            "completed": self.completed,
        }


@dataclass
class EvidenceRequirement:
    evidence_id: str = ""
    task_id: str = ""
    evidence_type: EvidenceType = EvidenceType.TEST_RESULT
    description: str = ""
    source: str = "RULE_BASED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidenceId": self.evidence_id, "taskId": self.task_id,
            "evidenceType": self.evidence_type.value,
            "description": self.description, "source": self.source,
        }


@dataclass
class ImplementationTask:
    task_id: str = ""
    work_package_id: str = ""
    title: str = ""
    description: str = ""
    category: WorkPackageType = WorkPackageType.INFRASTRUCTURE
    status: TaskStatus = TaskStatus.PLANNED
    priority: int = 5
    execution_mode: str = "PLAN_ONLY"
    dependencies: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    evidence_requirements: list[EvidenceRequirement] = field(default_factory=list)
    risk_level: RiskSeverity = RiskSeverity.LOW
    estimated_effort: ImplementationEstimate = field(default_factory=ImplementationEstimate)
    owner_role: str = ""
    automation: AutomationEligibility = AutomationEligibility.MANUAL
    derived_from: list[str] = field(default_factory=list)
    delivery_stage: DeliveryStage | None = None
    local_validatable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "taskId": self.task_id, "workPackageId": self.work_package_id,
            "title": self.title, "description": self.description,
            "category": self.category.value, "status": self.status.value,
            "priority": self.priority, "executionMode": self.execution_mode,
            "dependencies": self.dependencies, "inputs": self.inputs,
            "outputs": self.outputs, "acceptanceCriteria": self.acceptance_criteria,
            "evidenceRequirements": [e.to_dict() for e in self.evidence_requirements],
            "riskLevel": self.risk_level.value,
            "estimatedEffort": self.estimated_effort.to_dict(),
            "ownerRole": self.owner_role, "automation": self.automation.value,
            "derivedFrom": self.derived_from,
            "deliveryStage": self.delivery_stage.value if self.delivery_stage else None,
            "localValidatable": self.local_validatable,
        }


@dataclass
class ImplementationWorkPackage:
    package_id: str = ""
    plan_id: str = ""
    title: str = ""
    description: str = ""
    package_type: WorkPackageType = WorkPackageType.INFRASTRUCTURE
    tasks: list[ImplementationTask] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    parallel_group: str = ""
    status: TaskStatus = TaskStatus.PLANNED
    estimated_effort: ImplementationEstimate = field(default_factory=ImplementationEstimate)

    def to_dict(self) -> dict[str, Any]:
        return {
            "packageId": self.package_id, "planId": self.plan_id,
            "title": self.title, "description": self.description,
            "packageType": self.package_type.value,
            "tasks": [t.to_dict() for t in self.tasks],
            "dependencies": self.dependencies,
            "parallelGroup": self.parallel_group,
            "status": self.status.value,
            "estimatedEffort": self.estimated_effort.to_dict(),
        }


@dataclass
class ImplementationDependency:
    """Explicit edge between work packages."""
    dep_id: str = ""
    from_package: str = ""
    to_package: str = ""
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "depId": self.dep_id, "fromPackage": self.from_package,
            "toPackage": self.to_package, "description": self.description,
        }


@dataclass
class ImplementationPlan:
    plan_id: str = field(default_factory=lambda: f"IMPL-{uuid4().hex[:6].upper()}")
    design_id: str = ""
    design_revision: int = 1
    status: PlanStatus = PlanStatus.DRAFT
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = ""

    summary: str = ""
    work_packages: list[ImplementationWorkPackage] = field(default_factory=list)
    dependencies: list[ImplementationDependency] = field(default_factory=list)
    milestones: list[ImplementationMilestone] = field(default_factory=list)
    risks: list[ImplementationRisk] = field(default_factory=list)
    blockers: list[ImplementationBlocker] = field(default_factory=list)
    gates: list[ImplementationGate] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)

    baseline_checksums: dict[str, str] = field(default_factory=dict)
    plan_checksum: str = ""

    critical_path: list[str] = field(default_factory=list)
    critical_path_duration: str = ""
    readiness: ReadinessState = ReadinessState.NOT_READY

    approved_by: str = ""
    approved_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "planId": self.plan_id, "designId": self.design_id,
            "designRevision": self.design_revision,
            "status": self.status.value,
            "createdAt": self.created_at, "updatedAt": self.updated_at,
            "summary": self.summary,
            "workPackages": [w.to_dict() for w in self.work_packages],
            "dependencies": [d.to_dict() for d in self.dependencies],
            "milestones": [m.to_dict() for m in self.milestones],
            "risks": [r.to_dict() for r in self.risks],
            "blockers": [b.to_dict() for b in self.blockers],
            "gates": [g.to_dict() for g in self.gates],
            "openQuestions": self.open_questions,
            "baselineChecksums": self.baseline_checksums,
            "planChecksum": self.plan_checksum,
            "criticalPath": self.critical_path,
            "criticalPathDuration": self.critical_path_duration,
            "readiness": self.readiness.value,
            "approvedBy": self.approved_by, "approvedAt": self.approved_at,
        }

    def compute_checksum(self) -> str:
        import hashlib, json
        data = {
            "designId": self.design_id, "designRevision": self.design_revision,
            "workPackages": sorted(
                [{"id": w.package_id, "tasks": len(w.tasks)} for w in self.work_packages],
                key=lambda x: x["id"]),
            "dependencies": sorted(
                [{"from": d.from_package, "to": d.to_package} for d in self.dependencies],
                key=lambda x: f"{x['from']}->{x['to']}"),
            "milestones": sorted([m.name for m in self.milestones]),
        }
        self.plan_checksum = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]
        return self.plan_checksum

    def approve(self, approved_by: str = "") -> None:
        self.status = PlanStatus.APPROVED_FOR_EXECUTION
        self.approved_by = approved_by
        self.approved_at = datetime.now(timezone.utc).isoformat()
        self.compute_checksum()

    def check_changed_after_approval(self) -> bool:
        if self.status != PlanStatus.APPROVED_FOR_EXECUTION:
            return False
        old_cs = self.plan_checksum
        new_cs = self.compute_checksum()
        return old_cs != new_cs
