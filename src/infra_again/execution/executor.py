"""Phase 7 Executors — PlanOnly, Fakecloud, Kind."""

from __future__ import annotations

import asyncio
import json
import os
import hashlib
import time
import uuid
from pathlib import Path
from typing import Any

from .registry import ExecutionAdapter
from .phase7_models import (
    ExecutionTask, ExecutionTarget, ExecutionFidelity, ActionType,
    ExecutionEvidence, EvidenceType, SourceTruth,
)


# ===========================================================================
# PlanOnlyExecutor
# ===========================================================================

class PlanOnlyExecutor(ExecutionAdapter):
    """Generate and validate IaC without applying."""

    @property
    def supported_action_types(self) -> list[ActionType]:
        return [ActionType.GENERATE_IAC, ActionType.VALIDATE_IAC, ActionType.PLAN_IAC]

    @property
    def supported_fidelity(self) -> ExecutionFidelity:
        return ExecutionFidelity.PLAN_ONLY

    async def execute(self, task: ExecutionTask, target: ExecutionTarget,
                      work_dir: str, correlation_id: str) -> dict[str, Any]:
        """Generate HCL, validate, plan — no apply."""
        import shutil
        result: dict[str, Any] = {"status": "COMPLETED", "outputs": [], "evidence": [], "artifacts": []}

        work_path = Path(work_dir)
        work_path.mkdir(parents=True, exist_ok=True)

        tofu = shutil.which("tofu")
        if not tofu:
            return {"status": "FAILED", "reason": "tofu not installed"}

        # Generate main.tf
        main_tf = work_path / "main.tf"
        main_tf.write_text(PlanOnlyExecutor._generate_hcl(task, correlation_id))

        result["artifacts"].append(str(main_tf))

        # tofu fmt
        proc = await asyncio.create_subprocess_exec(
            tofu, "fmt", str(main_tf),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=str(work_path),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        result["outputs"].append({"command": "fmt", "exit": proc.returncode, "stdout": stdout.decode(errors="replace")})

        # tofu init
        proc = await asyncio.create_subprocess_exec(
            tofu, "init",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=str(work_path),
            env={**os.environ, "AWS_ENDPOINT_URL_S3": "http://localhost:4566"},
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        result["outputs"].append({"command": "init", "exit": proc.returncode, "stdout": stdout.decode(errors="replace")})

        # tofu validate
        proc = await asyncio.create_subprocess_exec(
            tofu, "validate",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=str(work_path),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        result["outputs"].append({"command": "validate", "exit": proc.returncode, "stdout": stdout.decode(errors="replace")})

        if proc.returncode != 0:
            result["status"] = "FAILED"
            result["error"] = stderr.decode(errors="replace")
            result["reason"] = f"tofu init failed: {stderr.decode(errors='replace')[:200]}"
            return result

        # tofu plan
        plan_file = work_path / "plan.tfplan"
        proc = await asyncio.create_subprocess_exec(
            tofu, "plan", "-out", str(plan_file),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=str(work_path),
            env={**os.environ, "AWS_ENDPOINT_URL_S3": "http://localhost:4566"},
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        plan_output = stdout.decode(errors="replace")
        result["outputs"].append({"command": "plan", "exit": proc.returncode, "stdout": plan_output})

        # Compute plan checksum
        if plan_file.exists():
            plan_checksum = hashlib.sha256(plan_file.read_bytes()).hexdigest()
            result["plan_checksum"] = plan_checksum
            result["evidence"].append({
                "evidenceId": f"EVD-{uuid.uuid4().hex[:8].upper()}",
                "evidenceType": "CONFIG_SNAPSHOT",
                "source": "GENERATED",
                "checksum": plan_checksum,
                "pathRef": str(plan_file),
            })

        result["status"] = "COMPLETED" if proc.returncode == 0 else "FAILED"
        return result

    @staticmethod
    def _generate_hcl(task: ExecutionTask, correlation_id: str) -> str:
        return f"""# INFRA-AGAIN Phase 7 — PLAN_ONLY
# Task: {task.title}
# Correlation: {correlation_id}

terraform {{
  required_version = ">= 1.0"
}}

provider "aws" {{
  region = "us-east-1"
  endpoints {{
    s3 = "http://localhost:4566"
  }}
  s3_use_path_style = true
  access_key = "test"
  secret_key = "test"
  skip_credentials_validation = true
  skip_requesting_account_id = true
}}

resource "aws_s3_bucket" "main" {{
  bucket = "infra-again-{correlation_id[:8]}-{task.execution_task_id.lower()}"
  tags = {{
    Name        = "{task.title}"
    managed_by  = "INFRA_AGAIN"
    correlation = "{correlation_id}"
  }}
}}
"""

    async def observe(self, target: ExecutionTarget, resource_ids: list[str] | None = None) -> dict[str, Any]:
        # PLAN_ONLY: observe artifacts on disk
        return {"observed": {"artifacts": "plan-only-execution"}, "observed_at": time.time()}


# ===========================================================================
# FakecloudExecutor
# ===========================================================================

class FakecloudExecutor(ExecutionAdapter):
    """Execute against local fakecloud (simulated AWS S3)."""

    @property
    def supported_action_types(self) -> list[ActionType]:
        return [ActionType.APPLY_LOCAL_IAC, ActionType.OBSERVE_RESOURCE,
                ActionType.VALIDATE_RESOURCE, ActionType.DESTROY_RUN_OWNED_RESOURCE]

    @property
    def supported_fidelity(self) -> ExecutionFidelity:
        return ExecutionFidelity.SIMULATED

    async def execute(self, task: ExecutionTask, target: ExecutionTarget,
                      work_dir: str, correlation_id: str) -> dict[str, Any]:
        """Apply local IaC to fakecloud, observe, validate."""
        import shutil
        result: dict[str, Any] = {"status": "EXECUTING", "outputs": [], "evidence": []}

        tofu = shutil.which("tofu")
        if not tofu:
            return {"status": "FAILED", "reason": "tofu not installed"}

        work_path = Path(work_dir)
        work_path.mkdir(parents=True, exist_ok=True)

        # Generate and apply
        main_tf = work_path / "main.tf"
        main_tf.write_text(FakecloudExecutor._generate_hcl(task, correlation_id))

        env = {**os.environ, "AWS_ENDPOINT_URL_S3": "http://localhost:4566"}

        # init
        proc = await asyncio.create_subprocess_exec(tofu, "init", cwd=str(work_path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env)
        await asyncio.wait_for(proc.communicate(), timeout=60)

        # apply
        proc = await asyncio.create_subprocess_exec(tofu, "apply", "-auto-approve",
            cwd=str(work_path), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        apply_output = stdout.decode(errors="replace")
        result["outputs"].append({"command": "apply", "exit": proc.returncode, "stdout": apply_output})

        if proc.returncode != 0:
            result["status"] = "FAILED"
            result["error"] = stderr.decode(errors="replace")
            return result

        result["status"] = "COMPLETED"
        return result

    @staticmethod
    def _generate_hcl(task: ExecutionTask, correlation_id: str) -> str:
        bucket_name = f"infra-again-{correlation_id[:8]}-{task.execution_task_id.lower()}"
        bucket_name = bucket_name.lower().replace("_", "-")  # S3 requires lowercase
        return f"""# INFRA-AGAIN Phase 7 — FAKECLOUD SIMULATED
terraform {{
  required_version = ">= 1.0"
}}

provider "aws" {{
  region = "us-east-1"
  endpoints {{
    s3 = "http://localhost:4566"
  }}
  s3_use_path_style = true
  access_key = "test"
  secret_key = "test"
  skip_credentials_validation = true
  skip_requesting_account_id = true
}}

resource "aws_s3_bucket" "main" {{
  bucket = "{bucket_name}"
  tags = {{
    managed_by  = "INFRA_AGAIN"
    correlation = "{correlation_id}"
  }}
}}
"""

    async def observe(self, target: ExecutionTarget, resource_ids: list[str] | None = None) -> dict[str, Any]:
        """Observe fakecloud via boto3."""
        try:
            import boto3
            s3 = boto3.client("s3", endpoint_url="http://localhost:4566",
                aws_access_key_id="test", aws_secret_access_key="test", region_name="us-east-1")
            buckets = s3.list_buckets()
            return {
                "observed": {"buckets": [b["Name"] for b in buckets.get("Buckets", [])]},
                "observed_at": time.time(),
            }
        except Exception as e:
            return {"observed": {}, "observed_at": time.time(), "error": str(e)}


# ===========================================================================
# KindExecutor
# ===========================================================================

class KindExecutor(ExecutionAdapter):
    """Execute against local kind Kubernetes cluster."""

    @property
    def supported_action_types(self) -> list[ActionType]:
        return [ActionType.CREATE_LOCAL_NAMESPACE, ActionType.DEPLOY_LOCAL_WORKLOAD,
                ActionType.OBSERVE_RESOURCE, ActionType.VALIDATE_RESOURCE,
                ActionType.DESTROY_RUN_OWNED_RESOURCE]

    @property
    def supported_fidelity(self) -> ExecutionFidelity:
        return ExecutionFidelity.LOCAL_RUNTIME

    async def execute(self, task: ExecutionTask, target: ExecutionTarget,
                      work_dir: str, correlation_id: str) -> dict[str, Any]:
        """Deploy workload to kind cluster."""
        import shutil
        result: dict[str, Any] = {"status": "EXECUTING", "outputs": [], "evidence": []}

        kubectl = shutil.which("kubectl") or "kubectl"
        # Use explicit context if available, fall back to default
        ctx = target.environment_name or ""
        ctx_args = ["--context", f"kind-{ctx}"] if ctx else []
        ns_name = f"infra-again-{correlation_id[:8]}".lower()
        deploy_name = f"app-{correlation_id[:8]}".lower()
        svc_name = f"svc-{correlation_id[:8]}".lower()

        async def _kubectl(args: list[str], stdin_data: str = "") -> tuple[int, str, str]:
            proc = await asyncio.create_subprocess_exec(
                kubectl, *args,
                stdin=asyncio.subprocess.PIPE if stdin_data else None,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(stdin_data.encode() if stdin_data else None), timeout=30)
            return proc.returncode or 0, stdout.decode(errors="replace"), stderr.decode(errors="replace")

        # Create namespace
        ns_manifest = json.dumps({
            "apiVersion": "v1", "kind": "Namespace",
            "metadata": {
                "name": ns_name,
                "labels": {"app.kubernetes.io/managed-by": "INFRA_AGAIN", "correlation": correlation_id},
            },
        })
        exit_code, stdout, stderr = await _kubectl(ctx_args + ["apply", "-f", "-"], ns_manifest)
        result["outputs"].append({"command": "apply-namespace", "exit": exit_code, "stdout": stdout})
        if exit_code != 0:
            result["status"] = "FAILED"; result["error"] = stderr; return result

        # Create deployment
        deploy_manifest = json.dumps({
            "apiVersion": "apps/v1", "kind": "Deployment",
            "metadata": {
                "name": deploy_name, "namespace": ns_name,
                "labels": {"app.kubernetes.io/managed-by": "INFRA_AGAIN", "correlation": correlation_id},
            },
            "spec": {
                "replicas": 2,
                "selector": {"matchLabels": {"app": deploy_name}},
                "template": {
                    "metadata": {"labels": {"app": deploy_name}},
                    "spec": {"containers": [{"name": "nginx", "image": "nginx:alpine", "ports": [{"containerPort": 80}]}]},
                },
            },
        })
        exit_code, stdout, stderr = await _kubectl(ctx_args + ["apply", "-f", "-"], deploy_manifest)
        result["outputs"].append({"command": "apply-deployment", "exit": exit_code, "stdout": stdout})
        if exit_code != 0:
            result["status"] = "FAILED"; result["error"] = stderr; return result

        # Create service
        svc_manifest = json.dumps({
            "apiVersion": "v1", "kind": "Service",
            "metadata": {
                "name": svc_name, "namespace": ns_name,
                "labels": {"app.kubernetes.io/managed-by": "INFRA_AGAIN", "correlation": correlation_id},
            },
            "spec": {
                "selector": {"app": deploy_name},
                "ports": [{"port": 80, "targetPort": 80}],
            },
        })
        exit_code, stdout, stderr = await _kubectl(ctx_args + ["apply", "-f", "-"], svc_manifest)
        result["outputs"].append({"command": "apply-service", "exit": exit_code, "stdout": stdout})
        if exit_code != 0:
            result["status"] = "FAILED"; result["error"] = stderr; return result

        result["status"] = "COMPLETED"
        result["namespace"] = ns_name
        return result

    async def observe(self, target: ExecutionTarget, resource_ids: list[str] | None = None) -> dict[str, Any]:
        """Observe kind cluster via kubectl."""
        import shutil
        kubectl = shutil.which("kubectl") or "kubectl"
        ctx = target.environment_name or ""
        ctx_args = ["--context", f"kind-{ctx}"] if ctx else []
        observed: dict[str, Any] = {}

        try:
            proc = await asyncio.create_subprocess_exec(
                kubectl, *ctx_args, "get", "deployments", "--all-namespaces", "-o", "json",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            if proc.returncode == 0:
                dep_data = json.loads(stdout)
                for item in dep_data.get("items", []):
                    labels = item["metadata"].get("labels", {})
                    if labels.get("app.kubernetes.io/managed-by") == "INFRA_AGAIN":
                        name = item["metadata"]["name"]
                        ns = item["metadata"]["namespace"]
                        ready = item.get("status", {}).get("readyReplicas", 0)
                        desired = item.get("spec", {}).get("replicas", 0)
                        observed[f"deploy/{ns}/{name}"] = {
                            "readyReplicas": ready, "desiredReplicas": desired,
                        }
        except Exception as e:
            observed["error"] = str(e)

        return {"observed": observed, "observed_at": time.time()}
