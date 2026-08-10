"""Phase 9.2-9.5 Promotion + Rollback + UAT + Production Readiness API."""

from __future__ import annotations

import hashlib, json, os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from .phase9_models import (
    PromotionPackage, EnvironmentTarget, EnvironmentClassification,
    PromotionStatus, BlastRadius, validate_transition,
    create_sandbox_environment, create_controlled_real_target,
)
from . import phase9_persistence as persist


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _digest(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]


# In-memory caches (NOT authoritative — persistence is source of truth)
_environments: dict[str, EnvironmentTarget] = {}


def register_promotion_routes(app: FastAPI) -> None:
    sandbox = create_sandbox_environment("123456789012", "us-east-1")
    cr = create_controlled_real_target("123456789012", "us-east-1")
    prod = EnvironmentTarget(environment_id="ENV-PROD-001", name="Production",
        classification=EnvironmentClassification.PRODUCTION,
        provider="aws", account_id="123456789012", region="us-east-1",
        blast_radius=BlastRadius.CRITICAL, production=True)
    for e in [sandbox, cr, prod]:
        _environments[e.environment_id] = e

    def _env(eid: str):
        e = _environments.get(eid)
        if not e: raise HTTPException(404, "Environment not found")
        return e

    @app.get("/api/v1/environments")
    async def list_environments():
        return {"environments": [e.to_dict() for e in _environments.values()]}

    # ══════════════════════════════════════════════════════
    # PROMOTIONS (Phase 9.2.1 — persistent, restart-safe)
    # ══════════════════════════════════════════════════════
    @app.post("/api/v1/promotions")
    async def create_promotion(body: dict[str, Any]):
        src = _env(body.get("sourceEnvironmentId",""))
        tgt = _env(body.get("targetEnvironmentId",""))
        valid, msg = validate_transition(src.classification, tgt.classification)
        if not valid:
            raise HTTPException(400, detail={"error": msg})

        promo_id = f"PROMO-{uuid4().hex[:8].upper()}"
        promo = {
            "promotionId": promo_id,
            "sourceEnvId": src.environment_id, "targetEnvId": tgt.environment_id,
            "sourceEnvClass": src.classification.value, "targetEnvClass": tgt.classification.value,
            "implementationPlanId": body.get("implementationPlanId",""),
            "executionPackageId": body.get("executionPackageId",""),
            "planChecksum": body.get("planChecksum",""),
            "packageChecksum": body.get("packageChecksum",""),
            "sourceExecutionId": body.get("sourceExecutionId",""),
            "sourceVerificationId": body.get("sourceVerificationId",""),
            "sourceEvidenceDigest": body.get("sourceEvidenceDigest",""),
            "blastRadius": tgt.blast_radius.value,
            "maintenanceWindowId": body.get("maintenanceWindowId",""),
            "rollbackPlanId": body.get("rollbackPlanId",""),
            "uatId": body.get("uatId",""),
            "requestedBy": body.get("requestedBy",""),
            "approvedBy": "",
            "status": "PENDING_APPROVAL",
            "promotionDigest": "",
            "createdAt": _now(), "approvedAt": "", "consumedAt": "", "expiresAt": body.get("expiresAt",""),
        }
        promo["promotionDigest"] = _digest({k: v for k, v in promo.items() if k != "promotionDigest"})
        persist.persist_promotion(promo)
        return {"promotion": promo}

    @app.get("/api/v1/promotions/{promotion_id}")
    async def get_promotion(promotion_id: str):
        p = persist.load_promotion(promotion_id)
        if not p: raise HTTPException(404, "Promotion not found")
        return {"promotion": p}

    @app.post("/api/v1/promotions/{promotion_id}/approve")
    async def approve_promotion(promotion_id: str, approved_by: str = ""):
        p = persist.load_promotion(promotion_id)
        if not p: raise HTTPException(404)
        if p["status"] != "PENDING_APPROVAL":
            raise HTTPException(400, detail={"error": f"Status is {p['status']}"})
        if p["requestedBy"] == approved_by:
            raise HTTPException(400, detail={"error": "SEPARATION_OF_DUTIES_VIOLATION"})
        p["status"] = "APPROVED"
        p["approvedBy"] = approved_by
        p["approvedAt"] = _now()
        persist.persist_promotion(p)
        return {"promotionId": promotion_id, "status": "APPROVED"}

    @app.post("/api/v1/promotions/{promotion_id}/reject")
    async def reject_promotion(promotion_id: str):
        p = persist.load_promotion(promotion_id)
        if not p: raise HTTPException(404)
        p["status"] = "REJECTED"
        persist.persist_promotion(p)
        return {"promotionId": promotion_id, "status": "REJECTED"}

    @app.post("/api/v1/promotions/{promotion_id}/consume")
    async def consume_promotion(promotion_id: str):
        p = persist.load_promotion(promotion_id)
        if not p: raise HTTPException(404)
        if p["status"] != "APPROVED":
            raise HTTPException(400, detail={"error": f"Status is {p['status']}, not APPROVED"})
        if p["status"] == "CONSUMED":
            raise HTTPException(400, detail={"error": "PROMOTION_PACKAGE_ALREADY_CONSUMED"})
        p["status"] = "CONSUMED"
        p["consumedAt"] = _now()
        persist.persist_promotion(p)
        return {"promotionId": promotion_id, "status": "CONSUMED"}

    @app.get("/api/v1/promotions/{promotion_id}/verify")
    async def verify_promotion(promotion_id: str):
        p = persist.load_promotion(promotion_id)
        if not p: raise HTTPException(404)
        current = _digest({k: v for k, v in p.items() if k != "promotionDigest"})
        valid = (current == p.get("promotionDigest",""))
        if not valid:
            p["status"] = "INVALIDATED"
            persist.persist_promotion(p)
        return {"promotionId": promotion_id, "valid": valid, "currentDigest": current}

    # ══════════════════════════════════════════════════════
    # ROLLBACK (Phase 9.3)
    # ══════════════════════════════════════════════════════
    @app.post("/api/v1/rollback-plans")
    async def create_rollback(body: dict[str, Any]):
        rb_id = f"RBP-{uuid4().hex[:8].upper()}"
        rb = {
            "rollbackId": rb_id, "environmentId": body.get("environmentId",""),
            "promotionId": body.get("promotionId",""),
            "implementationPlanId": body.get("implementationPlanId",""),
            "executionPackageId": body.get("executionPackageId",""),
            "triggerConditions": body.get("triggerConditions",[]),
            "rollbackSteps": body.get("rollbackSteps",[]),
            "verificationSteps": body.get("verificationSteps",[]),
            "expectedRecoveryState": body.get("expectedRecoveryState",""),
            "owner": body.get("owner",""), "approvedBy": "",
            "maxDurationSeconds": body.get("maxDurationSeconds",300),
            "createdAt": _now(), "expiresAt": body.get("expiresAt",""),
            "rollbackDigest": "", "status": "DRAFT",
        }
        rb["rollbackDigest"] = _digest({k: v for k, v in rb.items() if k != "rollbackDigest"})
        persist.persist_rollback(rb)
        return {"rollbackPlan": rb}

    @app.get("/api/v1/rollback-plans/{rollback_id}")
    async def get_rollback(rollback_id: str):
        rb = persist.load_rollback(rollback_id)
        if not rb: raise HTTPException(404)
        return {"rollbackPlan": rb}

    @app.post("/api/v1/rollback-plans/{rollback_id}/approve")
    async def approve_rollback(rollback_id: str, approved_by: str = ""):
        rb = persist.load_rollback(rollback_id)
        if not rb: raise HTTPException(404)
        rb["status"] = "APPROVED"
        rb["approvedBy"] = approved_by
        persist.persist_rollback(rb)
        return {"rollbackId": rollback_id, "status": "APPROVED"}

    # ══════════════════════════════════════════════════════
    # UAT (Phase 9.4)
    # ══════════════════════════════════════════════════════
    @app.post("/api/v1/uat")
    async def create_uat(body: dict[str, Any]):
        uat_id = f"UAT-{uuid4().hex[:8].upper()}"
        uat = {
            "uatId": uat_id, "promotionId": body.get("promotionId",""),
            "environmentId": body.get("environmentId",""),
            "scope": body.get("scope",""), "acceptanceCriteria": body.get("acceptanceCriteria",""),
            "requestedBy": body.get("requestedBy",""),
            "performedBy": "", "approvedBy": "",
            "status": "NOT_STARTED", "uatEvidenceDigest": "",
            "startedAt": "", "completedAt": "", "expiresAt": body.get("expiresAt",""),
        }
        persist.persist_uat(uat)
        return {"uat": uat}

    @app.get("/api/v1/uat/{uat_id}")
    async def get_uat(uat_id: str):
        u = persist.load_uat(uat_id)
        if not u: raise HTTPException(404)
        return {"uat": u}

    @app.post("/api/v1/uat/{uat_id}/pass")
    async def pass_uat(uat_id: str, performed_by: str = "", approved_by: str = ""):
        u = persist.load_uat(uat_id)
        if not u: raise HTTPException(404)
        if performed_by == approved_by:
            raise HTTPException(400, detail={"error": "SEPARATION_OF_DUTIES_VIOLATION"})
        u["status"] = "PASSED"
        u["performedBy"] = performed_by
        u["approvedBy"] = approved_by
        u["completedAt"] = _now()
        u["uatEvidenceDigest"] = _digest({"uatId": uat_id, "passedAt": _now()})
        persist.persist_uat(u)
        return {"uatId": uat_id, "status": "PASSED"}

    # ══════════════════════════════════════════════════════
    # PRODUCTION READINESS (Phase 9.5)
    # ══════════════════════════════════════════════════════
    @app.post("/api/v1/production-readiness/evaluate")
    async def evaluate_readiness(body: dict[str, Any]):
        rd_id = f"RDY-{uuid4().hex[:8].upper()}"
        blocks = []
        promo_id = body.get("promotionId","")
        uat_id = body.get("uatId","")
        rollback_id = body.get("rollbackPlanId","")

        # Check promotion
        if promo_id:
            promo = persist.load_promotion(promo_id)
            if not promo: blocks.append("PROMOTION_NOT_FOUND")
            elif promo["status"] != "APPROVED": blocks.append(f"PROMOTION_NOT_APPROVED:{promo['status']}")
        else: blocks.append("PROMOTION_REQUIRED")

        # Check UAT
        if uat_id:
            uat = persist.load_uat(uat_id)
            if not uat: blocks.append("UAT_NOT_FOUND")
            elif uat["status"] != "PASSED": blocks.append(f"UAT_NOT_PASSED:{uat['status']}")
        else: blocks.append("UAT_REQUIRED")

        # Check rollback
        if rollback_id:
            rb = persist.load_rollback(rollback_id)
            if not rb: blocks.append("ROLLBACK_NOT_FOUND")
            elif rb["status"] != "APPROVED": blocks.append(f"ROLLBACK_NOT_APPROVED:{rb['status']}")
        else: blocks.append("ROLLBACK_REQUIRED")

        # Check plan/package
        plan_cs = body.get("planChecksum","")
        pkg_cs = body.get("packageChecksum","")
        if plan_cs and pkg_cs and plan_cs != pkg_cs:
            blocks.append("CHECKSUM_MISMATCH")

        decision = "READY" if not blocks else "NOT_READY"
        rd = {
            "readinessId": rd_id, "promotionId": promo_id,
            "environmentId": body.get("environmentId",""),
            "planId": body.get("planId",""), "packageId": body.get("packageId",""),
            "planChecksum": plan_cs, "packageChecksum": pkg_cs,
            "blocks": blocks, "readinessDecision": decision,
            "readinessDigest": "", "evaluatedAt": _now(), "expiresAt": _now(),
        }
        rd["readinessDigest"] = _digest({k: v for k, v in rd.items() if k != "readinessDigest"})
        persist.persist_readiness(rd)
        # PRODUCTION remains BLOCKED regardless of readiness
        return {"readiness": rd, "PRODUCTION_EXECUTION_ALLOWED": False, "PRODUCTION": "BLOCK"}

    @app.get("/api/v1/production-readiness/{readiness_id}")
    async def get_readiness(readiness_id: str):
        rd = persist.load_readiness(readiness_id)
        if not rd: raise HTTPException(404)
        return {"readiness": rd, "PRODUCTION_EXECUTION_ALLOWED": False, "PRODUCTION": "BLOCK"}
