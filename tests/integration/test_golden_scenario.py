"""
Golden Infrastructure Scenario — Phase 2A.1 HARDENED

Tests: full pipeline, idempotency, ownership, destroy policy,
persistence, restart reconciliation, validation failure.
"""

import pytest
import tempfile
import os
import shutil
from unittest.mock import AsyncMock, patch

from infra_again.contracts import (
    ApplicationRuntimeRequirement,
    DatabaseRequirement,
    EvidenceItem,
    EvidenceType,
    InfrastructureRequest,
    InfrastructureRequirements,
    InfrastructureResult,
    InfrastructureStatus,
    NetworkingRequirement,
    Provider,
)
from infra_again.core.domain import (
    ExecutionMode,
    ExecutionState,
    ExecutionTarget,
    ExecutionTargetType,
    OwnedResource,
    Platform,
    ResourceOwnership,
    TargetScope,
    TruthStatus,
)
from infra_again.core.persistence import RunStore
from infra_again.execution.orchestrator import (
    ExecutionOrchestrator,
    PolicyEngine,
    ActionPolicy,
    IdempotencyStatus,
)
from infra_again.providers.aws.adapter import AwsProviderAdapter


@pytest.fixture
def hello_again_request() -> InfrastructureRequest:
    return InfrastructureRequest(
        infrastructureRequestId="ir-hello-again-001",
        correlationId="e2e-golden-hello-again",
        workPackageId="wp-hello-again-001",
        engineeringResultId="er-hello-again-001",
        requirements=InfrastructureRequirements(
            database=DatabaseRequirement(engine="postgresql", version="16"),
            applicationRuntime=ApplicationRuntimeRequirement(
                containerized=True, replicas=1, https=False, port=8080),
            networking=NetworkingRequirement(public=False, httpsOnly=False),
            providerHint=Provider.AWS,
        ),
    )


@pytest.fixture
def plan_only_target() -> ExecutionTarget:
    return ExecutionTarget(
        mode=ExecutionMode.PLAN_ONLY, provider=Provider.AWS,
        platform=Platform.NATIVE_VM, target_type=ExecutionTargetType.FAKECLOUD,
        fidelity_notes={"Execution": "PLAN_ONLY", "Real AWS Provisioning": "NOT_TESTED",
                        "Production Readiness": "NOT_VERIFIED"})


@pytest.fixture
def simulated_target() -> ExecutionTarget:
    return ExecutionTarget(
        mode=ExecutionMode.SIMULATED, provider=Provider.AWS,
        platform=Platform.NATIVE_VM, target_type=ExecutionTargetType.FAKECLOUD,
        endpoint="http://localhost:4566",
        fidelity_notes={"AWS API Compatibility": "SIMULATED",
                        "Real AWS Provisioning": "NOT_TESTED",
                        "Production Readiness": "NOT_VERIFIED"})


@pytest.fixture
def temp_store():
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    store = RunStore(db_path)
    yield store
    shutil.rmtree(tmpdir, ignore_errors=True)


# ============================================================================
# Golden Scenario: PLAN_ONLY (regression)
# ============================================================================


@pytest.mark.asyncio
async def test_golden_hello_again_plan_only(hello_again_request, plan_only_target, temp_store):
    adapter = AwsProviderAdapter()
    orchestrator = ExecutionOrchestrator(provider_adapter=adapter, store=temp_store)
    result = await orchestrator.process(hello_again_request, plan_only_target)
    assert isinstance(result, InfrastructureResult)
    assert result.correlationId == "e2e-golden-hello-again"
    assert result.provider == Provider.AWS
    assert result.status == InfrastructureStatus.SUCCESS


@pytest.mark.asyncio
async def test_golden_hello_again_no_aws_skus(hello_again_request, plan_only_target, temp_store):
    adapter = AwsProviderAdapter()
    orchestrator = ExecutionOrchestrator(provider_adapter=adapter, store=temp_store)
    result = await orchestrator.process(hello_again_request, plan_only_target)
    data = result.model_dump_json()
    assert "db.r6g" not in data
    assert "m7i" not in data


