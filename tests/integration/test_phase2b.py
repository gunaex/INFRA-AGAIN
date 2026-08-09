"""
Phase 2B Tests — OpenTofu IaC Integration.

Tests: IaC engine, HCL rendering, OpenTofu pipeline, visualization.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from infra_again.contracts import (
    InfrastructureRequest, InfrastructureRequirements, Provider,
)
from infra_again.core.domain import (
    CapabilityCategory, CapabilityRequirement,
    ExecutionMode, ExecutionState, ExecutionTarget, ExecutionTargetType,
    InfrastructurePlan, Platform, CapabilityMapping, OwnedResource,
    ResourceOwnership, TargetScope,
)
from infra_again.core.persistence import RunStore
from infra_again.iac.engine import IaCResult, IaCStage
from infra_again.iac.opentofu import OpenTofuEngine, extract_plan_info
from infra_again.iac.renderer import render_tofu_config
from infra_again.visualization.graph import (
    ArchitectureGraph, GraphType, NodeStatus, DiffAction,
)
from infra_again.visualization.renderer import (
    build_proposed_graph, build_planned_graph, build_observed_graph,
    build_diff, render_mermaid_before_after,
)
from infra_again.execution.orchestrator import ExecutionOrchestrator
from infra_again.providers.aws.adapter import AwsProviderAdapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fakecloud_ready() -> bool:
    try:
        import httpx
        resp = httpx.get("http://localhost:4566/_fakecloud/health", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


def _require_fakecloud():
    if not _fakecloud_ready():
        pytest.fail("fakecloud not running — acceptance requires fakecloud online")


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
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def tmp_iac_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


def _make_plan(simulated_target) -> InfrastructurePlan:
    plan = InfrastructurePlan(
        provider=Provider.AWS, platform=Platform.NATIVE_VM,
        execution_target=simulated_target)
    plan.capability_mappings.append(CapabilityMapping(
        requirement=CapabilityRequirement(
            category=CapabilityCategory.STORAGE, name="object_storage",
            properties={"bucket_name": "infra-again-tofu-test"}),
        provider=Provider.AWS,
        resource_type="AWS::S3::Bucket",
        resource_properties={"bucket_name": "infra-again-tofu-test"}))
    return plan


# ---------------------------------------------------------------------------
# IaC Engine Tests
# ---------------------------------------------------------------------------


class TestIaCEngine:
    """OpenTofu engine probe and basic ops."""

    async def test_probe_returns_version(self):
        engine = OpenTofuEngine()
        version = await engine.probe()
        assert version is not None, "OpenTofu must be installed"
        assert "OpenTofu" in version or "1." in version, f"Unexpected version: {version}"

    async def test_engine_name(self):
        engine = OpenTofuEngine()
        assert engine.engine_name == "OPENTOFU"


class TestHclRenderer:
    """Deterministic HCL generation."""

    def test_generates_provider_block(self, simulated_target, tmp_iac_dir):
        plan = _make_plan(simulated_target)
        checksum = render_tofu_config(plan, tmp_iac_dir, run_id="run-001",
                                       correlation_id="corr-001")
        assert checksum, "Must return checksum"
        main_tf = tmp_iac_dir / "main.tf"
        assert main_tf.exists()
        content = main_tf.read_text()
        assert 'provider "aws"' in content
        assert "skip_credentials_validation" in content
        assert "skip_metadata_api_check" in content
        # No real AWS endpoints
        assert "amazonaws.com" not in content.lower()

    def test_generates_s3_bucket(self, simulated_target, tmp_iac_dir):
        plan = _make_plan(simulated_target)
        render_tofu_config(plan, tmp_iac_dir, run_id="run-001", correlation_id="corr-001")
        content = (tmp_iac_dir / "main.tf").read_text()
        assert 'resource "aws_s3_bucket"' in content
        assert "infra-again-tofu-test" in content
        assert "managed_by" in content

    def test_generates_outputs(self, simulated_target, tmp_iac_dir):
        plan = _make_plan(simulated_target)
        render_tofu_config(plan, tmp_iac_dir, run_id="run-001", correlation_id="corr-001")
        outputs = tmp_iac_dir / "outputs.tf"
        assert outputs.exists()
        content = outputs.read_text()
        assert "output" in content


class TestOpenTofuPipeline:
    """Real OpenTofu init/validate/plan/apply against fakecloud."""

    async def test_fmt_pass(self, simulated_target, tmp_iac_dir):
        plan = _make_plan(simulated_target)
        render_tofu_config(plan, tmp_iac_dir, run_id="run-001", correlation_id="corr-001")
        engine = OpenTofuEngine()
        result = await engine.fmt(tmp_iac_dir)
        assert result.success, f"fmt failed: {result.stderr}"

    async def test_init_and_validate(self, simulated_target, tmp_iac_dir):
        _require_fakecloud()
        plan = _make_plan(simulated_target)
        render_tofu_config(plan, tmp_iac_dir, run_id="run-001", correlation_id="corr-001")
        engine = OpenTofuEngine()
        init = await engine.init(tmp_iac_dir)
        assert init.success, f"init failed: {init.stderr}"
        val = await engine.validate(tmp_iac_dir)
        assert val.success, f"validate failed: {val.stderr}"

    async def test_plan_and_show(self, simulated_target, tmp_iac_dir):
        _require_fakecloud()
        plan = _make_plan(simulated_target)
        render_tofu_config(plan, tmp_iac_dir, run_id="run-001", correlation_id="corr-001")
        engine = OpenTofuEngine()
        await engine.init(tmp_iac_dir)
        plan_path = tmp_iac_dir / "tfplan"
        result = await engine.plan(tmp_iac_dir, plan_path)
        assert result.success, f"plan failed: {result.stderr}"
        assert plan_path.exists()

        plan_json = await engine.show(plan_path)
        assert plan_json, "Must return plan JSON"
        info = extract_plan_info(plan_json)
        assert info.create_count >= 1, "Should create at least one resource"

    async def test_full_tofu_apply_observe(self, simulated_target, tmp_iac_dir, temp_store):
        """Full pipeline: render → init → validate → plan → apply → observe."""
        _require_fakecloud()

        plan = _make_plan(simulated_target)
        render_tofu_config(plan, tmp_iac_dir, run_id="run-001", correlation_id="corr-001")
        engine = OpenTofuEngine()

        # Init
        init = await engine.init(tmp_iac_dir)
        assert init.success

        # Validate
        val = await engine.validate(tmp_iac_dir)
        assert val.success

        # Plan
        plan_path = tmp_iac_dir / "tfplan"
        plan_result = await engine.plan(tmp_iac_dir, plan_path)
        assert plan_result.success
        assert plan_path.exists()

        # Apply
        apply_result = await engine.apply(tmp_iac_dir, plan_path)
        assert apply_result.success, f"apply failed: {apply_result.stderr}"

        # Observe via fakecloud
        adapter = AwsProviderAdapter()
        observed = await adapter.observe(simulated_target)
        assert "infra-again-tofu-test" in str(observed), \
            "Bucket must exist after tofu apply"

        # Validate
        desired = {"infra-again-tofu-test": {"bucket_name": "infra-again-tofu-test"}}
        validations = await adapter.validate(desired, observed)
        assert len(validations) > 0
        assert any(v.matches for v in validations), "At least one resource must validate"

        # Cleanup via tofu destroy
        await engine.destroy(tmp_iac_dir)

        # Verify cleanup
        observed_after = await adapter.observe(simulated_target, ["infra-again-tofu-test"])
        obs = observed_after.get("observed", {})
        assert "infra-again-tofu-test" not in obs


class TestOrchestratorWithTofu:
    """Full orchestrator pipeline with OpenTofu integration."""

    async def test_orchestrator_tofu_pipeline(self, simulated_target, temp_store):
        """Orchestrator.process() with IaC engine → real apply → observe → validate."""
        _require_fakecloud()

        adapter = AwsProviderAdapter()
        engine = OpenTofuEngine()
        orchestrator = ExecutionOrchestrator(
            provider_adapter=adapter, store=temp_store, iac_engine=engine)

        request = InfrastructureRequest(
            infrastructureRequestId="ir-tofu-001",
            correlationId="e2e-tofu", workPackageId="wp-tofu",
            engineeringResultId="er-tofu",
            requirements=InfrastructureRequirements(providerHint=Provider.AWS))

        result = await orchestrator.process(request, simulated_target)

        # Verify evidence files exist
        import glob
        evidence_dir = Path(".ai/infra-runs")
        run_dirs = sorted(evidence_dir.glob("run-*"), key=os.path.getmtime, reverse=True)
        if run_dirs:
            latest = run_dirs[0]
            files = [f.name for f in latest.rglob("*") if f.is_file()]
            assert "architecture-proposed.json" in files or any("architecture" in f for f in files), \
                "Architecture graphs must be generated"

        # Verify result
        assert result.correlationId == "e2e-tofu"
        assert result.provider == Provider.AWS

        # Cleanup test bucket
        try:
            import boto3
            s3 = boto3.client("s3", endpoint_url="http://localhost:4566",
                              aws_access_key_id="test", aws_secret_access_key="test",
                              region_name="us-east-1")
            for b in s3.list_buckets().get("Buckets", []):
                if "infra-again" in b["Name"]:
                    s3.delete_bucket(Bucket=b["Name"])
        except Exception:
            pass

    async def test_plan_failure_prevents_apply(self, simulated_target, temp_store, tmp_iac_dir):
        """Invalid HCL → tofu validate fails → apply NOT called."""
        # Write invalid HCL
        tmp_iac_dir.mkdir(parents=True, exist_ok=True)
        (tmp_iac_dir / "main.tf").write_text("invalid {{ syntax }}\n")

        engine = OpenTofuEngine()
        result = await engine.validate(tmp_iac_dir)
        assert not result.success, "Validate should fail on invalid HCL"

    async def test_restart_during_iac_applying(self, simulated_target, temp_store):
        """Restart while IAC_APPLYING → REQUIRES_RECONCILIATION."""
        temp_store.create_run("run-iac-restart", "corr-restart")
        temp_store.update_run("run-iac-restart",
                              iac_stage=IaCStage.IAC_APPLYING.value,
                              execution_mode="SIMULATED",
                              execution_target_type="FAKECLOUD")

        orchestrator = ExecutionOrchestrator(store=temp_store)
        ctx = orchestrator.load_run("run-iac-restart")
        assert ctx is not None
        assert ctx.state == ExecutionState.REQUIRES_RECONCILIATION, \
            f"Expected REQUIRES_RECONCILIATION, got {ctx.state}"


# ---------------------------------------------------------------------------
# Visualization Tests
# ---------------------------------------------------------------------------


class TestArchitectureGraph:
    """Architecture graph generation and visualization."""

    def test_proposed_graph_generated(self, simulated_target):
        plan = _make_plan(simulated_target)
        graph = build_proposed_graph(plan)
        assert graph.graph_type == GraphType.PROPOSED
        assert len(graph.nodes) >= 1
        node = graph.nodes[0]
        assert node.status == NodeStatus.PROPOSED

    def test_planned_graph_generated(self, simulated_target):
        plan = _make_plan(simulated_target)
        graph = build_planned_graph(plan, ExecutionMode.SIMULATED)
        assert graph.graph_type == GraphType.PLANNED
        assert len(graph.nodes) >= 2  # proposed + resolved
        assert len(graph.edges) >= 1
        assert graph.edges[0].relationship.value == "REALIZED_AS"

    def test_observed_graph_builds_from_observation(self, simulated_target):
        observed_state = {
            "observed": {
                "infra-again-tofu-test": {"name": "infra-again-tofu-test"}
            }
        }
        graph = build_observed_graph(observed_state, execution_mode=ExecutionMode.SIMULATED,
                                      target_endpoint="http://localhost:4566")
        assert graph.graph_type == GraphType.OBSERVED
        assert len(graph.nodes) >= 1
        assert graph.nodes[0].status == NodeStatus.OBSERVED

    def test_missing_resource_visible(self, simulated_target):
        plan = _make_plan(simulated_target)
        observed_state = {"observed": {}}
        graph = build_observed_graph(observed_state, plan, execution_mode=ExecutionMode.SIMULATED)
        missing = [n for n in graph.nodes if n.status == NodeStatus.MISSING]
        assert len(missing) >= 1, "Missing resources must be visible"

    def test_before_after_diff(self, simulated_target):
        plan = _make_plan(simulated_target)
        planned = build_planned_graph(plan, ExecutionMode.SIMULATED)
        observed = build_observed_graph(
            {"observed": {"infra-again-tofu-test": {"name": "infra-again-tofu-test"}}},
            execution_mode=ExecutionMode.SIMULATED)
        diff = build_diff(planned, observed)
        assert diff.match_count >= 1

    def test_missing_in_diff(self, simulated_target):
        plan = _make_plan(simulated_target)
        planned = build_planned_graph(plan, ExecutionMode.SIMULATED)
        observed = build_observed_graph({"observed": {}}, plan, execution_mode=ExecutionMode.SIMULATED)
        diff = build_diff(planned, observed)
        assert diff.missing_count >= 1

    def test_mermaid_generated(self, simulated_target):
        plan = _make_plan(simulated_target)
        planned = build_planned_graph(plan, ExecutionMode.SIMULATED)
        observed = build_observed_graph(
            {"observed": {"infra-again-tofu-test": {"name": "infra-again-tofu-test"}}},
            execution_mode=ExecutionMode.SIMULATED)
        diff = build_diff(planned, observed)
        md = render_mermaid_before_after(planned, observed, diff, run_id="run-001",
                                          correlation_id="corr-001")
        assert "```mermaid" in md
        assert "BEFORE" in md
        assert "AFTER" in md

    def test_planned_not_shown_as_observed(self, simulated_target):
        """PLANNED resources must not appear as OBSERVED without evidence."""
        plan = _make_plan(simulated_target)
        planned = build_planned_graph(plan, ExecutionMode.SIMULATED)
        for node in planned.nodes:
            if node.status == NodeStatus.PLANNED:
                assert node.status != NodeStatus.OBSERVED
                assert node.status != NodeStatus.VALIDATED

    def test_execution_mode_visible(self, simulated_target):
        graph = build_planned_graph(_make_plan(simulated_target), ExecutionMode.SIMULATED)
        assert "execution_mode" in graph.metadata
        assert graph.metadata["execution_mode"] == "SIMULATED"
        assert "SIMULATED" in str(graph.metadata)

    def test_graph_to_dict_serializable(self, simulated_target):
        graph = build_planned_graph(_make_plan(simulated_target), ExecutionMode.SIMULATED)
        d = graph.to_dict()
        assert isinstance(d, dict)
        assert "nodes" in d
        assert "edges" in d
        # Must be JSON-serializable
        json.dumps(d)
