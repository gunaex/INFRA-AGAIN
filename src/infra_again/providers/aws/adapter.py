"""
AWS Provider Adapter — PLAN_ONLY implementation.

This is the FIRST executable provider adapter for INFRA-AGAIN.
It supports PLAN_ONLY mode for architecture planning without
requiring AWS credentials or real infrastructure.

Do NOT require AWS credentials.
Do NOT hardcode AWS service names into provider-neutral abstractions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...core.domain import (
    CapabilityMapping,
    CapabilityRequirement,
    ChangeSet,
    ExecutionMode,
    ExecutionTarget,
    InfrastructurePlan,
    Provider,
    TruthStatus,
    ValidationResult,
)
from ..interface import ProviderAdapter, ProviderCapability


# ---------------------------------------------------------------------------
# Known AWS capability catalog (minimal, provider-neutral map)
# ---------------------------------------------------------------------------


@dataclass
class AwsCapabilityMapping:
    """Maps provider-neutral requirements to AWS resource types."""
    requirement_key: str
    aws_service: str
    aws_resource_type: str
    notes: str


# This is a minimal, curated mapping — NOT a full cloud catalog.
# Future: replace with Dynamic Capability Registry data.
AWS_CAPABILITY_MAP: list[AwsCapabilityMapping] = [
    AwsCapabilityMapping("database", "RDS", "AWS::RDS::DBInstance",
                         "Managed relational database"),
    AwsCapabilityMapping("database", "Aurora", "AWS::RDS::DBCluster",
                         "Aurora cluster for production workloads"),
    AwsCapabilityMapping("object_storage", "S3", "AWS::S3::Bucket",
                         "Object storage"),
    AwsCapabilityMapping("container_runtime", "ECS", "AWS::ECS::Service",
                         "Container orchestration (ECS)"),
    AwsCapabilityMapping("container_runtime", "EKS", "AWS::EKS::Cluster",
                         "Managed Kubernetes (EKS)"),
    AwsCapabilityMapping("application_load_balancer", "ALB", "AWS::ElasticLoadBalancingV2::LoadBalancer",
                         "Application Load Balancer"),
    AwsCapabilityMapping("cdn", "CloudFront", "AWS::CloudFront::Distribution",
                         "Content delivery network"),
    AwsCapabilityMapping("dns", "Route53", "AWS::Route53::RecordSet",
                         "DNS management"),
    AwsCapabilityMapping("secrets", "SecretsManager", "AWS::SecretsManager::Secret",
                         "Secrets management"),
    AwsCapabilityMapping("encryption_key", "KMS", "AWS::KMS::Key",
                         "Key management"),
]


class AwsProviderAdapter(ProviderAdapter):
    """
    AWS Provider Adapter.

    Currently implements PLAN_ONLY mode.
    No real AWS credentials required.
    Does NOT execute real infrastructure changes in this implementation.
    """

    @property
    def provider(self) -> Provider:
        return Provider.AWS

    # ------------------------------------------------------------------
    # Discover
    # ------------------------------------------------------------------

    async def discover(self, target: ExecutionTarget) -> dict[str, Any]:
        """
        Discover current AWS infrastructure state.

        Returns NOT_CONFIGURED if no AWS credentials available.
        PLAN_ONLY and SIMULATED modes return empty discovery.
        """
        if target.mode in (ExecutionMode.PLAN_ONLY, ExecutionMode.SIMULATED):
            return {
                "status": TruthStatus.NOT_CONFIGURED.value,
                "resources": {},
                "note": "PLAN_ONLY/SIMULATED — no real AWS discovery",
            }
        # Real discovery would use boto3/AWS SDK here
        return {
            "status": TruthStatus.NOT_CONFIGURED.value,
            "resources": {},
            "note": "AWS credentials not configured",
        }

    # ------------------------------------------------------------------
    # Plan
    # ------------------------------------------------------------------

    async def plan(
        self,
        requirements: list[CapabilityRequirement],
        target: ExecutionTarget,
    ) -> InfrastructurePlan:
        """
        Generate an AWS infrastructure plan from provider-neutral requirements.

        Maps capabilities to AWS resource types using the capability map.
        Does NOT require AWS credentials.
        """
        plan = InfrastructurePlan(
            provider=Provider.AWS,
            platform=target.platform,
            execution_target=target,
        )

        for req in requirements:
            mapping = self._map_to_aws(req)
            if mapping:
                plan.capability_mappings.append(mapping)

        plan.risk_assessment = self._assess_risks(plan)
        return plan

    # ------------------------------------------------------------------
    # Validate Plan
    # ------------------------------------------------------------------

    async def validate_plan(self, plan: InfrastructurePlan) -> list[str]:
        """Validate plan against known AWS constraints."""
        warnings: list[str] = []

        if not plan.capability_mappings:
            warnings.append("Plan contains no capability mappings")

        if plan.provider != Provider.AWS:
            warnings.append(f"Plan provider mismatch: expected AWS, got {plan.provider}")

        return warnings

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------

    async def apply(
        self,
        plan: InfrastructurePlan,
        target: ExecutionTarget,
    ) -> ChangeSet:
        """
        Execute plan against AWS.

        SAFETY: Returns empty ChangeSet in PLAN_ONLY mode.
        Real execution requires AWS credentials + policy approval.
        """
        if target.mode == ExecutionMode.PLAN_ONLY:
            return ChangeSet(
                provider=Provider.AWS,
                platform=target.platform,
                iac_tool="OPENTOFU",
            )

        # Real apply would use OpenTofu/Terraform here
        # Gated by policy approval upstream
        return ChangeSet(
            provider=Provider.AWS,
            platform=target.platform,
            iac_tool="OPENTOFU",
        )

    # ------------------------------------------------------------------
    # Observe
    # ------------------------------------------------------------------

    async def observe(
        self,
        target: ExecutionTarget,
        resource_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Observe actual AWS infrastructure state."""
        if target.mode in (ExecutionMode.PLAN_ONLY, ExecutionMode.SIMULATED):
            return {"observed": {}, "note": "PLAN_ONLY/SIMULATED — no real observation"}
        return {"observed": {}, "status": TruthStatus.NOT_CONFIGURED.value}

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    async def validate(
        self,
        desired: dict[str, Any],
        observed: dict[str, Any],
    ) -> list[ValidationResult]:
        """Compare desired vs observed AWS state."""
        results: list[ValidationResult] = []
        for key, desired_state in desired.items():
            observed_state = observed.get(key)
            results.append(ValidationResult(
                resource_id=key,
                desired_state=desired_state if isinstance(desired_state, dict) else {},
                observed_state=observed_state if isinstance(observed_state, dict) else None,
                matches=False,
                drift_detected=False,
                drift_details="Not observed — PLAN_ONLY or no AWS connection",
            ))
        return results

    # ------------------------------------------------------------------
    # Destroy
    # ------------------------------------------------------------------

    async def destroy(
        self,
        target: ExecutionTarget,
        resource_ids: list[str] | None = None,
    ) -> ChangeSet:
        """
        Destroy AWS resources.

        BLOCKED by default — requires policy approval.
        Returns empty ChangeSet in PLAN_ONLY.
        """
        if target.mode == ExecutionMode.PLAN_ONLY:
            return ChangeSet(provider=Provider.AWS)
        # Real destroy requires AIRLOCK clearance
        return ChangeSet(provider=Provider.AWS)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    async def probe_status(self) -> TruthStatus:
        """Truthfully report AWS connection status."""
        # Check for AWS credentials/config
        import os
        if os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"):
            return TruthStatus.READY
        if os.path.exists(os.path.expanduser("~/.aws/credentials")):
            return TruthStatus.READY
        return TruthStatus.NOT_CONFIGURED

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    async def get_capabilities(self) -> list[ProviderCapability]:
        """Return currently known AWS capabilities."""
        capabilities: list[ProviderCapability] = []
        for mapping in AWS_CAPABILITY_MAP:
            capabilities.append(ProviderCapability(
                capability_id=f"aws-{mapping.aws_resource_type.lower().replace('::', '-')}",
                provider=Provider.AWS,
                resource_type=mapping.aws_resource_type,
                category=mapping.requirement_key,
                properties_schema={},
                lifecycle="CAPABILITY_MAPPED",
                provenance_url=f"https://docs.aws.amazon.com/{mapping.aws_service.lower()}",
            ))
        return capabilities

    async def map_capability(
        self,
        requirement: CapabilityRequirement,
    ) -> CapabilityMapping | None:
        """Map a provider-neutral requirement to an AWS resource."""
        mapping = self._map_to_aws(requirement)
        return mapping

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _map_to_aws(self, requirement: CapabilityRequirement) -> CapabilityMapping | None:
        """Internal: map requirement to AWS resource type."""
        for aws_map in AWS_CAPABILITY_MAP:
            if aws_map.requirement_key == requirement.name or aws_map.requirement_key in str(requirement.properties):
                return CapabilityMapping(
                    requirement=requirement,
                    provider=Provider.AWS,
                    resource_type=aws_map.aws_resource_type,
                    resource_properties=requirement.properties,
                    confidence=0.9,
                )
        return None

    def _assess_risks(self, plan: InfrastructurePlan) -> str:
        """Assess risks for the plan."""
        risks: list[str] = []
        if not plan.capability_mappings:
            risks.append("No resources mapped — plan may be incomplete")
        risks.append("PLAN_ONLY mode — no real infrastructure changes")
        return "; ".join(risks) if risks else "No significant risks identified"