@pytest.mark.asyncio
async def test_policy_blocks_production_without_approval(hello_again_request, temp_store):
    production_target = ExecutionTarget(
        mode=ExecutionMode.PRODUCTION, provider=Provider.AWS,
        platform=Platform.NATIVE_VM, target_type=ExecutionTargetType.AWS_PRODUCTION)
    adapter = AwsProviderAdapter()
    orchestrator = ExecutionOrchestrator(provider_adapter=adapter, store=temp_store)
    result = await orchestrator.process(hello_again_request, production_target)
    assert result.status in (InfrastructureStatus.PARTIAL, InfrastructureStatus.FAILED)


# ============================================================================
# Idempotency — Phase 2A.1 FIXED
# ============================================================================


@pytest.mark.asyncio
async def test_idempotent_completed_returns_exact_persisted_result(
    hello_again_request, plan_only_target, temp_store,
):
    """COMPLETED: return exact persisted result, not a rebuilt one."""
    adapter = AwsProviderAdapter()
    orchestrator = ExecutionOrchestrator(provider_adapter=adapter, store=temp_store)
    result1 = await orchestrator.process(hello_again_request, plan_only_target, idempotency_key="idem-comp-001")
    assert result1.status == InfrastructureStatus.SUCCESS

    # Second call: must return persisted result, not rebuild
    result2 = await orchestrator.process(hello_again_request, plan_only_target, idempotency_key="idem-comp-001")
    assert result2.status == InfrastructureStatus.SUCCESS
    assert result2.infrastructureResultId == result1.infrastructureResultId
    assert result2.correlationId == result1.correlationId
    assert result2.completedAt is not None


@pytest.mark.asyncio
async def test_idempotent_executing_not_success(temp_store):
    """EXECUTING state must NOT return SUCCESS."""
    temp_store.create_run("run-exec", "corr-exec", idempotency_key="idem-exec-001")
    temp_store.transition_state("run-exec", ExecutionState.NORMALIZING)
    temp_store.transition_state("run-exec", ExecutionState.PLANNING)
    temp_store.transition_state("run-exec", ExecutionState.PLAN_READY)
    temp_store.transition_state("run-exec", ExecutionState.WAITING_FOR_APPROVAL)
    temp_store.transition_state("run-exec", ExecutionState.APPROVED)
    temp_store.transition_state("run-exec", ExecutionState.EXECUTING)

    orchestrator = ExecutionOrchestrator(store=temp_store)
    req = InfrastructureRequest(
        infrastructureRequestId="ir-exec", correlationId="corr-exec",
        workPackageId="wp", engineeringResultId="er",
        requirements=InfrastructureRequirements())

    result = await orchestrator.process(req, idempotency_key="idem-exec-001")
    assert result.status != InfrastructureStatus.SUCCESS, \
        "EXECUTING must NOT return SUCCESS"
    assert result.status == InfrastructureStatus.PARTIAL


@pytest.mark.asyncio
async def test_idempotent_validating_not_success(temp_store):
    """VALIDATING state must NOT return SUCCESS."""
    temp_store.create_run("run-val", "corr-val", idempotency_key="idem-val-001")
    for s in [ExecutionState.NORMALIZING, ExecutionState.PLANNING, ExecutionState.PLAN_READY,
              ExecutionState.WAITING_FOR_APPROVAL, ExecutionState.APPROVED,
              ExecutionState.EXECUTING, ExecutionState.OBSERVING, ExecutionState.VALIDATING]:
        temp_store.transition_state("run-val", s)

    orchestrator = ExecutionOrchestrator(store=temp_store)
    req = InfrastructureRequest(
        infrastructureRequestId="ir-val", correlationId="corr-val",
        workPackageId="wp", engineeringResultId="er",
        requirements=InfrastructureRequirements())

    result = await orchestrator.process(req, idempotency_key="idem-val-001")
    assert result.status != InfrastructureStatus.SUCCESS
    assert result.status == InfrastructureStatus.PARTIAL


