"""Phase 9.2.1+ Persistence — promotion, rollback, UAT, production readiness.

SQLite persistence using existing INFRA-AGAIN database conventions.
Tables: promotion_packages, rollback_plans, uat_records, production_readiness
"""

from __future__ import annotations

import json, os, sqlite3
from pathlib import Path
from typing import Any, Optional

DB_PATH = os.environ.get("INFRA_AGAIN_DB", str(Path(".ai/infra-again.db").resolve()))


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    _init(c)
    return c


def _init(c: sqlite3.Connection) -> None:
    c.executescript("""
        CREATE TABLE IF NOT EXISTS promotion_packages (
            promotion_id TEXT PRIMARY KEY,
            source_env_id TEXT, target_env_id TEXT,
            source_env_class TEXT, target_env_class TEXT,
            implementation_plan_id TEXT, execution_package_id TEXT,
            plan_checksum TEXT, package_checksum TEXT,
            source_execution_id TEXT, source_verification_id TEXT,
            source_evidence_digest TEXT,
            blast_radius TEXT, maintenance_window_id TEXT,
            rollback_plan_id TEXT, uat_id TEXT,
            requested_by TEXT, approved_by TEXT,
            status TEXT, promotion_digest TEXT,
            created_at TEXT, approved_at TEXT, consumed_at TEXT, expires_at TEXT
        );

        CREATE TABLE IF NOT EXISTS rollback_plans (
            rollback_id TEXT PRIMARY KEY,
            environment_id TEXT, promotion_id TEXT,
            implementation_plan_id TEXT, execution_package_id TEXT,
            trigger_conditions TEXT, rollback_steps TEXT, verification_steps TEXT,
            expected_recovery_state TEXT,
            owner TEXT, approved_by TEXT,
            max_duration_seconds INTEGER,
            created_at TEXT, expires_at TEXT,
            rollback_digest TEXT, status TEXT
        );

        CREATE TABLE IF NOT EXISTS uat_records (
            uat_id TEXT PRIMARY KEY,
            promotion_id TEXT, environment_id TEXT,
            scope TEXT, acceptance_criteria TEXT,
            requested_by TEXT, performed_by TEXT, approved_by TEXT,
            status TEXT, uat_evidence_digest TEXT,
            started_at TEXT, completed_at TEXT, expires_at TEXT
        );

        CREATE TABLE IF NOT EXISTS production_readiness (
            readiness_id TEXT PRIMARY KEY,
            promotion_id TEXT, environment_id TEXT,
            plan_id TEXT, package_id TEXT,
            plan_checksum TEXT, package_checksum TEXT,
            blocks TEXT, readiness_decision TEXT,
            readiness_digest TEXT,
            evaluated_at TEXT, expires_at TEXT
        );
    """)
    c.commit()


# ══════════════════════════════════════════════════════════
# Promotion persistence
# ══════════════════════════════════════════════════════════

def persist_promotion(promo: dict) -> None:
    c = _conn()
    c.execute("""INSERT OR REPLACE INTO promotion_packages VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        promo["promotionId"], promo.get("sourceEnvId",""), promo.get("targetEnvId",""),
        promo.get("sourceEnvClass",""), promo.get("targetEnvClass",""),
        promo.get("implementationPlanId",""), promo.get("executionPackageId",""),
        promo.get("planChecksum",""), promo.get("packageChecksum",""),
        promo.get("sourceExecutionId",""), promo.get("sourceVerificationId",""),
        promo.get("sourceEvidenceDigest",""),
        promo.get("blastRadius",""), promo.get("maintenanceWindowId",""),
        promo.get("rollbackPlanId",""), promo.get("uatId",""),
        promo.get("requestedBy",""), promo.get("approvedBy",""),
        promo.get("status","DRAFT"), promo.get("promotionDigest",""),
        promo.get("createdAt",""), promo.get("approvedAt",""), promo.get("consumedAt",""), promo.get("expiresAt",""),
    ))
    c.commit()
    c.close()


def load_promotion(promotion_id: str) -> Optional[dict]:
    c = _conn()
    row = c.execute("SELECT * FROM promotion_packages WHERE promotion_id=?", (promotion_id,)).fetchone()
    c.close()
    if not row:
        return None
    d = dict(row)
    return {
        "promotionId": d["promotion_id"], "sourceEnvId": d["source_env_id"], "targetEnvId": d["target_env_id"],
        "sourceEnvClass": d["source_env_class"], "targetEnvClass": d["target_env_class"],
        "implementationPlanId": d["implementation_plan_id"], "executionPackageId": d["execution_package_id"],
        "planChecksum": d["plan_checksum"], "packageChecksum": d["package_checksum"],
        "sourceExecutionId": d["source_execution_id"], "sourceVerificationId": d["source_verification_id"],
        "sourceEvidenceDigest": d["source_evidence_digest"],
        "blastRadius": d["blast_radius"], "maintenanceWindowId": d["maintenance_window_id"],
        "rollbackPlanId": d["rollback_plan_id"], "uatId": d["uat_id"],
        "requestedBy": d["requested_by"], "approvedBy": d["approved_by"],
        "status": d["status"], "promotionDigest": d["promotion_digest"],
        "createdAt": d["created_at"], "approvedAt": d["approved_at"], "consumedAt": d["consumed_at"], "expiresAt": d["expires_at"],
    }


# ══════════════════════════════════════════════════════════
# Rollback persistence
# ══════════════════════════════════════════════════════════

def persist_rollback(rb: dict) -> None:
    c = _conn()
    c.execute("""INSERT OR REPLACE INTO rollback_plans VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        rb["rollbackId"], rb.get("environmentId",""), rb.get("promotionId",""),
        rb.get("implementationPlanId",""), rb.get("executionPackageId",""),
        json.dumps(rb.get("triggerConditions",[])), json.dumps(rb.get("rollbackSteps",[])),
        json.dumps(rb.get("verificationSteps",[])), rb.get("expectedRecoveryState",""),
        rb.get("owner",""), rb.get("approvedBy",""), rb.get("maxDurationSeconds",300),
        rb.get("createdAt",""), rb.get("expiresAt",""),
        rb.get("rollbackDigest",""), rb.get("status","DRAFT"),
    ))
    c.commit()
    c.close()


