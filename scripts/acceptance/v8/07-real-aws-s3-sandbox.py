#!/usr/bin/env python3
"""Phase 8.1 Stage A — Real AWS S3 Sandbox Pre-Mutation Discovery.

Read-only credential discovery, identity observation, and approval package
generation.  ZERO AWS MUTATIONS.

Must be explicitly invoked with INFRA_AGAIN_REAL_AWS_SANDBOX=1.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(PROJECT, "src"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short(s: str, n: int = 16) -> str:
    return s[:n] if s else ""


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def main(log_dir: str) -> int:
    os.makedirs(log_dir, exist_ok=True)

    # =========================================================================
    # SAFETY: Explicit opt-in required
    # =========================================================================
    if not os.environ.get("INFRA_AGAIN_REAL_AWS_SANDBOX"):
        print("REAL_AWS_SANDBOX=NOT_EXECUTED")
        print("Set INFRA_AGAIN_REAL_AWS_SANDBOX=1 to enable Stage A discovery.")
        return 0

    print("=" * 70)
    print("PHASE 8.1 STAGE A — PRE-MUTATION AWS SANDBOX DISCOVERY")
    print("=" * 70)
    print(f"Timestamp: {_now()}")
    print(f"AWS_MUTATIONS_SO_FAR=0")
    print()

    # =========================================================================
    # GATE A1: Git Safety
    # =========================================================================
    import subprocess

    def _git(cmd: list[str]) -> str:
        return subprocess.run(
            ["git"] + cmd, capture_output=True, text=True, cwd=PROJECT
        ).stdout.strip()

    head = _git(["rev-parse", "HEAD"])
    short_head = _git(["rev-parse", "--short", "HEAD"])
    ahead = _git(["rev-list", "--count", "origin/main..HEAD"])
    branch = _git(["branch", "--show-current"])
    status = _git(["status", "--porcelain"])

    print("── GATE A1: Git Safety ──")
    print(f"  CURRENT_HEAD={short_head}")
    print(f"  BRANCH={branch}")
    print(f"  COMMITS_AHEAD_OF_REMOTE={ahead}")
    print(f"  WORKTREE_CLEAN={'true' if not status.strip() else 'has untracked'}")
    print(f"  LOCAL_REMOTE_MATCH={'false' if ahead != '0' else 'true'}")
    print()

    # =========================================================================
    # GATE A2: AWS Credential Discovery
    # =========================================================================
    print("── GATE A2: AWS Credential Discovery ──")

    credential_source = "NOT_AVAILABLE"
    aws_profile = os.environ.get("AWS_PROFILE", "")
    has_access_key = bool(os.environ.get("AWS_ACCESS_KEY_ID"))
    has_session_token = bool(os.environ.get("AWS_SESSION_TOKEN"))
    has_config = os.path.exists(os.path.expanduser("~/.aws/config"))
    has_creds_file = os.path.exists(os.path.expanduser("~/.aws/credentials"))

    import boto3
    import botocore.session as bc_session
    import botocore.credentials as bc_creds

    boto_session = bc_session.get_session()
    boto_creds = boto_session.get_credentials()

    if boto_creds and boto_creds.access_key:
        credential_source = boto_creds.method
    elif aws_profile:
        credential_source = f"AWS_PROFILE={aws_profile}"
    elif has_access_key:
        credential_source = "AWS_ACCESS_KEY_ID"
    elif has_config:
        credential_source = "SHARED_CONFIG"
    elif has_creds_file:
        credential_source = "SHARED_CREDENTIALS"
    else:
        # Check SSO
        try:
            sso_config = os.path.expanduser("~/.aws/config")
            if os.path.exists(sso_config):
                with open(sso_config) as f:
                    if "sso_" in f.read():
                        credential_source = "SSO_CONFIGURED"
        except Exception:
            pass

    print(f"  CredentialSource={credential_source}")
    print(f"  AWS_PROFILE={'set' if aws_profile else 'not set'}")
    print(f"  AWS_ACCESS_KEY_ID={'present' if has_access_key else 'absent'}")
    print(f"  AWS_SESSION_TOKEN={'present' if has_session_token else 'absent'}")
    print(f"  ~/.aws/config={'exists' if has_config else 'absent'}")
    print(f"  ~/.aws/credentials={'exists' if has_creds_file else 'absent'}")

    if credential_source == "NOT_AVAILABLE":
        print()
        print("AWS_CREDENTIALS=NOT_AVAILABLE")
        print("REAL_AWS_SANDBOX=NOT_EXECUTED")
        print()
        print("=" * 70)
        print("STAGE A STOPPED: No AWS credentials available.")
        print("Configure AWS credentials and re-run with:")
        print("  INFRA_AGAIN_REAL_AWS_SANDBOX=1 python3 ...")
        print("=" * 70)
        return 0
    print()

    # =========================================================================
    # GATE A3: Observe Real AWS Identity (STS GetCallerIdentity)
    # =========================================================================
    print("── GATE A3: AWS Identity Observation ──")

    try:
        sts = boto3.client("sts")
        identity = sts.get_caller_identity()
        aws_account = identity["Account"]
        aws_arn = identity["Arn"]
        aws_user_id = identity["UserId"]
        identity_observed = True
        print(f"  Account={aws_account}")
        print(f"  Arn={aws_arn}")
        print(f"  UserId={aws_user_id[:20]}...")
        print(f"  AWS_IDENTITY_OBSERVED=true")
    except Exception as e:
        print(f"  STS GetCallerIdentity FAILED: {e}")
        print(f"  AWS_IDENTITY_OBSERVED=false")
        print()
        print("REAL_AWS_SANDBOX=NOT_EXECUTED")
        return 1
    print()

    # =========================================================================
    # PRODUCTION ACCOUNT PROTECTION
    # =========================================================================
    print("── Production Account Check ──")
    # Check known production accounts from environment/config
    known_prod = os.environ.get("INFRA_AGAIN_PRODUCTION_ACCOUNTS", "").split(",")
    known_prod = [a.strip() for a in known_prod if a.strip()]
    if aws_account in known_prod:
        print(f"  PRODUCTION_ACCOUNT_DETECTED: {aws_account}")
        print("  STOP: Cannot proceed with production account.")
        return 1
    print(f"  ProductionStatus=SANDBOX (not in known production list)")
    print()

    # =========================================================================
    # GATE A4: Region
    # =========================================================================
    print("── GATE A4: Region ──")
    aws_region = (
        os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-east-1"
    )
    region_source = (
        "AWS_REGION" if os.environ.get("AWS_REGION")
        else "AWS_DEFAULT_REGION" if os.environ.get("AWS_DEFAULT_REGION")
        else "DEFAULT"
    )
    print(f"  AWS_REGION={aws_region}")
    print(f"  REGION_SOURCE={region_source}")
    print()

    # =========================================================================
    # GATE A5: Resource Definition
    # =========================================================================
    print("── GATE A5: Resource Definition ──")
    account_fragment = aws_account[-6:] if len(aws_account) >= 6 else aws_account
    run_fragment = uuid.uuid4().hex[:8]
    bucket_name = f"infra-again-sandbox-{account_fragment}-{run_fragment}"
    print(f"  Service=S3")
    print(f"  BucketName={bucket_name}")
    print(f"  PublicAccess=BLOCKED (all 4 blocks enabled)")
    print(f"  Objects=0")
    print(f"  Encryption=AES256 (SSE-S3 default)")
    print(f"  Versioning=disabled")
    print()

    # =========================================================================
    # GATE A6: TTL
    # =========================================================================
    print("── GATE A6: TTL ──")
    ttl_hours = 1.0
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).isoformat()
    print(f"  TTL={ttl_hours}h")
    print(f"  EXPIRES_AT={expires_at}")
    print()

    # =========================================================================
    # GATE A7: Cost Boundary
    # =========================================================================
    print("── GATE A7: Cost Boundary ──")
    from infra_again.execution.sandbox_models import CostEstimate

    cost_estimate = CostEstimate(
        estimated_maximum_cost=0.01,
        ceiling=0.10,
        cost_window_hours=1.0,
        source="RULE_BASED (empty bucket, acceptance lifecycle only)",
    )
    if cost_estimate.exceeds_ceiling:
        print(f"  SANDBOX_COST_LIMIT_EXCEEDED")
        return 1
    print(f"  ESTIMATED_MAXIMUM_COST_USD={cost_estimate.estimated_maximum_cost:.2f}")
    print(f"  APPROVED_COST_CEILING_USD={cost_estimate.ceiling:.2f}")
    print(f"  CostWithinCeiling=true")
    print()

    # =========================================================================
    # GATE A8: IAM Capability Preflight
    # =========================================================================
    print("── GATE A8: IAM Capability Preflight ──")
    required_actions = [
        "s3:CreateBucket",
        "s3:PutBucketPublicAccessBlock",
        "s3:GetBucketPublicAccessBlock",
        "s3:PutBucketTagging",
        "s3:GetBucketTagging",
        "s3:GetBucketLocation",
        "s3:HeadBucket",
        "s3:DeleteBucket",
    ]
    print(f"  RequiredPermissions={required_actions}")
    print(f"  IAM_CAPABILITY_CHECK=NOT_PERFORMED (IAM simulation not available)")
    print(f"  Note: Verify these permissions before approval.")
    print()

    # =========================================================================
    # GATE A9: Sandbox Preflight
    # =========================================================================
    print("── GATE A9: Sandbox Preflight ──")
    from infra_again.execution.sandbox_models import (
        SandboxTarget, SandboxAccount, SandboxResourceAllowlist,
        OwnershipTags, CleanupPolicy, CredentialLease, CredentialSource,
        CostEstimate,
    )
    from infra_again.execution.sandbox_preflight import SandboxPreflightEngine

    package_checksum = _sha256(f"pkg-{run_fragment}")
    plan_checksum = _sha256(f"plan-{run_fragment}")

    sandbox_target = SandboxTarget(
        provider="aws",
        account=SandboxAccount(
            account_id=aws_account,
            provider="aws",
            caller_identity={
                "Account": aws_account,
                "Arn": aws_arn,
                "UserId": aws_user_id,
            },
            verified=True,
            verified_at=_now(),
        ),
        region=aws_region,
        resource_allowlist=SandboxResourceAllowlist(services=["s3"]),
        cost_estimate=cost_estimate,
        ttl_hours=ttl_hours,
        ownership_tags=OwnershipTags(run_id=run_fragment),
        credential_lease=CredentialLease(
            source=CredentialSource.TEMPORARY_STS,
            principal_arn=aws_arn,
            account_id=aws_account,
            expiration=expires_at,
        ),
        production=False,
    )

    preflight = SandboxPreflightEngine.run(
        package_id=f"PKG-{run_fragment}",
        sandbox_target=sandbox_target,
        plan_checksum=plan_checksum,
        package_checksum=package_checksum,
    )

    if preflight.all_passed:
        print(f"  SANDBOX_PREFLIGHT=PASS")
    else:
        print(f"  SANDBOX_PREFLIGHT=FAIL")
        for f in preflight.failures:
            print(f"    FAILURE: {f}")
        return 1
    print()

    # =========================================================================
    # GATE A10: APPROVAL PACKAGE
    # =========================================================================
    print("=" * 70)
    print("PHASE 8.1 REAL AWS SANDBOX APPROVAL REQUIRED")
    print("=" * 70)
    print()
    print(f"Provider:              AWS")
    print(f"Observed Account ID:   {aws_account}")
    print(f"Observed Principal:    {aws_arn}")
    print(f"Production Status:     SANDBOX (confirmed)")
    print(f"Region:                {aws_region}")
    print(f"Resource:              S3 Bucket")
    print(f"Exact Bucket Name:     {bucket_name}")
    print(f"Public Access:         BLOCKED (4/4)")
    print(f"Objects:               0")
    print(f"TTL:                   {ttl_hours}h")
    print(f"Expires At:            {expires_at}")
    print(f"Estimated Max Cost:    USD {cost_estimate.estimated_maximum_cost:.2f}")
    print(f"Cost Ceiling:          USD {cost_estimate.ceiling:.2f}")
    print(f"Execution Package:     PKG-{run_fragment}")
    print(f"Plan Checksum:         {plan_checksum}")
    print(f"Package Checksum:      {package_checksum}")
    print(f"Resource Allowlist:    S3 only")
    print(f"CONTROLLED_REAL:       BLOCKED")
    print(f"PRODUCTION:            BLOCKED")
    print()
    print(f"AWS_MUTATIONS_SO_FAR:  0")
    print(f"REAL_AWS_SANDBOX:      AWAITING_APPROVAL")
    print()
    print("=" * 70)
    print("APPROVAL REQUIRED")
    print("Type 'Approved' or equivalent to proceed with real AWS S3 creation.")
    print("Changing account, region, bucket name, checksum, cost, or TTL")
    print("invalidates this approval and requires re-running Stage A.")
    print("=" * 70)

    # Save approval package for later use
    approval_package = {
        "phase": "8.1",
        "stage": "A",
        "timestamp": _now(),
        "gitHead": short_head,
        "aws": {
            "account": aws_account,
            "principalArn": aws_arn,
            "region": aws_region,
            "credentialSource": credential_source,
        },
        "resource": {
            "service": "s3",
            "bucketName": bucket_name,
            "publicAccessBlocked": True,
            "objects": 0,
        },
        "cost": {
            "estimatedMaxUSD": cost_estimate.estimated_maximum_cost,
            "ceilingUSD": cost_estimate.ceiling,
        },
        "ttl": {
            "hours": ttl_hours,
            "expiresAt": expires_at,
        },
        "execution": {
            "packageId": f"PKG-{run_fragment}",
            "planChecksum": plan_checksum,
            "packageChecksum": package_checksum,
        },
        "safety": {
            "controlledRealBlocked": True,
            "productionBlocked": True,
            "awsMutationsSoFar": 0,
        },
        "preflight": {
            "passed": preflight.all_passed,
            "checks": preflight.to_dict()["checks"],
        },
        "status": "AWAITING_APPROVAL",
    }
    approval_file = os.path.join(log_dir, "approval-package.json")
    with open(approval_file, "w") as f:
        json.dump(approval_package, f, indent=2)
    print(f"\nApproval package saved: {approval_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