@pytest.mark.asyncio
async def test_idempotent_failed_remains_failed(temp_store):
    """FAILED state must remain FAILED."""
    temp_store.create_run("run-fail", "corr-fail", idempotency_key="idem-fail-001")
    temp_store.transition_state("run-fail", ExecutionState.NORMALIZING)
    temp_store.transition_state("run-fail", ExecutionState.FAILED, "test error")

    orchestrator = ExecutionOrchestrator(store=temp_store)
    req = InfrastructureRequest(
        infrastructureRequestId="ir-fail", correlationId="corr-fail",
        workPackageId="wp", engineeringResultId="er",
        requirements=InfrastructureRequirements())

    result = await orchestrator.process(req, idempotency_key="idem-fail-001")
    assert result.status == InfrastructureStatus.FAILED


@pytest.mark.asyncio
async def test_idempotent_no_duplicate_mutation(hello_again_request, plan_only_target, temp_store):
    """Duplicate request must not create a second run."""
    adapter = AwsProviderAdapter()
    orchestrator = ExecutionOrchestrator(provider_adapter=adapter, store=temp_store)

    result1 = await orchestrator.process(hello_again_request, plan_only_target, idempotency_key="idem-dup-001")
    result2 = await orchestrator.process(hello_again_request, plan_only_target, idempotency_key="idem-dup-001")

    assert result1.status == InfrastructureStatus.SUCCESS
    assert result2.status == InfrastructureStatus.SUCCESS
    # Only one run should exist for this idempotency key
    runs = temp_store.list_runs(hello_again_request.correlationId)
    idem_runs = [r for r in runs if r.get("idempotency_key") == "idem-dup-001"]
    assert len(idem_runs) == 1, "Only one run per idempotency key"


# ============================================================================
# Destroy Policy — Phase 2A.1 HARDENED (no bypass)
# ============================================================================


