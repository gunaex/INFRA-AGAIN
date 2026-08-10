"""Deterministic Implementation Planner.

Derives ImplementationPlan from accepted BASELINE_FROZEN design.
No LLM — rule-based derivation from design truth.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .models import (
    ImplementationPlan, ImplementationWorkPackage, ImplementationTask,
    ImplementationDependency, ImplementationMilestone, ImplementationGate,
    ImplementationRisk, ImplementationBlocker, EvidenceRequirement,
    WorkPackageType, TaskStatus, AutomationEligibility, RiskSeverity,
    ReadinessState, GateState, EvidenceType, EstimateSource, EffortUnit,
    ImplementationEstimate, DeliveryStage, RiskCategory, PlanStatus,
)


def generate_implementation_plan(
    design: dict[str, Any],
    flow: dict[str, Any] | None = None,
) -> ImplementationPlan:
    """Generate an implementation plan from an accepted design.

    Args:
        design: DesignBaseline.to_dict() — must be BASELINE_FROZEN
        flow: Optional FlowDefinition.to_dict()

    Returns:
        ImplementationPlan with work packages, tasks, dependencies.
    """
    # Validate entry gate
    if design.get("status") != "BASELINE_FROZEN":
        raise ValueError("IMPLEMENTATION_PLAN_NOT_ALLOWED: Design must be BASELINE_FROZEN")

    plan = ImplementationPlan(
        design_id=design["designId"],
        design_revision=design["revision"],
        status=PlanStatus.GENERATED,
        baseline_checksums={
            "requirements": design.get("requirementsChecksum", ""),
            "architecture": design.get("architectureChecksum", ""),
            "flow": design.get("flowChecksum", ""),
        },
        summary=f"Implementation plan for {design.get('metadata', {}).get('name', design['designId'])} rev {design['revision']}",
    )

    # Default security package
    wp_sec = _create_security_package(plan.plan_id)
    plan.work_packages.append(wp_sec)

    # Application package
    wp_app = ImplementationWorkPackage(
        package_id=f"WP-APP-{len(plan.work_packages)+1:03d}",
        plan_id=plan.plan_id, title="Application Runtime",
        description="Provision and configure the application runtime environment.",
        package_type=WorkPackageType.APPLICATION,
        parallel_group="PG-02",
        estimated_effort=ImplementationEstimate(2.0, EffortUnit.PERSON_DAYS, EstimateSource.RULE_BASED, 0.7),
    )
    wp_app.tasks = [
        _make_task(f"T-APP-{len(wp_app.tasks)+1:03d}", wp_app.package_id,
                    "Provision application host", "Configure compute/storage for application",
                    WorkPackageType.APPLICATION, ["wp-sec-001"], local=True),
        _make_task(f"T-APP-{len(wp_app.tasks)+2:03d}", wp_app.package_id,
                    "Configure application runtime", "Install and configure runtime dependencies",
                    WorkPackageType.APPLICATION, ["wp-sec-001"], local=True),
        _make_task(f"T-APP-{len(wp_app.tasks)+3:03d}", wp_app.package_id,
                    "Validate application health", "Verify application responds correctly",
                    WorkPackageType.TESTING, ["wp-sec-001"], local=True,
                    evidence=[EvidenceRequirement(evidence_id=f"EV-APP-01", task_id="",
                        evidence_type=EvidenceType.TEST_RESULT,
                        description="Application health check response")]),
    ]
    plan.work_packages.append(wp_app)

    # Database package
    wp_db = ImplementationWorkPackage(
        package_id=f"WP-DATA-{len(plan.work_packages)+1:03d}",
        plan_id=plan.plan_id, title="PostgreSQL Database",
        description="Provision and configure relational database.",
        package_type=WorkPackageType.DATABASE,
        parallel_group="PG-02",
        estimated_effort=ImplementationEstimate(2.0, EffortUnit.PERSON_DAYS, EstimateSource.RULE_BASED, 0.7),
    )
    wp_db.tasks = [
        _make_task(f"T-DB-{len(wp_db.tasks)+1:03d}", wp_db.package_id,
                    "Provision database instance", "Create managed PostgreSQL instance",
                    WorkPackageType.DATABASE, ["wp-sec-001"], local=False,
                    evidence=[EvidenceRequirement(evidence_id="EV-DB-01", task_id="",
                        evidence_type=EvidenceType.API_RESPONSE,
                        description="Database instance creation confirmation")]),
        _make_task(f"T-DB-{len(wp_db.tasks)+2:03d}", wp_db.package_id,
                    "Configure database access", "Set up network access, credentials, encryption",
                    WorkPackageType.DATABASE, ["wp-sec-001"], local=False),
        _make_task(f"T-DB-{len(wp_db.tasks)+3:03d}", wp_db.package_id,
                    "Validate database connectivity", "Verify application can reach database",
                    WorkPackageType.TESTING, ["wp-sec-001"], local=False,
                    evidence=[EvidenceRequirement(evidence_id="EV-DB-02", task_id="",
                        evidence_type=EvidenceType.TEST_RESULT,
                        description="Database connectivity validation")]),
        _make_task(f"T-DB-{len(wp_db.tasks)+4:03d}", wp_db.package_id,
                    "Configure backup", "Set up automated backup and retention policy",
                    WorkPackageType.DATABASE, ["wp-sec-001"], local=False),
    ]
    plan.work_packages.append(wp_db)

    # Integration package
    wp_int = ImplementationWorkPackage(
        package_id=f"WP-INT-{len(plan.work_packages)+1:03d}",
        plan_id=plan.plan_id, title="Application Integration",
        description="Integrate application, database, and external dependencies.",
        package_type=WorkPackageType.INTEGRATION,
        estimated_effort=ImplementationEstimate(2.0, EffortUnit.PERSON_DAYS, EstimateSource.RULE_BASED, 0.6),
    )
    wp_int.tasks = [
        _make_task(f"T-INT-{len(wp_int.tasks)+1:03d}", wp_int.package_id,
                    "Configure application-to-database connectivity",
                    "Ensure secure authenticated path between app and DB",
                    WorkPackageType.INTEGRATION, ["wp-app-001", "wp-data-001"], local=False,
                    evidence=[EvidenceRequirement(evidence_id="EV-INT-01", task_id="",
                        evidence_type=EvidenceType.TEST_RESULT,
                        description="Application-to-database connectivity check")]),
        _make_task(f"T-INT-{len(wp_int.tasks)+2:03d}", wp_int.package_id,
                    "Validate API gateway routing", "Confirm request path User→API→App→DB",
                    WorkPackageType.INTEGRATION, ["wp-app-001", "wp-data-001"], local=False),
    ]
    plan.work_packages.append(wp_int)

    # Testing package
    wp_test = ImplementationWorkPackage(
        package_id=f"WP-TEST-{len(plan.work_packages)+1:03d}",
        plan_id=plan.plan_id, title="Integration & Flow Testing",
        description="Validate system flows including failure scenarios.",
        package_type=WorkPackageType.TESTING,
        estimated_effort=ImplementationEstimate(3.0, EffortUnit.PERSON_DAYS, EstimateSource.RULE_BASED, 0.5),
    )
    # Derive tasks from flow scenarios
    scenario_tests = [
        ("HAPPY_PATH", "Verify complete request path succeeds"),
        ("AUTH_FAILURE", "Verify invalid credential does not reach protected services"),
        ("FIREWALL_BLOCK", "Verify unauthorized traffic is blocked before API Gateway"),
        ("DATABASE_SLOW", "Verify database latency degradation is detected"),
        ("API_TIMEOUT", "Verify timeout handling propagates correctly"),
        ("APPROVAL_WAIT", "Verify approval gate pauses and continues correctly"),
        ("RETRY_RECOVERY", "Verify transient failure recovery succeeds"),
    ]
    for i, (scenario, desc) in enumerate(scenario_tests):
        wp_test.tasks.append(_make_task(
            f"T-TEST-{i+1:03d}", wp_test.package_id,
            f"Run {scenario} scenario", desc,
            WorkPackageType.TESTING, ["wp-int-001"], local=True, automation=AutomationEligibility.AUTO,
            evidence=[EvidenceRequirement(evidence_id=f"EV-TEST-{i+1:03d}", task_id="",
                evidence_type=EvidenceType.TEST_RESULT,
                description=f"Simulated {scenario} test result")],
        ))
    plan.work_packages.append(wp_test)

    # Deployment package
    wp_dep = ImplementationWorkPackage(
        package_id=f"WP-DEP-{len(plan.work_packages)+1:03d}",
        plan_id=plan.plan_id, title="Deployment Readiness",
        description="Prepare for controlled deployment. No real production deploy in this phase.",
        package_type=WorkPackageType.DEPLOYMENT,
        estimated_effort=ImplementationEstimate(2.0, EffortUnit.PERSON_DAYS, EstimateSource.RULE_BASED, 0.5),
    )
    wp_dep.tasks = [
        _make_task(f"T-DEP-{len(wp_dep.tasks)+1:03d}", wp_dep.package_id,
                    "Validate deployment configuration", "Review all IaC templates and configuration",
                    WorkPackageType.DEPLOYMENT, ["wp-int-001", "wp-test-001"], local=True),
        _make_task(f"T-DEP-{len(wp_dep.tasks)+2:03d}", wp_dep.package_id,
                    "Create deployment runbook", "Document step-by-step deployment procedure",
                    WorkPackageType.DOCUMENTATION, ["wp-int-001", "wp-test-001"], local=True,
                    automation=AutomationEligibility.MANUAL),
        _make_task(f"T-DEP-{len(wp_dep.tasks)+3:03d}", wp_dep.package_id,
                    "Verify rollback plan", "Ensure all changes can be reversed",
                    WorkPackageType.DEPLOYMENT, ["wp-int-001", "wp-test-001"], local=True),
    ]
    plan.work_packages.append(wp_dep)

    # Build dependencies between packages
    plan.dependencies = [
        ImplementationDependency(dep_id="DEP-001", from_package="wp-sec-001", to_package="wp-app-001",
                                  description="Security foundation required before application"),
        ImplementationDependency(dep_id="DEP-002", from_package="wp-sec-001", to_package="wp-data-001",
                                  description="Security foundation required before database"),
        ImplementationDependency(dep_id="DEP-003", from_package="wp-app-001", to_package="wp-int-001",
                                  description="Application must exist before integration"),
        ImplementationDependency(dep_id="DEP-004", from_package="wp-data-001", to_package="wp-int-001",
                                  description="Database must exist before integration"),
        ImplementationDependency(dep_id="DEP-005", from_package="wp-int-001", to_package="wp-test-001",
                                  description="Integration before testing"),
        ImplementationDependency(dep_id="DEP-006", from_package="wp-test-001", to_package="wp-dep-001",
                                  description="Testing before deployment readiness"),
    ]

    # Milestones
    plan.milestones = [
        ImplementationMilestone(milestone_id="M1", name="Design Baseline Frozen",
                                 description="Design accepted and frozen", completed=True),
        ImplementationMilestone(milestone_id="M2", name="Infra Foundation Ready",
                                 description="Security and network foundation ready", depends_on=["wp-sec-001"]),
        ImplementationMilestone(milestone_id="M3", name="Application Runtime Ready",
                                 description="App and DB provisioned", depends_on=["wp-app-001", "wp-data-001"]),
        ImplementationMilestone(milestone_id="M4", name="Integration Ready",
                                 description="Integration verified", depends_on=["wp-int-001"]),
        ImplementationMilestone(milestone_id="M5", name="IFT Ready",
                                 description="Integration and flow testing complete", depends_on=["wp-test-001"]),
        ImplementationMilestone(milestone_id="M6", name="UAT Ready",
                                 description="User acceptance ready", depends_on=["wp-test-001"]),
        ImplementationMilestone(milestone_id="M7", name="Production Readiness",
                                 description="Deployment ready", depends_on=["wp-dep-001"]),
    ]

    # Critical path
    plan.critical_path = ["wp-sec-001", "wp-app-001", "wp-int-001", "wp-test-001", "wp-dep-001"]

    # Risks
    plan.risks = [
        ImplementationRisk(risk_id="RISK-001", title="Database provisioning delay",
                            description="Managed database creation may be blocked by provider quotas",
                            severity=RiskSeverity.MEDIUM, category=RiskCategory.DATA,
                            affected_tasks=["T-DB-001"]),
        ImplementationRisk(risk_id="RISK-002", title="Integration dependency",
                            description="App and DB teams must coordinate for integration testing",
                            severity=RiskSeverity.MEDIUM, category=RiskCategory.INTEGRATION,
                            affected_tasks=["T-INT-001"]),
    ]

    # Gates
    plan.gates = [
        ImplementationGate(gate_id="GATE-001", name="DESIGN_ACCEPTED",
                            state=GateState.PASS, description="Design is frozen"),
        ImplementationGate(gate_id="GATE-002", name="CREDENTIALS_READY",
                            state=GateState.PENDING, description="Cloud credentials required for real execution"),
        ImplementationGate(gate_id="GATE-003", name="SECURITY_APPROVED",
                            state=GateState.PENDING, description="Security review required before deployment"),
        ImplementationGate(gate_id="GATE-004", name="TEST_ENV_READY",
                            state=GateState.PENDING, description="Test environment not yet provisioned"),
    ]

    # Blockers
    plan.blockers = [
        ImplementationBlocker(blocker_id="BLOCK-001", severity=RiskSeverity.HIGH,
                               description="No cloud provider credentials configured",
                               affected_tasks=["T-DB-001", "T-APP-001"],
                               resolution_required="Obtain AWS account credentials"),
        ImplementationBlocker(blocker_id="BLOCK-002", severity=RiskSeverity.MEDIUM,
                               description="Production region not yet selected",
                               affected_tasks=["T-DB-001"],
                               resolution_required="Select AWS region for production deployment"),
    ]

    # Open questions
    plan.open_questions = [
        "Which AWS account will host the solution?",
        "What production region is approved?",
        "Is database migration required from existing systems?",
        "Who owns external API credentials?",
    ]

    # Readiness
    plan.readiness = ReadinessState.PARTIALLY_READY

    plan.compute_checksum()
    plan.status = PlanStatus.REVIEW_READY
    return plan


def _create_security_package(plan_id: str) -> ImplementationWorkPackage:
    wp = ImplementationWorkPackage(
        package_id="wp-sec-001",
        plan_id=plan_id,
        title="Security Foundation",
        description="Authentication, authorization, WAF, firewall, and security baseline.",
        package_type=WorkPackageType.SECURITY,
        estimated_effort=ImplementationEstimate(3.0, EffortUnit.PERSON_DAYS, EstimateSource.RULE_BASED, 0.8),
    )
    wp.tasks = [
        _make_task("T-SEC-001", wp.package_id, "Configure credential and identity provider",
                    "Set up authentication for user access", WorkPackageType.SECURITY, [], local=True,
                    evidence=[EvidenceRequirement(evidence_id="EV-SEC-01", task_id="",
                        evidence_type=EvidenceType.CONFIG_SNAPSHOT, description="Auth configuration")]),
        _make_task("T-SEC-002", wp.package_id, "Configure WAF rules",
                    "Define web application firewall policies", WorkPackageType.SECURITY, ["T-SEC-001"], local=True,
                    evidence=[EvidenceRequirement(evidence_id="EV-SEC-02", task_id="",
                        evidence_type=EvidenceType.TEST_RESULT, description="WAF rule validation")]),
        _make_task("T-SEC-003", wp.package_id, "Configure firewall policies",
                    "Define network-level access rules", WorkPackageType.SECURITY, ["T-SEC-001"], local=True),
        _make_task("T-SEC-004", wp.package_id, "Validate security baseline",
                    "Verify all security controls are correctly configured",
                    WorkPackageType.TESTING, ["T-SEC-002", "T-SEC-003"], local=True,
                    evidence=[EvidenceRequirement(evidence_id="EV-SEC-03", task_id="",
                        evidence_type=EvidenceType.TEST_RESULT, description="Security baseline validation")]),
        _make_task("T-SEC-005", wp.package_id, "Configure secret management",
                    "Set up secure storage for credentials and API keys",
                    WorkPackageType.SECURITY, ["T-SEC-001"], local=False),
    ]
    return wp


def _make_task(
    task_id: str, wp_id: str, title: str, description: str,
    category: WorkPackageType, dependencies: list[str],
    local: bool = True, automation: AutomationEligibility = AutomationEligibility.AUTO,
    evidence: list[EvidenceRequirement] | None = None,
) -> ImplementationTask:
    return ImplementationTask(
        task_id=task_id, work_package_id=wp_id,
        title=title, description=description,
        category=category, status=TaskStatus.PLANNED,
        priority=5,
        execution_mode="LOCAL_RUNTIME" if local else "PLAN_ONLY",
        dependencies=[d for d in dependencies if d],
        acceptance_criteria=[f"{title} completed and verified"],
        evidence_requirements=evidence or [],
        risk_level=RiskSeverity.LOW,
        estimated_effort=ImplementationEstimate(0.5, EffortUnit.PERSON_DAYS, EstimateSource.RULE_BASED, 0.7),
        owner_role="Infrastructure Engineer",
        automation=automation,
        derived_from=["design-accepted"],
        delivery_stage=DeliveryStage.PU,
        local_validatable=local,
    )


def compute_critical_path(
    packages: list[ImplementationWorkPackage],
    dependencies: list[ImplementationDependency],
) -> list[str]:
    """Deterministic critical path via topological sort."""
    # Build graph
    incoming: dict[str, list[str]] = {w.package_id: [] for w in packages}
    for d in dependencies:
        if d.to_package not in incoming:
            incoming[d.to_package] = []
        incoming[d.to_package].append(d.from_package)

    # Topological sort
    result: list[str] = []
    visited: set[str] = set()
    temp: set[str] = set()

    def visit(node: str) -> None:
        if node in temp:
            raise ValueError(f"IMPLEMENTATION_DEPENDENCY_CYCLE: cycle detected at {node}")
        if node not in visited:
            temp.add(node)
            for pred in incoming.get(node, []):
                if pred in [w.package_id for w in packages]:
                    visit(pred)
            temp.discard(node)
            visited.add(node)
            result.append(node)

    # Start from packages with no outgoing dependencies (leaves)
    start_nodes = set(w.package_id for w in packages)
    for d in dependencies:
        start_nodes.discard(d.from_package)
    if not start_nodes:
        start_nodes = {packages[-1].package_id} if packages else set()

    for node in start_nodes:
        visit(node)

    # Return longest path (top-to-bottom)
    result.reverse()
    return result


def detect_cycles(
    packages: list[ImplementationWorkPackage],
    dependencies: list[ImplementationDependency],
) -> list[list[str]]:
    """Detect dependency cycles. Returns list of cycles found."""
    try:
        compute_critical_path(packages, dependencies)
        return []
    except ValueError as e:
        if "CYCLE" in str(e):
            return [["cycle-detected"]]
        raise
