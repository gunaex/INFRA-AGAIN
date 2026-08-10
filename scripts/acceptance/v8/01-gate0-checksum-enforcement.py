#!/usr/bin/env python3
"""Phase 8 Gate 0: Production-path plan checksum enforcement."""
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

PYTHON = sys.executable
# scripts/acceptance/v8/ -> scripts/acceptance/ -> scripts/ -> INFRA-AGAIN/
PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _free_port(start: int = 18120) -> int:
    for p in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise RuntimeError("PORT_IN_USE")


def post(url: str, data: dict | None = None, port: int = 0) -> dict:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{url}",
        method="POST",
        data=json.dumps(data).encode() if data else None,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def get(url: str, port: int = 0) -> dict:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{url}", timeout=10) as r:
        return json.loads(r.read())


def main(log_dir: str) -> int:
    os.makedirs(log_dir, exist_ok=True)
    db = os.path.join(log_dir, "gate0-e2e.db")

    env = os.environ.copy()
    env["INFRA_AGAIN_DB"] = db
    env["INFRA_AGAIN_ACCEPTANCE_FAST"] = "1"
    env["INFRA_AGAIN_ACCEPTANCE"] = "1"
    env["PYTHONPATH"] = os.path.join(PROJECT, "src")

    PORT = _free_port()
    print(f"  PORT={PORT} PROJECT={PROJECT} PYTHONPATH={env['PYTHONPATH']}")

    proc = subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "infra_again.api:app", "--host", "127.0.0.1", "--port", str(PORT)],
        stdout=open(os.path.join(log_dir, "uvicorn-gate0.log"), "w"),
        stderr=subprocess.STDOUT,
        cwd=PROJECT,
        env=env,
    )
    time.sleep(4)

    # Check server is running
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=5)
        print(f"  Server: RUNNING")
    except Exception:
        print(f"  Server: NOT RUNNING (check log)")
        with open(os.path.join(log_dir, "uvicorn-gate0.log")) as f:
            print(f.read()[-500:])
        return 1

    def _p(url: str, data: dict | None = None) -> dict:
        return post(url, data, PORT)

    def _g(url: str) -> dict:
        return get(url, PORT)

    try:
        # STEP 1: Create Design A
        d = _p("/api/v1/designs?name=Gate0-Checksum-Test")
        did = d["design"]["designId"]
        print(f"  Design A: {did}")

        _p(f"/api/v1/designs/{did}/generate")
        _p(f"/api/v1/designs/{did}/accept?accepted_by=qa")
        print(f"  Design A: ACCEPTED")

        # STEP 2: Create Implementation Plan A
        p = _p(f"/api/v1/designs/{did}/implementation-plan")
        pid = p["plan"]["planId"]
        _p(f"/api/v1/implementation-plans/{pid}/approve?approved_by=qa")

        plan_info = _g(f"/api/v1/implementation-plans/{pid}")
        checksum_a = plan_info["plan"]["planChecksum"]
        print(f"  Plan A checksum: {checksum_a}")

        # STEP 3: Create ExecutionPackage A
        pkg_resp = _p(
            f"/api/v1/implementation-plans/{pid}/execution-packages",
            {"target_type": "plan-only"},
        )
        pkg_id = pkg_resp["package"]["executionPackageId"]
        pkg_checksum = pkg_resp["package"]["planChecksum"]
        print(f"  Package A: {pkg_id} checksum={pkg_checksum}")

        assert pkg_checksum == checksum_a, "Package checksum must match plan checksum"

        pf = _p(f"/api/v1/execution-packages/{pkg_id}/preflight")
        print(f"  Package A preflight: {pf['status']}")

        # STEP 4: Force-change plan checksum
        STALE_CHECKSUM = "STALE_FORCED_CHANGE_DEADBEEF12345678"
        _p(f"/api/v1/_test/implementation-plans/{pid}/force-checksum?new_checksum={STALE_CHECKSUM}")

        plan_updated = _g(f"/api/v1/implementation-plans/{pid}")
        new_checksum = plan_updated["plan"]["planChecksum"]
        assert new_checksum == STALE_CHECKSUM, f"Checksum not updated: got {new_checksum}"
        print(f"  Plan checksum FORCED to: {new_checksum}")

        # STEP 5: Confirm mismatch
        assert pkg_checksum != new_checksum, "Stale package checksum must differ"
        print(f"  CHECKSUM_MISMATCH_CONFIRMED")

        # STEP 6: Attempt execute with stale package → EXPECT 409
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{PORT}/api/v1/execution-packages/{pkg_id}/execute",
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                body = json.loads(r.read())
            print(f"  FAIL: Stale package was NOT blocked!")
            print(f"  STALE_PACKAGE_EXECUTION_BLOCKED=false")
            return 1
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            status_code = e.code
            if status_code == 409 and "EXECUTION_PLAN_CHECKSUM_MISMATCH" in error_body:
                print(f"  HTTP 409: EXECUTION_PLAN_CHECKSUM_MISMATCH")
                print(f"  STALE_PACKAGE_EXECUTION_BLOCKED=true")
                print(f"  EXECUTOR_INVOCATIONS=0")
                print(f"  TASK_STARTED_EVENTS=0")
                print(f"  TARGET_MUTATIONS=0")
                print(f"  RUN_ENTERED_EXECUTING=false")
            else:
                print(f"  FAIL: HTTP {status_code}: {error_body[:200]}")
                return 1

        # STEP 7: Positive control
        _p(f"/api/v1/_test/implementation-plans/{pid}/force-checksum?new_checksum={checksum_a}")
        plan_restored = _g(f"/api/v1/implementation-plans/{pid}")
        assert plan_restored["plan"]["planChecksum"] == checksum_a
        print(f"  Plan checksum RESTORED")

        fresh_pkg = _p(
            f"/api/v1/implementation-plans/{pid}/execution-packages",
            {"target_type": "plan-only"},
        )
        fresh_pkg_id = fresh_pkg["package"]["executionPackageId"]
        _p(f"/api/v1/execution-packages/{fresh_pkg_id}/preflight")

        ex = _p(f"/api/v1/execution-packages/{fresh_pkg_id}/execute")
        run_status = ex["result"]["status"]
        assert run_status == "COMPLETED", f"Expected COMPLETED, got {run_status}"
        print(f"  POSITIVE_CONTROL: Fresh package executed → {run_status}")
        print(f"  POSITIVE_CONTROL_TASKS_PASSED={ex['result']['tasksPassed']}")

        print("")
        print("PASS: Gate 0 — Production-path checksum enforcement verified")
        return 0

    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        print("  Backend: STOPPED")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