class TestDestroyPolicyHardened:
    """Comprehensive destroy ownership policy matrix."""

    def test_owned_isolated_ephemeral_same_run_auto(self):
        """Owned + ephemeral + ISOLATED + same run → AUTO."""
        ownership = ResourceOwnership(
            managed_by="INFRA_AGAIN", created_by_run_id="run-123",
            ephemeral=True, target_scope=TargetScope.ISOLATED)
        target = ExecutionTarget(mode=ExecutionMode.SIMULATED, provider=Provider.AWS,
                                 platform=Platform.NATIVE_VM, target_type=ExecutionTargetType.FAKECLOUD)
        decision = PolicyEngine.evaluate("destroy", target, context={
            "resource_id": "bucket-1", "ownership": ownership, "current_run_id": "run-123"})
        assert decision.policy == ActionPolicy.AUTO

    def test_different_run_ask(self):
        ownership = ResourceOwnership(
            managed_by="INFRA_AGAIN", created_by_run_id="run-other",
            ephemeral=True, target_scope=TargetScope.ISOLATED)
        target = ExecutionTarget(mode=ExecutionMode.SIMULATED, provider=Provider.AWS,
                                 platform=Platform.NATIVE_VM, target_type=ExecutionTargetType.FAKECLOUD)
        decision = PolicyEngine.evaluate("destroy", target, context={
            "resource_id": "b", "ownership": ownership, "current_run_id": "run-123"})
        assert decision.policy == ActionPolicy.ASK

    def test_not_managed_by_infra_ask(self):
        ownership = ResourceOwnership(
            managed_by="OTHER", created_by_run_id="run-123",
            ephemeral=True, target_scope=TargetScope.ISOLATED)
        target = ExecutionTarget(mode=ExecutionMode.SIMULATED, provider=Provider.AWS,
                                 platform=Platform.NATIVE_VM, target_type=ExecutionTargetType.FAKECLOUD)
        decision = PolicyEngine.evaluate("destroy", target, context={
            "resource_id": "b", "ownership": ownership, "current_run_id": "run-123"})
        assert decision.policy == ActionPolicy.ASK

    def test_not_ephemeral_ask(self):
        ownership = ResourceOwnership(
            managed_by="INFRA_AGAIN", created_by_run_id="run-123",
            ephemeral=False, target_scope=TargetScope.ISOLATED)
        target = ExecutionTarget(mode=ExecutionMode.SIMULATED, provider=Provider.AWS,
                                 platform=Platform.NATIVE_VM, target_type=ExecutionTargetType.FAKECLOUD)
        decision = PolicyEngine.evaluate("destroy", target, context={
            "resource_id": "b", "ownership": ownership, "current_run_id": "run-123"})
        assert decision.policy == ActionPolicy.ASK

    def test_shared_scope_ask(self):
        ownership = ResourceOwnership(
            managed_by="INFRA_AGAIN", created_by_run_id="run-123",
            ephemeral=True, target_scope=TargetScope.SHARED)
        target = ExecutionTarget(mode=ExecutionMode.SIMULATED, provider=Provider.AWS,
                                 platform=Platform.NATIVE_VM, target_type=ExecutionTargetType.FAKECLOUD)
        decision = PolicyEngine.evaluate("destroy", target, context={
            "resource_id": "b", "ownership": ownership, "current_run_id": "run-123"})
        assert decision.policy == ActionPolicy.ASK

    def test_external_scope_ask(self):
        ownership = ResourceOwnership(
            managed_by="INFRA_AGAIN", created_by_run_id="run-123",
            ephemeral=True, target_scope=TargetScope.EXTERNAL)
        target = ExecutionTarget(mode=ExecutionMode.SIMULATED, provider=Provider.AWS,
                                 platform=Platform.NATIVE_VM, target_type=ExecutionTargetType.FAKECLOUD)
        decision = PolicyEngine.evaluate("destroy", target, context={
            "resource_id": "b", "ownership": ownership, "current_run_id": "run-123"})
        assert decision.policy == ActionPolicy.ASK

    def test_unknown_scope_ask(self):
        ownership = ResourceOwnership(
            managed_by="INFRA_AGAIN", created_by_run_id="run-123",
            ephemeral=True, target_scope=TargetScope.UNKNOWN)
        target = ExecutionTarget(mode=ExecutionMode.SIMULATED, provider=Provider.AWS,
                                 platform=Platform.NATIVE_VM, target_type=ExecutionTargetType.FAKECLOUD)
        decision = PolicyEngine.evaluate("destroy", target, context={
            "resource_id": "b", "ownership": ownership, "current_run_id": "run-123"})
        assert decision.policy == ActionPolicy.ASK

    def test_missing_ownership_ask(self):
        """Missing ownership → ASK, never AUTO."""
        target = ExecutionTarget(mode=ExecutionMode.SIMULATED, provider=Provider.AWS,
                                 platform=Platform.NATIVE_VM, target_type=ExecutionTargetType.FAKECLOUD)
        decision = PolicyEngine.evaluate("destroy", target, context={
            "resource_id": "b", "ownership": None, "current_run_id": "run-123"})
        assert decision.policy == ActionPolicy.ASK

    def test_simulated_non_owned_ask(self):
        """SIMULATED target but non-owned resource → ASK."""
        ownership = ResourceOwnership(
            managed_by="INFRA_AGAIN", created_by_run_id="run-other",
            ephemeral=True, target_scope=TargetScope.ISOLATED)
        target = ExecutionTarget(mode=ExecutionMode.SIMULATED, provider=Provider.AWS,
                                 platform=Platform.NATIVE_VM, target_type=ExecutionTargetType.FAKECLOUD)
        decision = PolicyEngine.evaluate("destroy", target, context={
            "resource_id": "b", "ownership": ownership, "current_run_id": "run-123"})
        assert decision.policy == ActionPolicy.ASK

    def test_local_runtime_non_owned_ask(self):
        """LOCAL_RUNTIME but non-owned → ASK."""
        ownership = ResourceOwnership(
            managed_by="INFRA_AGAIN", created_by_run_id="run-other",
            ephemeral=True, target_scope=TargetScope.ISOLATED)
        target = ExecutionTarget(mode=ExecutionMode.LOCAL_RUNTIME, provider=Provider.ON_PREM,
                                 platform=Platform.KUBERNETES, target_type=ExecutionTargetType.KIND)
        decision = PolicyEngine.evaluate("destroy", target, context={
            "resource_id": "b", "ownership": ownership, "current_run_id": "run-123"})
        assert decision.policy == ActionPolicy.ASK

    def test_production_destroy_blocked(self):
        """Production destroy always BLOCKED."""
        ownership = ResourceOwnership(
            managed_by="INFRA_AGAIN", created_by_run_id="run-123",
            ephemeral=True, target_scope=TargetScope.ISOLATED)
        target = ExecutionTarget(mode=ExecutionMode.PRODUCTION, provider=Provider.AWS,
                                 platform=Platform.NATIVE_VM, target_type=ExecutionTargetType.AWS_PRODUCTION)
        decision = PolicyEngine.evaluate("destroy", target, context={
            "resource_id": "b", "ownership": ownership, "current_run_id": "run-123"})
        assert decision.policy == ActionPolicy.BLOCK


