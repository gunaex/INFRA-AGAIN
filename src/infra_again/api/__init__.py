"""INFRA-AGAIN Control API — FastAPI.

Exposes the Infrastructure OS through a REST API for:
- Health, capabilities, targets
- Run management (plan, apply, reconcile)
- Architecture visualization
- Evidence retrieval
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..core.domain import (
    ExecutionMode, ExecutionState, ExecutionTarget, ExecutionTargetType,
    Platform, Provider, TruthStatus,
)
from ..core.persistence import RunStore
from ..registry import CapabilityRegistry
from ..execution.lab import all_lab_targets, get_target

app = FastAPI(title="INFRA-AGAIN Control API", version="3.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

store = RunStore()
registry = CapabilityRegistry()

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"status": "ok", "version": "3.0.0", "timestamp": datetime.now(timezone.utc).isoformat()}


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


@app.get("/api/v1/capabilities")
async def get_capabilities(
    provider: str | None = None,
    platform: str | None = None,
    verified_only: bool = False,
):
    caps = registry.get_all()
    if provider:
        caps = [c for c in caps if c.provider == provider]
    if platform:
        caps = [c for c in caps if c.platform == platform]
    if verified_only:
        caps = [c for c in caps if c.lifecycle.value == "VERIFIED"]
    return {"capabilities": [c.to_dict() for c in caps], "count": len(caps)}


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------


@app.get("/api/v1/targets")
async def get_targets():
    targets = []
    for t in all_lab_targets():
        targets.append({
            "target_type": t.target_type.value,
            "name": t.name,
            "provider": t.provider.value,
            "platform": t.platform.value,
            "mode": t.mode.value,
            "status": t.status.value,
            "fidelity": t.fidelity_notes,
            "description": t.description,
        })
    return {"targets": targets, "count": len(targets)}


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


@app.get("/api/v1/runs")
async def list_runs(correlation_id: str | None = None):
    runs = store.list_runs(correlation_id)
    return {"runs": runs, "count": len(runs)}


@app.get("/api/v1/runs/{run_id}")
async def get_run(run_id: str):
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    transitions = store.get_transitions(run_id)
    evidence = store.get_evidence(run_id)
    resources = store.get_resources_for_run(run_id)
    return {
        "run": run,
        "transitions": transitions,
        "evidence_count": len(evidence),
        "resources": resources,
    }


@app.get("/api/v1/runs/{run_id}/architecture")
async def get_run_architecture(run_id: str):
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    evidence_dir = Path(".ai/infra-runs") / run_id
    arch: dict[str, Any] = {}
    for fname in ["architecture-proposed.json", "architecture-planned.json",
                   "architecture-observed.json", "architecture-diff.json"]:
        fpath = evidence_dir / fname
        if fpath.exists():
            try:
                arch[fname.replace(".json", "").replace("architecture-", "")] = json.loads(fpath.read_text())
            except Exception:
                arch[fname] = {"error": "parse failed"}
    return {"run_id": run_id, "architecture": arch}


@app.get("/api/v1/runs/{run_id}/evidence")
async def get_run_evidence(run_id: str):
    evidence = store.get_evidence(run_id)
    return {"run_id": run_id, "evidence": evidence, "count": len(evidence)}


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


class PlanRequest(BaseModel):
    infrastructureRequestId: str
    correlationId: str
    workPackageId: str = ""
    engineeringResultId: str = ""
    provider: str = "AWS"
    platform: str = "NATIVE_VM"
    targetType: str = "FAKECLOUD"
    requirements: dict[str, Any] = {}


@app.post("/api/v1/plan")
async def create_plan(req: PlanRequest):
    from ..contracts import InfrastructureRequest, InfrastructureRequirements
    from ..execution.orchestrator import ExecutionOrchestrator
    from ..providers.aws.adapter import AwsProviderAdapter

    infra_req = InfrastructureRequest(
        infrastructureRequestId=req.infrastructureRequestId,
        correlationId=req.correlationId,
        workPackageId=req.workPackageId,
        engineeringResultId=req.engineeringResultId,
        requirements=InfrastructureRequirements(),
    )
    target = ExecutionTarget(
        mode=ExecutionMode.PLAN_ONLY,
        provider=Provider(req.provider),
        platform=Platform(req.platform),
        target_type=ExecutionTargetType(req.targetType) if req.targetType else None,
    )
    adapter = AwsProviderAdapter()
    orchestrator = ExecutionOrchestrator(provider_adapter=adapter, store=store)
    result = await orchestrator.process(infra_req, target)
    return {"result": result.model_dump(mode="json"), "run_id": orchestrator._ctx.run_id if orchestrator._ctx else ""}


@app.post("/api/v1/runs/{run_id}/apply")
async def apply_run(run_id: str):
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404)
    state = run.get("state", "")
    if state not in (ExecutionState.PLAN_READY.value, ExecutionState.WAITING_FOR_APPROVAL.value):
        raise HTTPException(status_code=400, detail=f"Cannot apply run in state {state}")
    return {"run_id": run_id, "status": "apply_requested", "state": state,
            "note": "Apply in SIMULATED/LOCAL_RUNTIME only via API in this phase"}


@app.post("/api/v1/runs/{run_id}/reconcile")
async def reconcile_run(run_id: str):
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404)
    if run.get("state") != ExecutionState.REQUIRES_RECONCILIATION.value:
        raise HTTPException(status_code=400, detail="Run is not in reconciliation state")
    return {"run_id": run_id, "status": "reconciliation_requested"}

# ===========================================================================
# Runner API (Phase 3.1)
# ===========================================================================

_runner_registry: dict[str, dict[str, Any]] = {}
_task_registry: dict[str, dict[str, Any]] = {}
_lease_registry: dict[str, dict[str, Any]] = {}
_RUNNER_AUTH_TOKEN = "runner-dev-token-change-in-production"  # nosec


def _verify_runner_auth(auth_header: str | None) -> bool:
    if not auth_header:
        return False
    return auth_header.replace("Bearer ", "") == _RUNNER_AUTH_TOKEN


class RunnerRegisterRequest(BaseModel):
    runnerId: str = ""
    name: str = ""
    version: str = ""
    os: str = ""
    arch: str = ""


@app.get("/api/v1/runners")
async def list_runners():
    return {"runners": list(_runner_registry.values()), "count": len(_runner_registry)}


@app.post("/api/v1/runners/register")
async def register_runner(req: RunnerRegisterRequest):
    rid = req.runnerId or f"runner-{len(_runner_registry)}"
    _runner_registry[rid] = {
        "runnerId": rid, "name": req.name, "version": req.version,
        "os": req.os, "arch": req.arch, "status": "ONLINE",
        "registeredAt": datetime.now(timezone.utc).isoformat(),
        "lastHeartbeat": datetime.now(timezone.utc).isoformat(),
    }
    return {"status": "registered", "runner": _runner_registry[rid]}


@app.post("/api/v1/runners/{runner_id}/heartbeat")
async def runner_heartbeat(runner_id: str, capabilities: dict[str, Any] | None = None):
    runner = _runner_registry.get(runner_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Runner not found")
    runner["lastHeartbeat"] = datetime.now(timezone.utc).isoformat()
    runner["status"] = "ONLINE"
    if capabilities:
        runner["capabilities"] = capabilities
    return {"status": "ok", "runnerId": runner_id}


class CreateTaskRequest(BaseModel):
    runId: str = ""
    correlationId: str = ""
    executionMode: str = "LOCAL_RUNTIME"
    provider: str = "ON_PREM"
    platform: str = "KUBERNETES"
    target: str = "KIND"
    action: str = "APPLY"


@app.post("/api/v1/runners/{runner_id}/tasks")
async def create_task(runner_id: str, req: CreateTaskRequest):
    from ..runner import ExecutionTask
    task = ExecutionTask(
        run_id=req.runId, correlation_id=req.correlationId,
        execution_mode=req.executionMode, provider=req.provider,
        platform=req.platform, target=req.target, action=req.action)
    _task_registry[task.task_id] = {
        "task": task.to_dict(), "state": "QUEUED", "runnerId": runner_id,
    }
    return {"task": task.to_dict(), "state": "QUEUED"}


@app.post("/api/v1/runners/{runner_id}/tasks/lease")
async def lease_task(runner_id: str):
    for tid, t in _task_registry.items():
        if t["state"] == "QUEUED":
            from ..runner import TaskLease
            now = datetime.now(timezone.utc)
            lease = TaskLease(
                task_id=tid, runner_id=runner_id,
                leased_at=now.isoformat(),
                expires_at=datetime.fromtimestamp(now.timestamp() + 3600, tz=timezone.utc).isoformat(),
            )
            t["state"] = "LEASED"
            _lease_registry[tid] = lease.to_dict()
            return {"lease": lease.to_dict(), "task": t["task"]}
    return {"status": "no_queued_tasks"}


@app.post("/api/v1/runners/{runner_id}/tasks/{task_id}/complete")
async def complete_task(runner_id: str, task_id: str, result: dict[str, Any] | None = None):
    t = _task_registry.get(task_id)
    if not t:
        raise HTTPException(status_code=404)
    if t.get("runnerId") != runner_id:
        raise HTTPException(status_code=403, detail="Not your task")
    t["state"] = "COMPLETED"
    t["result"] = result or {}
    return {"status": "completed", "taskId": task_id}


@app.post("/api/v1/runners/{runner_id}/tasks/{task_id}/fail")
async def fail_task(runner_id: str, task_id: str, error: str = ""):
    t = _task_registry.get(task_id)
    if not t:
        raise HTTPException(status_code=404)
    t["state"] = "FAILED"
    t["error"] = error
    return {"status": "failed", "taskId": task_id, "error": error}
