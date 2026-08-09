"""Dynamic Provider Intelligence — Domain Model + Catalog System.

Phase 4: DISCOVERED != SUPPORTED != SAFE_TO_EXECUTE
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


# ============================================================================
# Lifecycle
# ============================================================================


class CatalogLifecycle(str, Enum):
    DISCOVERED = "DISCOVERED"
    METADATA_COLLECTED = "METADATA_COLLECTED"
    CAPABILITY_MAPPED = "CAPABILITY_MAPPED"
    SCHEMA_VALIDATED = "SCHEMA_VALIDATED"
    EXECUTION_SUPPORT_CHECKED = "EXECUTION_SUPPORT_CHECKED"
    VERIFIED = "VERIFIED"
    SUPPORTED = "SUPPORTED"
    UNVERIFIED = "UNVERIFIED"
    UNAVAILABLE = "UNAVAILABLE"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"
    BLOCKED = "BLOCKED"


class ExecutionSupport(str, Enum):
    NONE = "NONE"
    PLAN_ONLY = "PLAN_ONLY"
    SIMULATED = "SIMULATED"
    LOCAL_RUNTIME = "LOCAL_RUNTIME"
    SANDBOX = "SANDBOX"
    CONTROLLED_REAL = "CONTROLLED_REAL"
    PRODUCTION = "PRODUCTION"
    NOT_TESTED = "NOT_TESTED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class SourceType(str, Enum):
    OFFICIAL_API = "OFFICIAL_API"
    OFFICIAL_SCHEMA = "OFFICIAL_SCHEMA"
    OFFICIAL_DOC = "OFFICIAL_DOC"
    STATIC_SEED = "STATIC_SEED"
    MANUAL_VERIFIED = "MANUAL_VERIFIED"


class CapabilityCategory(str, Enum):
    OBJECT_STORAGE = "OBJECT_STORAGE"
    RELATIONAL_DATABASE = "RELATIONAL_DATABASE"
    COMPUTE_VM = "COMPUTE_VM"
    CONTAINER_RUNTIME = "CONTAINER_RUNTIME"
    KUBERNETES = "KUBERNETES"
    LOAD_BALANCING = "LOAD_BALANCING"
    NETWORKING = "NETWORKING"
    DNS = "DNS"
    SECRETS = "SECRETS"
    MESSAGING = "MESSAGING"
    OBSERVABILITY = "OBSERVABILITY"
    IAM = "IAM"
    CACHE = "CACHE"
    SERVERLESS = "SERVERLESS"


class FreshnessStatus(str, Enum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


# ============================================================================
# Provider Service
# ============================================================================


@dataclass
class ProviderService:
    provider: str = ""
    service_id: str = ""
    display_name: str = ""
    category: str = ""
    lifecycle: CatalogLifecycle = CatalogLifecycle.DISCOVERED
    execution_support: list[str] = field(default_factory=list)
    regions: list[str] = field(default_factory=list)
    resource_types: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    source_type: SourceType = SourceType.STATIC_SEED
    source_uri: str = ""
    deprecated: bool = False
    deprecated_at: str = ""
    replaced_by: str = ""
    notes: str = ""

    @property
    def is_safe_to_execute(self) -> bool:
        return self.lifecycle in (CatalogLifecycle.VERIFIED, CatalogLifecycle.SUPPORTED)

    @property
    def is_executable(self) -> bool:
        return any(s not in ("NONE", "PLAN_ONLY", "NOT_TESTED", "NOT_IMPLEMENTED")
                   for s in self.execution_support)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider, "serviceId": self.service_id,
            "displayName": self.display_name, "category": self.category,
            "lifecycle": self.lifecycle.value,
            "executionSupport": self.execution_support,
            "regions": self.regions, "resourceTypes": self.resource_types,
            "capabilities": self.capabilities,
            "sourceType": self.source_type.value, "sourceUri": self.source_uri,
            "deprecated": self.deprecated, "deprecatedAt": self.deprecated_at,
            "replacedBy": self.replaced_by, "notes": self.notes,
            "isExecutable": self.is_executable,
            "isSafeToExecute": self.is_safe_to_execute,
        }


# ============================================================================
# Capability Mapping
# ============================================================================


@dataclass
class CapabilityMapping:
    capability: str = ""     # provider-neutral capability
    provider: str = ""
    service_id: str = ""
    resource_type: str = ""
    lifecycle: CatalogLifecycle = CatalogLifecycle.DISCOVERED
    execution_support: list[str] = field(default_factory=list)
    confidence: float = 0.0   # 0..1 based on evidence
    selection_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability, "provider": self.provider,
            "serviceId": self.service_id, "resourceType": self.resource_type,
            "lifecycle": self.lifecycle.value,
            "executionSupport": self.execution_support,
            "confidence": self.confidence,
            "selectionReason": self.selection_reason,
        }


# ============================================================================
# Catalog Snapshot
# ============================================================================


@dataclass
class CatalogSnapshot:
    snapshot_id: str = field(default_factory=lambda: f"snap-{uuid4().hex[:8]}")
    provider: str = ""
    retrieved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_version: str = "1.0"
    checksum: str = ""
    services: list[ProviderService] = field(default_factory=list)
    service_count: int = 0
    freshness: FreshnessStatus = FreshnessStatus.UNKNOWN

    def compute_checksum(self) -> str:
        data = json.dumps([s.to_dict() for s in self.services], sort_keys=True)
        self.checksum = hashlib.sha256(data.encode()).hexdigest()[:16]
        self.service_count = len(self.services)
        return self.checksum


# ============================================================================
# Catalog Diff
# ============================================================================


class DiffAction(str, Enum):
    SERVICE_ADDED = "SERVICE_ADDED"
    SERVICE_REMOVED = "SERVICE_REMOVED"
    RESOURCE_ADDED = "RESOURCE_ADDED"
    RESOURCE_REMOVED = "RESOURCE_REMOVED"
    SCHEMA_CHANGED = "SCHEMA_CHANGED"
    REGION_ADDED = "REGION_ADDED"
    REGION_REMOVED = "REGION_REMOVED"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"


@dataclass
class CatalogDiff:
    provider: str = ""
    previous_snapshot_id: str = ""
    current_snapshot_id: str = ""
    changes: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "previousSnapshotId": self.previous_snapshot_id,
            "currentSnapshotId": self.current_snapshot_id,
            "changes": self.changes,
        }


# ============================================================================
# Provider Catalog
# ============================================================================


class ProviderCatalog:
    """Central provider catalog with snapshots and capability registry."""

    def __init__(self):
        self._services: dict[str, ProviderService] = {}
        self._snapshots: list[CatalogSnapshot] = []
        self._mappings: list[CapabilityMapping] = []
        self._seed()

    def _seed(self):
        """Seed with verified AWS and GCP services."""
        now = datetime.now(timezone.utc).isoformat()
        # AWS services
        aws_services = [
            ProviderService(provider="AWS", service_id="s3", display_name="Amazon S3",
                category="OBJECT_STORAGE", lifecycle=CatalogLifecycle.VERIFIED,
                execution_support=["SIMULATED"], resource_types=["AWS::S3::Bucket"],
                capabilities=["OBJECT_STORAGE"], source_type=SourceType.MANUAL_VERIFIED,
                notes="Verified: fakecloud S3 create/observe/validate/destroy"),
            ProviderService(provider="AWS", service_id="rds", display_name="Amazon RDS",
                category="RELATIONAL_DATABASE", lifecycle=CatalogLifecycle.CAPABILITY_MAPPED,
                execution_support=["PLAN_ONLY"], resource_types=["AWS::RDS::DBInstance"],
                capabilities=["RELATIONAL_DATABASE"], source_type=SourceType.MANUAL_VERIFIED,
                notes="PLAN_ONLY only — fakecloud RDS not verified"),
            ProviderService(provider="AWS", service_id="ec2", display_name="Amazon EC2",
                category="COMPUTE_VM", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], resource_types=["AWS::EC2::Instance"],
                capabilities=["COMPUTE_VM"]),
            ProviderService(provider="AWS", service_id="eks", display_name="Amazon EKS",
                category="KUBERNETES", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["KUBERNETES"]),
            ProviderService(provider="AWS", service_id="ecs", display_name="Amazon ECS",
                category="CONTAINER_RUNTIME", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["CONTAINER_RUNTIME"]),
            ProviderService(provider="AWS", service_id="elb", display_name="Elastic Load Balancing",
                category="LOAD_BALANCING", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["LOAD_BALANCING"]),
            ProviderService(provider="AWS", service_id="route53", display_name="Route 53",
                category="DNS", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["DNS"]),
            ProviderService(provider="AWS", service_id="secretsmanager", display_name="Secrets Manager",
                category="SECRETS", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["SECRETS"]),
            ProviderService(provider="AWS", service_id="sqs", display_name="Amazon SQS",
                category="MESSAGING", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["MESSAGING"]),
            ProviderService(provider="AWS", service_id="sns", display_name="Amazon SNS",
                category="MESSAGING", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["MESSAGING"]),
            ProviderService(provider="AWS", service_id="cloudwatch", display_name="CloudWatch",
                category="OBSERVABILITY", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["OBSERVABILITY"]),
            ProviderService(provider="AWS", service_id="iam", display_name="IAM",
                category="IAM", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["IAM"]),
            ProviderService(provider="AWS", service_id="elasticache", display_name="ElastiCache",
                category="CACHE", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["CACHE"]),
            ProviderService(provider="AWS", service_id="lambda", display_name="Lambda",
                category="SERVERLESS", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["SERVERLESS"]),
        ]
        # GCP services
        gcp_services = [
            ProviderService(provider="GCP", service_id="storage", display_name="Cloud Storage",
                category="OBJECT_STORAGE", lifecycle=CatalogLifecycle.CAPABILITY_MAPPED,
                execution_support=["PLAN_ONLY"], resource_types=["google_storage_bucket"],
                capabilities=["OBJECT_STORAGE"], source_type=SourceType.STATIC_SEED,
                notes="PLAN_ONLY only — GCP execution not implemented"),
            ProviderService(provider="GCP", service_id="compute", display_name="Compute Engine",
                category="COMPUTE_VM", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["COMPUTE_VM"]),
            ProviderService(provider="GCP", service_id="cloudsql", display_name="Cloud SQL",
                category="RELATIONAL_DATABASE", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["RELATIONAL_DATABASE"]),
            ProviderService(provider="GCP", service_id="gke", display_name="GKE",
                category="KUBERNETES", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["KUBERNETES"]),
            ProviderService(provider="GCP", service_id="cloudrun", display_name="Cloud Run",
                category="CONTAINER_RUNTIME", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["CONTAINER_RUNTIME"]),
            ProviderService(provider="GCP", service_id="vpc", display_name="VPC",
                category="NETWORKING", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["NETWORKING"]),
            ProviderService(provider="GCP", service_id="loadbalancing", display_name="Cloud Load Balancing",
                category="LOAD_BALANCING", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["LOAD_BALANCING"]),
            ProviderService(provider="GCP", service_id="secretmanager", display_name="Secret Manager",
                category="SECRETS", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["SECRETS"]),
            ProviderService(provider="GCP", service_id="pubsub", display_name="Pub/Sub",
                category="MESSAGING", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["MESSAGING"]),
            ProviderService(provider="GCP", service_id="monitoring", display_name="Cloud Monitoring",
                category="OBSERVABILITY", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["OBSERVABILITY"]),
            ProviderService(provider="GCP", service_id="dns", display_name="Cloud DNS",
                category="DNS", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["DNS"]),
        ]

        for s in aws_services + gcp_services:
            self._services[f"{s.provider}:{s.service_id}"] = s

        # Create initial snapshots
        for provider in ["AWS", "GCP"]:
            svcs = [s for s in self._services.values() if s.provider == provider]
            snap = CatalogSnapshot(provider=provider, freshness=FreshnessStatus.CURRENT)
            snap.services = svcs
            snap.compute_checksum()
            self._snapshots.append(snap)

        # Seed capability mappings
        self._mappings = [
            CapabilityMapping(capability="OBJECT_STORAGE", provider="AWS", service_id="s3",
                resource_type="AWS::S3::Bucket", lifecycle=CatalogLifecycle.VERIFIED,
                execution_support=["SIMULATED"], confidence=1.0,
                selection_reason="SIMULATED execution VERIFIED via fakecloud"),
            CapabilityMapping(capability="OBJECT_STORAGE", provider="GCP", service_id="storage",
                resource_type="google_storage_bucket", lifecycle=CatalogLifecycle.CAPABILITY_MAPPED,
                execution_support=["PLAN_ONLY"], confidence=0.8,
                selection_reason="Catalog mapped, PLAN_ONLY only"),
            CapabilityMapping(capability="RELATIONAL_DATABASE", provider="AWS", service_id="rds",
                resource_type="AWS::RDS::DBInstance", lifecycle=CatalogLifecycle.CAPABILITY_MAPPED,
                execution_support=["PLAN_ONLY"], confidence=0.7,
                selection_reason="PLAN_ONLY only"),
            CapabilityMapping(capability="RELATIONAL_DATABASE", provider="GCP", service_id="cloudsql",
                resource_type="google_sql_database_instance", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], confidence=0.5),
            CapabilityMapping(capability="KUBERNETES", provider="AWS", service_id="eks",
                resource_type="AWS::EKS::Cluster", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], confidence=0.5),
            CapabilityMapping(capability="KUBERNETES", provider="GCP", service_id="gke",
                resource_type="google_container_cluster", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], confidence=0.5),
        ]

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_service(self, provider: str, service_id: str) -> ProviderService | None:
        return self._services.get(f"{provider}:{service_id}")

    def get_services(self, provider: str | None = None) -> list[ProviderService]:
        if provider:
            return [s for s in self._services.values() if s.provider == provider]
        return list(self._services.values())

    def get_mappings(self, capability: str | None = None, provider: str | None = None) -> list[CapabilityMapping]:
        results = self._mappings
        if capability:
            results = [m for m in results if m.capability == capability]
        if provider:
            results = [m for m in results if m.provider == provider]
        return results

    def get_snapshot(self, provider: str) -> CatalogSnapshot | None:
        for s in self._snapshots:
            if s.provider == provider:
                return s
        return None

    def get_snapshots(self) -> list[CatalogSnapshot]:
        return list(self._snapshots)

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    def compare(self, capability: str, execution_mode: str = "") -> list[dict[str, Any]]:
        """Compare providers for a given capability."""
        mappings = self.get_mappings(capability=capability)
        results = []
        for m in mappings:
            svc = self.get_service(m.provider, m.service_id)
            fit = "FULL" if m.confidence >= 0.8 else "PARTIAL"
            results.append({
                "provider": m.provider, "serviceId": m.service_id,
                "resourceType": m.resource_type, "fit": fit,
                "executionSupport": m.execution_support,
                "lifecycle": m.lifecycle.value, "confidence": m.confidence,
                "selectionReason": m.selection_reason,
                "service": svc.to_dict() if svc else None,
            })
        return results

    def diff_snapshots(self, provider: str, prev_id: str, curr_id: str) -> CatalogDiff:
        prev = next((s for s in self._snapshots if s.snapshot_id == prev_id), None)
        curr = next((s for s in self._snapshots if s.snapshot_id == curr_id), None)
        diff = CatalogDiff(provider=provider, previous_snapshot_id=prev_id, current_snapshot_id=curr_id)
        if prev and curr:
            prev_ids = {s.service_id for s in prev.services}
            curr_ids = {s.service_id for s in curr.services}
            for sid in curr_ids - prev_ids:
                diff.changes.append({"action": "SERVICE_ADDED", "serviceId": sid})
            for sid in prev_ids - curr_ids:
                diff.changes.append({"action": "SERVICE_REMOVED", "serviceId": sid})
        return diff


# Global instance
_provider_catalog = ProviderCatalog()


def get_catalog() -> ProviderCatalog:
    return _provider_catalog