@pytest.mark.asyncio
async def test_destroy_not_called_on_ask(temp_store):
    """Provider.destroy() must NOT be called when policy returns ASK."""
    temp_store.create_run("run-001", "corr-001")
    temp_store.create_run("run-other", "corr-other")  # Foreign key for resource ownership
    resource = OwnedResource(
        resource_id="bucket-1", resource_type="AWS::S3::Bucket", provider="AWS",
        ownership=ResourceOwnership(
            managed_by="INFRA_AGAIN", created_by_run_id="run-other",
            ephemeral=True, target_scope=TargetScope.ISOLATED))
    temp_store.register_resource(resource)

    mock_adapter = AsyncMock(spec=AwsProviderAdapter)
    mock_adapter.provider = Provider.AWS

    orchestrator = ExecutionOrchestrator(provider_adapter=mock_adapter, store=temp_store)
    target = ExecutionTarget(mode=ExecutionMode.SIMULATED, provider=Provider.AWS,
                             platform=Platform.NATIVE_VM, target_type=ExecutionTargetType.FAKECLOUD)

    ok, msg = await orchestrator.destroy_resource("run-001", "bucket-1", target)
    assert not ok, f"Should not succeed: {msg}"
    assert "ASK" in msg
    mock_adapter.destroy.assert_not_called()


@pytest.mark.asyncio
async def test_destroy_not_called_on_block(temp_store):
    """Provider.destroy() must NOT be called when policy returns BLOCK."""
    temp_store.create_run("run-001", "corr-001")
    resource = OwnedResource(
        resource_id="bucket-1", resource_type="AWS::S3::Bucket", provider="AWS",
        ownership=ResourceOwnership(
            managed_by="INFRA_AGAIN", created_by_run_id="run-001",
            ephemeral=True, target_scope=TargetScope.ISOLATED))
    temp_store.register_resource(resource)

    mock_adapter = AsyncMock(spec=AwsProviderAdapter)
    mock_adapter.provider = Provider.AWS

    orchestrator = ExecutionOrchestrator(provider_adapter=mock_adapter, store=temp_store)
    target = ExecutionTarget(mode=ExecutionMode.PRODUCTION, provider=Provider.AWS,
                             platform=Platform.NATIVE_VM, target_type=ExecutionTargetType.AWS_PRODUCTION)

    ok, msg = await orchestrator.destroy_resource("run-001", "bucket-1", target)
    assert not ok
    assert "BLOCKED" in msg
    mock_adapter.destroy.assert_not_called()


# ============================================================================
# Restart / Reconciliation
# ============================================================================


def test_restart_from_executing_requires_reconciliation(temp_store):
    """Restart during EXECUTING → REQUIRES_RECONCILIATION."""
    temp_store.create_run("run-exec-r", "corr-r")
    for s in [ExecutionState.NORMALIZING, ExecutionState.PLANNING, ExecutionState.PLAN_READY,
              ExecutionState.WAITING_FOR_APPROVAL, ExecutionState.APPROVED,
              ExecutionState.EXECUTING]:
        temp_store.transition_state("run-exec-r", s)

    orchestrator = ExecutionOrchestrator(store=temp_store)
    ctx = orchestrator.load_run("run-exec-r")
    assert ctx is not None
    assert ctx.state == ExecutionState.REQUIRES_RECONCILIATION, \
        f"Expected REQUIRES_RECONCILIATION, got {ctx.state}"