def load_rollback(rollback_id: str) -> Optional[dict]:
    c = _conn()
    row = c.execute("SELECT * FROM rollback_plans WHERE rollback_id=?", (rollback_id,)).fetchone()
    c.close()
    if not row: return None
    d = dict(row)
    return {
        "rollbackId": d["rollback_id"], "environmentId": d["environment_id"], "promotionId": d["promotion_id"],
        "implementationPlanId": d["implementation_plan_id"], "executionPackageId": d["execution_package_id"],
        "triggerConditions": json.loads(d["trigger_conditions"]), "rollbackSteps": json.loads(d["rollback_steps"]),
        "verificationSteps": json.loads(d["verification_steps"]),
        "expectedRecoveryState": d["expected_recovery_state"],
        "owner": d["owner"], "approvedBy": d["approved_by"], "maxDurationSeconds": d["max_duration_seconds"],
        "createdAt": d["created_at"], "expiresAt": d["expires_at"],
        "rollbackDigest": d["rollback_digest"], "status": d["status"],
    }


# ══════════════════════════════════════════════════════════
# UAT persistence
# ══════════════════════════════════════════════════════════

def persist_uat(uat: dict) -> None:
    c = _conn()
    c.execute("""INSERT OR REPLACE INTO uat_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        uat["uatId"], uat.get("promotionId",""), uat.get("environmentId",""),
        uat.get("scope",""), uat.get("acceptanceCriteria",""),
        uat.get("requestedBy",""), uat.get("performedBy",""), uat.get("approvedBy",""),
        uat.get("status","NOT_STARTED"), uat.get("uatEvidenceDigest",""),
        uat.get("startedAt",""), uat.get("completedAt",""), uat.get("expiresAt",""),
    ))
    c.commit()
    c.close()


def load_uat(uat_id: str) -> Optional[dict]:
    c = _conn()
    row = c.execute("SELECT * FROM uat_records WHERE uat_id=?", (uat_id,)).fetchone()
    c.close()
    if not row: return None
    d = dict(row)
    return {
        "uatId": d["uat_id"], "promotionId": d["promotion_id"], "environmentId": d["environment_id"],
        "scope": d["scope"], "acceptanceCriteria": d["acceptance_criteria"],
        "requestedBy": d["requested_by"], "performedBy": d["performed_by"], "approvedBy": d["approved_by"],
        "status": d["status"], "uatEvidenceDigest": d["uat_evidence_digest"],
        "startedAt": d["started_at"], "completedAt": d["completed_at"], "expiresAt": d["expires_at"],
    }


# ══════════════════════════════════════════════════════════
# Production Readiness persistence
# ══════════════════════════════════════════════════════════

def persist_readiness(rd: dict) -> None:
    c = _conn()
    c.execute("""INSERT OR REPLACE INTO production_readiness VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (
        rd["readinessId"], rd.get("promotionId",""), rd.get("environmentId",""),
        rd.get("planId",""), rd.get("packageId",""),
        rd.get("planChecksum",""), rd.get("packageChecksum",""),
        json.dumps(rd.get("blocks",[])), rd.get("readinessDecision",""),
        rd.get("readinessDigest",""), rd.get("evaluatedAt",""), rd.get("expiresAt",""),
    ))
    c.commit()
    c.close()


def load_readiness(readiness_id: str) -> Optional[dict]:
    c = _conn()
    row = c.execute("SELECT * FROM production_readiness WHERE readiness_id=?", (readiness_id,)).fetchone()
    c.close()
    if not row: return None
    d = dict(row)
    return {
        "readinessId": d["readiness_id"], "promotionId": d["promotion_id"], "environmentId": d["environment_id"],
        "planId": d["plan_id"], "packageId": d["package_id"],
        "planChecksum": d["plan_checksum"], "packageChecksum": d["package_checksum"],
        "blocks": json.loads(d["blocks"]), "readinessDecision": d["readiness_decision"],
        "readinessDigest": d["readiness_digest"],
        "evaluatedAt": d["evaluated_at"], "expiresAt": d["expires_at"],
    }
