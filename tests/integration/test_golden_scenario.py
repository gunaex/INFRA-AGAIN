"""
Golden Infrastructure Scenario — "hello-again" Phase 2A

Tests the full pipeline: PLAN_ONLY and SIMULATED (fakecloud).
"""

import pytest
import tempfile
import os
import shutil

from infra_again.contracts import (
    ApplicationRuntimeRequirement,
    DatabaseRequirement,
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
    Platform,
    ResourceOwnership,
    TargetScope,
    TruthStatus,
)
from infra_again.core.persistence import RunStore
from infra_again.execution.orchestrator import ExecutionOrchestrator
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
    """Create a temporary SQLite database for testing."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    store = RunStore(db_path)
    yield store
    shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Golden Scenario: hello-again (PLAN_ONLY)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_golden_hello_again_plan_only(
    hello_again_request: InfrastructureRequest, plan_only_target: ExecutionTarget,
    temp_store: RunStore,
):
    adapter = AwsProviderAdapter()
    orchestrator = ExecutionOrchestrator(provider_adapter=adapter, store=temp_store)
    result = await orchestrator.process(hello_again_request, plan_only_target)
    assert isinstance(result, InfrastructureResult)
    assert result.correlationId == "e2e-golden-hello-again"
    assert result.provider == Provider.AWS
    assert result.status == InfrastructureStatus.SUCCESS


@pytest.mark.asyncio
async def test_golden_hello_again_no_aws_skus(
    hello_again_request: InfrastructureRequest, plan_only_target: ExecutionTarget,
    temp_store: RunStore,
):
    adapter = AwsProviderAdapter()
    orchestrator = ExecutionOrchestrator(provider_adapter=adapter, store=temp_store)
    result = await orchestrator.process(hello_again_request, plan_only_target)
    data = result.model_dump_json()
    assert "db.r6g" not in data
    assert "m7i" not in data


@pytest.mark.asyncio
async def test_golden_hello_again_evidence_includes_plan(
    hello_again_request: InfrastructureRequest, plan_only_target: ExecutionTarget,
    temp_store: RunStore,
):
    adapter = AwsProviderAdapter()
    orchestrator = ExecutionOrchestrator(provider_adapter=adapter, store=temp_store)
    result = await orchestrator.process(hello_again_request, plan_only_target)
    plan_items = [e for e in result.evidence if e.type.value == "ARCHITECTURE_PLAN"]
    assert len(plan_items) > 0


@pytest.mark.asyncio
async def test_policy_blocks_production_without_approval(
    hello_again_request: InfrastructureRequest, temp_store: RunStore,
):
    production_target = ExecutionTarget(
        mode=ExecutionMode.PRODUCTION, provider=Provider.AWS,
        platform=Platform.NATIVE_VM, target_type=ExecutionTargetType.AWS_PRODUCTION)
    adapter = AwsProviderAdapter()
    orchestrator = ExecutionOrchestrator(provider_adapter=adapter, store=temp_store)
    result = await orchestrator.process(hello_again_request, production_target)
    assert result.status in (InfrastructureStatus.PARTIAL, InfrastructureStatus.FAILED)


@pytest.mark.asyncio
async def test_golden_hello_again_idempotency(
    hello_again_request: InfrastructureRequest, plan_only_target: ExecutionTarget,
    temp_store: RunStore,
):
    adapter = AwsProviderAdapter()
    orchestrator = ExecutionOrchestrator(provider_adapter=adapter, store=temp_store)
    result1 = await orchestrator.process(hello_again_request, plan_only_target)
    result2 = await orchestrator.process(
        hello_again_request, plan_only_target, idempotency_key="idem-test-001")
    assert result1.status == InfrastructureStatus.SUCCESS
    assert result1.correlationId == result2.correlationId


# ---------------------------------------------------------------------------
# Phase 2A: Persistence & State Machine Tests
# ---------------------------------------------------------------------------


class TestPersistence:
    """SQLite persistence and state machine tests."""

    def test_run_creation_and_retrieval(self, temp_store: RunStore):
        temp_store.create_run("run-001", "corr-001")
        run = temp_store.get_run("run-001")
        assert run is not None
        assert run["run_id"] == "run-001"
        assert run["state"] == ExecutionState.DRAFT.value

    def test_state_transition_valid(self, temp_store: RunStore):
        temp_store.create_run("run-001", "corr-001")
        ok, msg = temp_store.transition_state("run-001", ExecutionState.NORMALIZING)
        assert ok
        run = temp_store.get_run("run-001")
        assert run["state"] == ExecutionState.NORMALIZING.value

    def test_state_transition_illegal(self, temp_store: RunStore):
        temp_store.create_run("run-001", "corr-001")
        ok, msg = temp_store.transition_state("run-001", ExecutionState.COMPLETED)
        assert not ok
        assert "Illegal" in msg

    def test_restart_survival(self, temp_store: RunStore):
        temp_store.create_run("run-001", "corr-001")
        temp_store.transition_state("run-001", ExecutionState.NORMALIZING)
        temp_store.transition_state("run-001", ExecutionState.PLANNING)
        temp_store.transition_state("run-001", ExecutionState.PLAN_READY)

        # Same store — simulates restart
        run = temp_store.get_run("run-001")
        assert run["state"] == ExecutionState.PLAN_READY.value

        transitions = temp_store.get_transitions("run-001")
        assert len(transitions) == 3

    def test_idempotency_key(self, temp_store: RunStore):
        temp_store.create_run("run-001", "corr-001", idempotency_key="idem-abc")
        existing = temp_store.get_run_by_idempotency("idem-abc")
        assert existing is not None
        assert existing["run_id"] == "run-001"

        not_found = temp_store.get_run_by_idempotency("idem-xyz")
        assert not_found is None

    def test_can_transition_helper(self, temp_store: RunStore):
        from infra_again.core.domain import can_transition
        assert can_transition(ExecutionState.DRAFT, ExecutionState.NORMALIZING)
        assert not can_transition(ExecutionState.DRAFT, ExecutionState.COMPLETED)
        assert not can_transition(ExecutionState.COMPLETED, ExecutionState.DRAFT)


class TestOwnership:
    """Resource ownership and destroy safety."""

    def test_auto_destroy_allowed(self):
        ownership = ResourceOwnership(
            managed_by="INFRA_AGAIN", created_by_run_id="run-123",
            ephemeral=True, target_scope=TargetScope.ISOLATED)
        assert ownership.is_auto_destroy_allowed("run-123") is True

    def test_auto_destroy_blocked_different_run(self):
        ownership = ResourceOwnership(
            managed_by="INFRA_AGAIN", created_by_run_id="run-other",
            ephemeral=True, target_scope=TargetScope.ISOLATED)
        assert ownership.is_auto_destroy_allowed("run-123") is False

    def test_auto_destroy_blocked_shared(self):
        ownership = ResourceOwnership(
            managed_by="INFRA_AGAIN", created_by_run_id="run-123",
            ephemeral=True, target_scope=TargetScope.SHARED)
        assert ownership.is_auto_destroy_allowed("run-123") is False

    def test_auto_destroy_blocked_not_ephemeral(self):
        ownership = ResourceOwnership(
            managed_by="INFRA_AGAIN", created_by_run_id="run-123",
            ephemeral=False, target_scope=TargetScope.ISOLATED)
        assert ownership.is_auto_destroy_allowed("run-123") is False

    def test_auto_destroy_blocked_not_managed(self):
        ownership = ResourceOwnership(
            managed_by="OTHER", created_by_run_id="run-123",
            ephemeral=True, target_scope=TargetScope.ISOLATED)
        assert ownership.is_auto_destroy_allowed("run-123") is False

    def test_store_can_auto_destroy(self, temp_store: RunStore):
        from infra_again.core.domain import OwnedResource
        temp_store.create_run("run-001", "corr-001")
        resource = OwnedResource(
            resource_id="bucket-1", resource_type="AWS::S3::Bucket",
            provider="AWS",
            ownership=ResourceOwnership(
                managed_by="INFRA_AGAIN", created_by_run_id="run-001",
                ephemeral=True, target_scope=TargetScope.ISOLATED))
        temp_store.register_resource(resource)

        can, reason = temp_store.can_auto_destroy("bucket-1", "run-001")
        assert can
        assert "AUTO" in reason

        can2, reason2 = temp_store.can_auto_destroy("bucket-1", "run-other")
        assert not can2


# ---------------------------------------------------------------------------
# SIMULATED Execution Tests (requires fakecloud)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fakecloud_probe():
    """Probe fakecloud availability truthfully."""
    adapter = AwsProviderAdapter()
    status = await adapter.probe_status()
    # fakecloud may or may not be running — just verify it returns a valid status
    assert status in (TruthStatus.READY, TruthStatus.NOT_CONFIGURED)


@pytest.mark.asyncio
async def test_simulated_apply_creates_bucket(simulated_target: ExecutionTarget, temp_store: RunStore):
    """Real S3 bucket creation against fakecloud, observe, validate."""
    import boto3

    try:
        __import__("httpx").get("http://localhost:4566/_fakecloud/health", timeout=2.0)
    except Exception:
        pytest.skip("fakecloud not running — skipping SIMULATED execution test")

    adapter = AwsProviderAdapter()
    from infra_again.core.domain import CapabilityRequirement, CapabilityCategory

    req = InfrastructureRequest(
        infrastructureRequestId="ir-sim-001",
        correlationId="e2e-simulated",
        workPackageId="wp-001",
        engineeringResultId="er-001",
        requirements=InfrastructureRequirements(providerHint=Provider.AWS),
    )

    orchestrator = ExecutionOrchestrator(provider_adapter=adapter, store=temp_store)

    plan = await adapter.plan(
        [CapabilityRequirement(
            category=CapabilityCategory.STORAGE, name="object_storage",
            properties={"bucket_name": "infra-again-test-bucket"})],
        simulated_target)

    cs = await adapter.apply(plan, simulated_target)
    assert len(cs.changes) > 0, "Should create at least one resource"
    assert cs.changes[0].action.value == "CREATE"

    observed = await adapter.observe(simulated_target)
    assert "observed" in observed
    assert "infra-again-test-bucket" in str(observed)

    desired = {"infra-again-test-bucket": {"bucket_name": "infra-again-test-bucket"}}
    validations = await adapter.validate(desired, observed)
    assert len(validations) > 0

    await adapter.destroy(simulated_target, ["infra-again-test-bucket"])
    observed_after = await adapter.observe(simulated_target, ["infra-again-test-bucket"])
    obs = observed_after.get("observed", {})
    assert "infra-again-test-bucket" not in obs


@pytest.mark.asyncio
async def test_validation_failure_detected(simulated_target: ExecutionTarget):
    """Validation must fail when desired != observed."""
    try:
        __import__("httpx").get("http://localhost:4566/_fakecloud/health", timeout=2.0)
    except Exception:
        pytest.skip("fakecloud not running — skipping validation test")

    adapter = AwsProviderAdapter()
    # Validate with a resource that doesn't exist
    desired = {"nonexistent-bucket-xyz": {"bucket_name": "nonexistent-bucket-xyz"}}
    observed = {"observed": {}}

    validations = await adapter.validate(desired, observed)
    assert len(validations) > 0
    # Should detect that the bucket doesn't exist
    assert validations[0].matches is False