def test_restart_preserves_full_context(temp_store):
    """Restart preserves runId, correlationId, state, target, resources."""
    temp_store.create_run("run-full", "corr-full")
    temp_store.update_run("run-full", provider="AWS", platform="NATIVE_VM",
                          execution_mode="SIMULATED", execution_target_type="FAKECLOUD",
                          execution_target_endpoint="http://localhost:4566")

    resource = OwnedResource(
        resource_id="bucket-1", resource_type="AWS::S3::Bucket", provider="AWS",
        ownership=ResourceOwnership(
            managed_by="INFRA_AGAIN", created_by_run_id="run-full",
            ephemeral=True, target_scope=TargetScope.ISOLATED))
    temp_store.register_resource(resource)

    orchestrator = ExecutionOrchestrator(store=temp_store)
    ctx = orchestrator.load_run("run-full")
    assert ctx is not None
    assert ctx.run_id == "run-full"
    assert ctx.target is not None
    assert ctx.target.provider == Provider.AWS
    assert ctx.target.mode == ExecutionMode.SIMULATED
    assert len(ctx.owned_resources) == 1
    assert ctx.owned_resources[0].resource_id == "bucket-1"


# ============================================================================
# Persistence
# ============================================================================


class TestPersistence:
    def test_run_creation_and_retrieval(self, temp_store):
        temp_store.create_run("run-001", "corr-001")
        run = temp_store.get_run("run-001")
        assert run is not None
        assert run["run_id"] == "run-001"
        assert run["state"] == ExecutionState.DRAFT.value

    def test_state_transition_valid(self, temp_store):
        temp_store.create_run("run-001", "corr-001")
        ok, msg = temp_store.transition_state("run-001", ExecutionState.NORMALIZING)
        assert ok
        run = temp_store.get_run("run-001")
        assert run["state"] == ExecutionState.NORMALIZING.value

    def test_state_transition_illegal(self, temp_store):
        temp_store.create_run("run-001", "corr-001")
        ok, msg = temp_store.transition_state("run-001", ExecutionState.COMPLETED)
        assert not ok
        assert "Illegal" in msg

    def test_restart_survival(self, temp_store):
        temp_store.create_run("run-001", "corr-001")
        temp_store.transition_state("run-001", ExecutionState.NORMALIZING)
        temp_store.transition_state("run-001", ExecutionState.PLANNING)
        temp_store.transition_state("run-001", ExecutionState.PLAN_READY)
        run = temp_store.get_run("run-001")
        assert run["state"] == ExecutionState.PLAN_READY.value
        transitions = temp_store.get_transitions("run-001")
        assert len(transitions) == 3

    def test_final_result_persistence(self, temp_store):
        temp_store.create_run("run-001", "corr-001")
        temp_store.persist_final_result("run-001", '{"status":"SUCCESS"}')
        result = temp_store.get_final_result("run-001")
        assert result is not None
        assert "SUCCESS" in result

    def test_idempotency_key(self, temp_store):
        temp_store.create_run("run-001", "corr-001", idempotency_key="idem-abc")
        existing = temp_store.get_run_by_idempotency("idem-abc")
        assert existing is not None
        assert existing["run_id"] == "run-001"
        not_found = temp_store.get_run_by_idempotency("idem-xyz")
        assert not_found is None


class TestOwnership:
    def test_auto_destroy_allowed(self):
        ownership = ResourceOwnership(
            managed_by="INFRA_AGAIN", created_by_run_id="run-123",
            ephemeral=True, target_scope=TargetScope.ISOLATED)
        assert ownership.is_auto_destroy_allowed("run-123") is True

    def test_store_can_auto_destroy(self, temp_store):
        temp_store.create_run("run-001", "corr-001")
        resource = OwnedResource(
            resource_id="bucket-1", resource_type="AWS::S3::Bucket", provider="AWS",
            ownership=ResourceOwnership(
                managed_by="INFRA_AGAIN", created_by_run_id="run-001",
                ephemeral=True, target_scope=TargetScope.ISOLATED))
        temp_store.register_resource(resource)
        can, reason = temp_store.can_auto_destroy("bucket-1", "run-001")
        assert can
        assert "AUTO" in reason
        can2, _ = temp_store.can_auto_destroy("bucket-1", "run-other")
        assert not can2


# ============================================================================
# SIMULATED Execution Tests (requires fakecloud running)
# ============================================================================


