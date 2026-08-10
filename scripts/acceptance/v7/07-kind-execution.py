#!/usr/bin/env python3
"""Gate 07: Real kind execution — namespace/deployment/service/observe/cleanup."""
import sys, os, time, json, asyncio, tempfile, subprocess, shutil
PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main(log_dir):
    from infra_again.execution.phase7_models import (
        ExecutionTask, ExecutionTarget, ExecutionFidelity, ActionType, PolicyVerdict,
    )
    from infra_again.execution.executor import KindExecutor
    from infra_again.execution.policy import ExecutionPolicyEngine

    kind_bin = shutil.which("kind")
    kubectl = shutil.which("kubectl") or "kubectl"
    if not kind_bin:
        print("FAIL: kind not installed (LOCAL_TARGET_UNAVAILABLE)")
        return 1

    cluster_name = "infra-again-acceptance-v7"
    ctx = f"kind-{cluster_name}"
    corr_id = f"kind-golden-{os.urandom(4).hex()}"

    # 1. Create/use acceptance kind cluster
    existing = subprocess.run([kind_bin, "get", "clusters"], capture_output=True, text=True)
    if cluster_name in existing.stdout:
        print(f"  Cluster '{cluster_name}' already exists — reusing")
    else:
        r = subprocess.run([kind_bin, "create", "cluster", "--name", cluster_name],
                          capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            print(f"FAIL: kind create failed\n{r.stderr}")
            return 1
        print(f"  Cluster '{cluster_name}': CREATED")

    try:
        # 2. Verify kubectl can reach cluster
        r = subprocess.run([kubectl, "--context", ctx, "cluster-info"],
                          capture_output=True, text=True, timeout=10)
        print(f"  kubectl ({ctx}): {'READY' if r.returncode==0 else 'NOT_READY'}")
        if r.returncode != 0:
            print("FAIL: kubectl cannot reach kind cluster")
            return 1

        # 3. Clean up stale namespaces
        r = subprocess.run([kubectl, "--context", ctx, "get", "ns", "-o", "json"],
                          capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            try:
                for ns in json.loads(r.stdout).get("items", []):
                    name = ns["metadata"]["name"]
                    if name.startswith("infra-again-"):
                        subprocess.run([kubectl, "--context", ctx, "delete", "ns", name, "--wait=false"],
                                      capture_output=True, timeout=10)
            except Exception:
                pass

        # 4. Policy check
        target = ExecutionTarget(target_id="kind", target_type="KIND",
            fidelity=ExecutionFidelity.LOCAL_RUNTIME, environment_name=cluster_name,
            managed_by="INFRA_AGAIN")
        task = ExecutionTask(execution_task_id="ET-KIND-REAL", implementation_task_id="IT-KIND",
            work_package_id="WP-KIND", title="Kind Deploy Golden Test",
            action_type=ActionType.DEPLOY_LOCAL_WORKLOAD,
            requested_fidelity=ExecutionFidelity.LOCAL_RUNTIME)
        policy = ExecutionPolicyEngine.evaluate(task, target)
        assert policy.verdict == PolicyVerdict.ALLOW
        print(f"  AIRLOCK: {policy.verdict.value}")

        # 5. Execute
        executor = KindExecutor()
        with tempfile.TemporaryDirectory() as work_dir:
            result = asyncio.run(executor.execute(task, target, work_dir, corr_id))
        assert result.get("status")=="COMPLETED", f"Execution failed: {result}"
        ns_name = result.get("namespace","")
        print(f"  NAMESPACE: {ns_name}")
        print(f"  EXECUTOR_INVOKED: true status={result['status']}")

        # 6. Wait for deployment readiness
        ready = 0; desired = 0
        print(f"  Waiting for deployment (up to 90s)...")
        for i in range(30):
            time.sleep(3)
            r = subprocess.run([kubectl, "--context", ctx, "get", "deployment",
                f"app-{corr_id[:8]}", "-n", ns_name, "-o", "json"],
                capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                try:
                    dep = json.loads(r.stdout)
                    ready = dep.get("status",{}).get("readyReplicas",0)
                    desired = dep.get("spec",{}).get("replicas",0)
                    if ready == desired and ready > 0:
                        break
                except json.JSONDecodeError:
                    pass
        print(f"  DEPLOYMENT: desired={desired} ready={ready}")
        print(f"  READY_REPLICAS: {ready}")
        assert ready == 2, f"Expected 2 ready replicas, got {ready} (waited {(i+1)*3}s)"

        # 7. Observe
        obs = asyncio.run(executor.observe(target))
        
        # 8. Validate service
        r = subprocess.run([kubectl, "--context", ctx, "get", "svc",
            f"svc-{corr_id[:8]}", "-n", ns_name],
            capture_output=True, text=True, timeout=10)
        svc_ok = r.returncode == 0
        print(f"  SERVICE_EXISTS: {svc_ok}")
        assert svc_ok, "Service should exist"
        print(f"  VALIDATION: PASS")
        print(f"  VERIFICATION: PASS")

        # 9. Cleanup
        subprocess.run([kubectl, "--context", ctx, "delete", "namespace", ns_name, "--wait=false"],
                      capture_output=True, timeout=30)
        print(f"  CLEANUP: namespace {ns_name} deleted")

        # 10. Post-cleanup check
        for i in range(15):
            time.sleep(2)
            r2 = subprocess.run([kubectl, "--context", ctx, "get", "namespace", ns_name],
                               capture_output=True, text=True, timeout=10)
            if r2.returncode != 0:
                break
        ns_gone = r2.returncode != 0
        print(f"  NAMESPACE_AFTER_CLEANUP: {'GONE' if ns_gone else 'STILL_EXISTS'} (waited {(i+1)*2}s)")
        assert ns_gone, f"Namespace should be gone"

        print("PASS: Kind real execution verified")
        return 0
    finally:
        print(f"  Cluster '{cluster_name}': KEPT (ownership: acceptance)")

if __name__ == "__main__": sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
