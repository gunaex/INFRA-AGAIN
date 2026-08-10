"""Phase 9.2 Promotion API — environment promotion control-plane routes."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException

from .phase9_models import (
    PromotionPackage, EnvironmentTarget, EnvironmentClassification,
    PromotionStatus, BlastRadius, validate_transition,
    create_sandbox_environment, create_controlled_real_target,
)

# In-memory store
_promotions: dict[str, PromotionPackage] = {}
_environments: dict[str, EnvironmentTarget] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def register_promotion_routes(app: FastAPI) -> None:
    """Register Phase 9.2 promotion API routes."""

    # Pre-populate environments
    sandbox = create_sandbox_environment("123456789012", "us-east-1")
    controlled_real = create_controlled_real_target("123456789012", "us-east-1")
    production = EnvironmentTarget(
        environment_id="ENV-PROD-001",
        name="INFRA-AGAIN Production",
        classification=EnvironmentClassification.PRODUCTION,
        provider="aws", account_id="123456789012", region="us-east-1",
        blast_radius=BlastRadius.CRITICAL, production=True,
    )
    _environments[sandbox.environment_id] = sandbox
    _environments[controlled_real.environment_id] = controlled_real
    _environments[production.environment_id] = production

    @app.get("/api/v1/environments")
    async def list_environments():
        return {"environments": [e.to_dict() for e in _environments.values()]}

    @app.post("/api/v1/promotions")
    async def create_promotion(body: dict[str, Any]):
        """Create a promotion package."""
        source_id = body.get("sourceEnvironmentId", "")
        target_id = body.get("targetEnvironmentId", "")
        execution_id = body.get("sourceExecutionId", "")
        plan_cs = body.get("planChecksum", "")
        pkg_cs = body.get("packageChecksum", "")
        evidence_digest = body.get("evidenceDigest", "")
        requested_by = body.get("requestedBy", "")

        source = _environments.get(source_id)
        target = _environments.get(target_id)
        if not source or not target:
            raise HTTPException(status_code=404, detail="Environment not found")

        # Validate transition
        valid, msg = validate_transition(source.classification, target.classification)
        if not valid:
            raise HTTPException(status_code=400, detail={"error": msg})

        pkg = PromotionPackage(
            source_execution_id=execution_id,
            source_plan_checksum=plan_cs,
            source_implementation_checksum=pkg_cs,
            evidence_checksum=evidence_digest,
            target_environment=target,
            created_at=_now(),
        )
        pkg.promotion_status = PromotionStatus.DRAFT

        ok, result = pkg.seal_promotion(source, target, requested_by)
        if not ok:
            raise HTTPException(status_code=400, detail={"error": result})

        _promotions[pkg.package_id] = pkg
        return {
            "promotion": {
                "packageId": pkg.package_id,
                "promotionDigest": pkg.promotion_digest,
                "status": pkg.promotion_status.value,
                "sourceEnv": source.classification.value,
                "targetEnv": target.classification.value,
                "executionId": execution_id,
                "requestedBy": requested_by,
                "createdAt": pkg.created_at,
            }
        }

    @app.get("/api/v1/promotions/{package_id}")
    async def get_promotion(package_id: str):
        pkg = _promotions.get(package_id)
        if not pkg:
            raise HTTPException(status_code=404, detail="Promotion not found")
        return {
            "promotion": {
                "packageId": pkg.package_id,
                "promotionDigest": getattr(pkg, 'promotion_digest', ''),
                "status": pkg.promotion_status.value if hasattr(pkg, 'promotion_status') else "UNKNOWN",
                "sourceEnv": pkg.source_env.classification.value if getattr(pkg, 'source_env', None) else "",
                "targetEnv": pkg.target_env.classification.value if getattr(pkg, 'target_env', None) else "",
                "executionId": pkg.source_execution_id,
                "planChecksum": pkg.source_plan_checksum,
                "packageChecksum": pkg.source_implementation_checksum,
                "evidenceDigest": pkg.evidence_checksum,
                "approvers": pkg.approvers,
                "createdAt": pkg.created_at,
            }
        }

    @app.post("/api/v1/promotions/{package_id}/approve")
    async def approve_promotion(package_id: str, approved_by: str = ""):
        pkg = _promotions.get(package_id)
        if not pkg:
            raise HTTPException(status_code=404, detail="Promotion not found")
        ok, msg = pkg.approve_promotion(approved_by)
        if not ok:
            raise HTTPException(status_code=400, detail={"error": msg})
        return {"promotionId": package_id, "status": "APPROVED", "approvedBy": approved_by}

    @app.post("/api/v1/promotions/{package_id}/reject")
    async def reject_promotion(package_id: str):
        pkg = _promotions.get(package_id)
        if not pkg:
            raise HTTPException(status_code=404, detail="Promotion not found")
        pkg.promotion_status = PromotionStatus.REJECTED
        return {"promotionId": package_id, "status": "REJECTED"}

    @app.post("/api/v1/promotions/{package_id}/consume")
    async def consume_promotion(package_id: str):
        pkg = _promotions.get(package_id)
        if not pkg:
            raise HTTPException(status_code=404, detail="Promotion not found")
        ok, msg = pkg.consume_promotion()
        if not ok:
            raise HTTPException(status_code=400, detail={"error": msg})
        return {"promotionId": package_id, "status": "CONSUMED"}

    @app.get("/api/v1/promotions/{package_id}/verify")
    async def verify_promotion(package_id: str):
        pkg = _promotions.get(package_id)
        if not pkg:
            raise HTTPException(status_code=404, detail="Promotion not found")
        ok, msg = pkg.verify_promotion_digest()
        return {"promotionId": package_id, "valid": ok, "message": msg}