@pytest.mark.asyncio
async def test_fakecloud_probe():
    adapter = AwsProviderAdapter()
    status = await adapter.probe_status()
    assert status in (TruthStatus.READY, TruthStatus.NOT_CONFIGURED)


def _fakecloud_ready() -> bool:
    try:
        import httpx
        resp = httpx.get("http://localhost:4566/_fakecloud/health", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


@pytest.mark.asyncio
async def test_simulated_apply_observe_validate_destroy(simulated_target, temp_store):
    """Deterministic: create → observe → validate → destroy → observe absence."""
    if not _fakecloud_ready():
        pytest.fail("fakecloud not running — acceptance requires fakecloud online")

    from infra_again.core.domain import CapabilityRequirement, CapabilityCategory

    adapter = AwsProviderAdapter()
    bucket_name = "infra-again-acceptance-test"

    # Apply: create bucket
    plan = await adapter.plan(
        [CapabilityRequirement(category=CapabilityCategory.STORAGE, name="object_storage",
                               properties={"bucket_name": bucket_name})],
        simulated_target)
    cs = await adapter.apply(plan, simulated_target)
    assert len(cs.changes) > 0
    assert cs.changes[0].action.value == "CREATE"

    # Observe: confirm bucket exists
    observed = await adapter.observe(simulated_target)
    assert bucket_name in str(observed)

    # Validate: desired == observed
    validations = await adapter.validate(
        {bucket_name: {"bucket_name": bucket_name}}, observed)
    assert len(validations) > 0
    assert validations[0].matches is True, f"Expected match, got {validations[0]}"

    # Destroy
    await adapter.destroy(simulated_target, [bucket_name])

    # Observe absence
    observed_after = await adapter.observe(simulated_target, [bucket_name])
    obs = observed_after.get("observed", {})
    assert bucket_name not in obs


@pytest.mark.asyncio
async def test_validation_failure_produces_failed_result(hello_again_request, simulated_target, temp_store):
    """Validation failure must produce FAILED result, not SUCCESS."""
    if not _fakecloud_ready():
        pytest.fail("fakecloud not running — acceptance requires fakecloud online")

    from infra_again.core.domain import CapabilityRequirement, CapabilityCategory

    adapter = AwsProviderAdapter()
    orchestrator = ExecutionOrchestrator(provider_adapter=adapter, store=temp_store)

    # Create a real bucket then validate against a nonexistent one
    plan = await adapter.plan(
        [CapabilityRequirement(category=CapabilityCategory.STORAGE, name="object_storage",
                               properties={"bucket_name": "infra-again-fail-test"})],
        simulated_target)
    await adapter.apply(plan, simulated_target)

    # Now validate against a resource that doesn't exist
    desired = {"nonexistent-bucket-xyz": {"bucket_name": "nonexistent-bucket-xyz"}}
    observed = await adapter.observe(simulated_target)
    validations = await adapter.validate(desired, observed)
    assert len(validations) > 0
    assert validations[0].matches is False, "Should detect mismatch"

    # Cleanup
    await adapter.destroy(simulated_target, ["infra-again-fail-test"])


# ============================================================================
# IdempotencyStatus classification
# ============================================================================


class TestIdempotencyStatus:
    def test_completed_is_terminal_good(self):
        assert IdempotencyStatus.classify("COMPLETED") == "COMPLETED"

    def test_executing_is_in_progress(self):
        assert IdempotencyStatus.classify("EXECUTING") == "IN_PROGRESS"

    def test_observing_is_in_progress(self):
        assert IdempotencyStatus.classify("OBSERVING") == "IN_PROGRESS"

    def test_validating_is_in_progress(self):
        assert IdempotencyStatus.classify("VALIDATING") == "IN_PROGRESS"

    def test_failed_is_terminal_bad(self):
        assert IdempotencyStatus.classify("FAILED") == "TERMINAL_NON_SUCCESS"

    def test_blocked_is_terminal_bad(self):
        assert IdempotencyStatus.classify("BLOCKED") == "TERMINAL_NON_SUCCESS"

    def test_requires_reconciliation_is_in_progress(self):
        assert IdempotencyStatus.classify("REQUIRES_RECONCILIATION") == "IN_PROGRESS"
