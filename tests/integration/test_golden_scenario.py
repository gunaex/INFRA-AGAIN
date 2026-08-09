"""
Golden Infrastructure Scenario — "hello-again"

Demonstrates the full INFRA-AGAIN pipeline:
    InfrastructureRequest → Normalize → Plan → PLAN_ONLY → Result + Evidence

This is the FIRST safe end-to-end path.
No AWS credentials required.
No real infrastructure mutation.
"""

import pytest

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
    ExecutionTarget,
    ExecutionTargetType,
    Platform,
)
from infra_again.execution.orchestrator import ExecutionOrchestrator
from infra_again.providers.aws.adapter import AwsProviderAdapter


# ---------------------------------------------------------------------------
# Golden Scenario: hello-again
# ---------------------------------------------------------------------------


@pytest.fixture
def hello_again_request() -> InfrastructureRequest:
    """The golden 'hello-again' infrastructure request.

    Intent:
        application:
          name: hello-again
          containerized: true
        object_storage:
          required: true
        database:
          engine: postgresql
          production_grade: false
        network:
          https: false
        environment:
          class: development
    """
    return InfrastructureRequest(
        infrastructureRequestId="ir-hello-again-001",
        correlationId="e2e-golden-hello-again",
        workPackageId="wp-hello-again-001",
        engineeringResultId="er-hello-again-001",
        requirements=InfrastructureRequirements(
            database=DatabaseRequirement(
                engine="postgresql",
                version="16",
            ),
            applicationRuntime=ApplicationRuntimeRequirement(
                containerized=True,
                replicas=1,
                https=False,
                port=8080,
            ),
            networking=NetworkingRequirement(
                public=False,
                httpsOnly=False,
            ),
            providerHint=Provider.AWS,
        ),
    )


@pytest.fixture
def plan_only_target() -> ExecutionTarget:
    """PLAN_ONLY execution target — no infrastructure mutation."""
    return ExecutionTarget(
        mode=ExecutionMode.PLAN_ONLY,
        provider=Provider.AWS,
        platform=Platform.NATIVE_VM,
        target_type=ExecutionTargetType.FAKECLOUD,
        fidelity_notes={
            "Execution": "PLAN_ONLY",
            "Real AWS Provisioning": "NOT_TESTED",
            "Production Readiness": "NOT_VERIFIED",
        },
    )


@pytest.mark.asyncio
async def test_golden_hello_again_plan_only(
    hello_again_request: InfrastructureRequest,
    plan_only_target: ExecutionTarget,
):
    """
    GOLDEN INFRA SCENARIO: hello-again PLAN_ONLY

    Pipeline:
        1. Receive InfrastructureRequest
        2. Normalize intent
        3. Resolve capabilities via AWS adapter
        4. Generate plan
        5. PLAN_ONLY → no execution
        6. Produce InfrastructureResult with evidence
    """
    adapter = AwsProviderAdapter()
    orchestrator = ExecutionOrchestrator(provider_adapter=adapter)

    result = await orchestrator.process(hello_again_request, plan_only_target)

    # Verify result structure
    assert isinstance(result, InfrastructureResult)
    assert result.correlationId == "e2e-golden-hello-again"
    assert result.infrastructureRequestId == "ir-hello-again-001"

    # Verify provider/platform
    assert result.provider == Provider.AWS
    assert result.platform == Platform.NATIVE_VM

    # Verify evidence produced
    assert len(result.evidence) > 0, "Evidence must be produced"

    # Verify PLAN_ONLY does not mutate infrastructure
    # (No real AWS calls were made)
    assert result.providerDetail is None or (
        result.providerDetail.resources == []
    ), "PLAN_ONLY must not create real resources"


@pytest.mark.asyncio
async def test_golden_hello_again_no_aws_skus_in_result(
    hello_again_request: InfrastructureRequest,
    plan_only_target: ExecutionTarget,
):
    """Validate that the result does not leak AWS SKUs into provider-neutral fields."""
    adapter = AwsProviderAdapter()
    orchestrator = ExecutionOrchestrator(provider_adapter=adapter)

    result = await orchestrator.process(hello_again_request, plan_only_target)

    # Serialize and check no AWS SKUs in the result
    data = result.model_dump_json()
    assert "db.r6g" not in data
    assert "m7i" not in data


@pytest.mark.asyncio
async def test_golden_hello_again_evidence_includes_plan(
    hello_again_request: InfrastructureRequest,
    plan_only_target: ExecutionTarget,
):
    """Validate evidence includes architecture plan reference."""
    adapter = AwsProviderAdapter()
    orchestrator = ExecutionOrchestrator(provider_adapter=adapter)

    result = await orchestrator.process(hello_again_request, plan_only_target)

    plan_items = [e for e in result.evidence if e.type.value == "ARCHITECTURE_PLAN"]
    assert len(plan_items) > 0, "Evidence must include architecture plan"


@pytest.mark.asyncio
async def test_policy_blocks_production_without_approval(
    hello_again_request: InfrastructureRequest,
):
    """Production execution must be blocked without explicit approval."""
    production_target = ExecutionTarget(
        mode=ExecutionMode.PRODUCTION,
        provider=Provider.AWS,
        platform=Platform.NATIVE_VM,
        target_type=ExecutionTargetType.AWS_PRODUCTION,
    )
    adapter = AwsProviderAdapter()
    orchestrator = ExecutionOrchestrator(provider_adapter=adapter)

    result = await orchestrator.process(hello_again_request, production_target)

    # Production should be blocked or require approval
    assert result.status in (InfrastructureStatus.PARTIAL, InfrastructureStatus.FAILED), \
        f"Production execution without approval should not succeed, got {result.status}"


@pytest.mark.asyncio
async def test_golden_hello_again_idempotency(
    hello_again_request: InfrastructureRequest,
    plan_only_target: ExecutionTarget,
):
    """Multiple runs with same request should produce consistent results."""
    adapter = AwsProviderAdapter()
    orchestrator = ExecutionOrchestrator(provider_adapter=adapter)

    result1 = await orchestrator.process(hello_again_request, plan_only_target)
    result2 = await orchestrator.process(hello_again_request, plan_only_target)

    # Both should succeed in PLAN_ONLY
    assert result1.status == InfrastructureStatus.SUCCESS
    assert result2.status == InfrastructureStatus.SUCCESS
    # Same correlation ID
    assert result1.correlationId == result2.correlationId
