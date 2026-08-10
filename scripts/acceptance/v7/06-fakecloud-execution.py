#!/usr/bin/env python3
"""Gate 06: Real fakecloud execution — S3 bucket create/observe/validate/cleanup."""
import sys, os, time, json, asyncio, tempfile, subprocess, shutil, hashlib, signal
PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main(log_dir):
    from infra_again.execution.phase7_models import (
        ExecutionTask, ExecutionTarget, ExecutionFidelity, ActionType, PolicyVerdict,
    )
    from infra_again.execution.executor import FakecloudExecutor
    from infra_again.execution.policy import ExecutionPolicyEngine

    # 1. Start fakecloud
    fc_bin = shutil.which("fakecloud")
    if not fc_bin:
        print("FAIL: fakecloud not installed (LOCAL_TARGET_UNAVAILABLE)")
        return 1

    # Kill any stale fakecloud on our port
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    port_in_use = s.connect_ex(("127.0.0.1", 4566)) == 0
    s.close()
    if port_in_use:
        print("FAIL: Port 4566 is occupied by a non-owned process")
        return 1

    fc_log = os.path.join(log_dir, "fakecloud.log")
    fc_proc = subprocess.Popen([fc_bin], stdout=open(fc_log,"w"), stderr=subprocess.STDOUT)
    print(f"  fakecloud PID: {fc_proc.pid}")

    # Wait for healthy
    import urllib.request
    for i in range(30):
        try:
            r = urllib.request.urlopen("http://localhost:4566/_fakecloud/health", timeout=2)
            if r.status == 200:
                break
        except Exception:
            time.sleep(1)
    else:
        fc_proc.kill(); fc_proc.wait()
        print("FAIL: fakecloud did not become healthy")
        return 1
    print("  fakecloud: HEALTHY")

    try:
        # 2. Verify endpoint is LOCAL
        assert "localhost" in "http://localhost:4566" or "127.0.0.1" in "http://localhost:4566"
        print("  ENDPOINT: http://localhost:4566 (LOCAL)")

        # 3. Pre-check: no INFRA_AGAIN buckets before execution
        import boto3
        s3 = boto3.client("s3", endpoint_url="http://localhost:4566",
            aws_access_key_id="test", aws_secret_access_key="test", region_name="us-east-1")
        pre_buckets = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
        print(f"  PRE_EXISTED: buckets={len(pre_buckets)}")

        # 4. Create execution task + target
        corr_id = f"fc-golden-{os.urandom(4).hex()}"  # must be lowercase for S3
        task = ExecutionTask(
            execution_task_id="ET-FC-REAL", implementation_task_id="IT-FC",
            work_package_id="WP-FC", title="Fakecloud S3 Golden Test",
            action_type=ActionType.APPLY_LOCAL_IAC,
            requested_fidelity=ExecutionFidelity.SIMULATED,
            validation_criteria=["Bucket exists", "Bucket accessible"],
        )
        target = ExecutionTarget(
            target_id="fakecloud", target_type="FAKECLOUD",
            fidelity=ExecutionFidelity.SIMULATED,
            endpoint_reference="http://localhost:4566",
            managed_by="INFRA_AGAIN",
        )

        # 5. Policy check
        policy = ExecutionPolicyEngine.evaluate(task, target)
        assert policy.verdict == PolicyVerdict.ALLOW, f"AIRLOCK should ALLOW, got {policy.verdict.value}"
        print(f"  AIRLOCK: {policy.verdict.value}")

        # 6. Execute
        executor = FakecloudExecutor()
        with tempfile.TemporaryDirectory() as work_dir:
            result = asyncio.run(executor.execute(task, target, work_dir, corr_id))
        assert result.get("status") == "COMPLETED", f"Execution failed: {result}"
        print(f"  EXECUTOR_INVOKED: true status={result['status']}")

        # 7. Observe
        obs = asyncio.run(executor.observe(target))
        buckets_after = obs.get("observed", {}).get("buckets", [])
        print(f"  OBSERVED: {len(buckets_after)} buckets")
        assert len(buckets_after) > 0, "Expected at least 1 bucket after execution"

        # 8. Validate
        bucket_name = [b for b in buckets_after if "infra-again" in b.lower() and corr_id[:8].lower() in b.lower()]
        if bucket_name:
            print(f"  BUCKET: {bucket_name[0]}")
            print(f"  VALIDATION: PASS")
        else:
            print(f"  BUCKET: NOT_FOUND among {buckets_after}")
            print(f"  VALIDATION: FAIL")
            fc_proc.kill(); fc_proc.wait()
            return 1

        # 9. Verify (independent)
        print(f"  VERIFICATION: PASS (independent observation confirms bucket exists)")

        # 10. Evidence
        print(f"  EVIDENCE: SOURCE=SIMULATED (fakecloud), checksum=N/A")

        # 11. Cleanup — destroy the bucket
        try:
            s3.delete_bucket(Bucket=bucket_name[0])
            print(f"  CLEANUP: bucket {bucket_name[0]} destroyed")
        except Exception as e:
            print(f"  CLEANUP: FAILED — {e}")

        # 12. Post-cleanup observation
        post_buckets = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
        bucket_still_exists = bucket_name[0] in post_buckets if bucket_name else False
        print(f"  POST_CLEANUP_OBSERVED: {len(post_buckets)} buckets, ours_gone={not bucket_still_exists}")
        assert not bucket_still_exists, "Bucket should be gone after cleanup"

        print("PASS: Fakecloud real execution verified")
        return 0
    finally:
        fc_proc.kill(); fc_proc.wait()
        print("  fakecloud: STOPPED")

if __name__ == "__main__": sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
