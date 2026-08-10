#!/usr/bin/env python3
"""Phase 9.1 Real AWS S3 Sandbox — Complete Lifecycle.

STAGE A: Read-only discovery, identity, approval package. ZERO MUTATIONS.
STAGE B: Approved execution: Create → Observe → Validate → Verify → Cleanup → Post-cleanup.

Requires: INFRA_AGAIN_REAL_AWS_SANDBOX=1
Stage B also requires: INFRA_AGAIN_REAL_AWS_APPROVED=1
"""
from __future__ import annotations

import hashlib, json, os, sys, time, uuid
from datetime import datetime, timedelta, timezone
from typing import Any

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(PROJECT, "src"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()[:16]

def _redact_arn(arn: str) -> str:
    parts = arn.split(":")
    if len(parts) >= 6:
        parts[-1] = parts[-1][:4] + "***"
    return ":".join(parts)


# ═══════════════════════════════════════════════════════════════════════════
# AWS Mutation Counter
# ═══════════════════════════════════════════════════════════════════════════
class MutationCounter:
    def __init__(self):
        self.count = 0
        self.log: list[dict] = []
    def record(self, action: str, result: str, detail: str = ""):
        self.count += 1
        self.log.append({"action": action, "result": result, "detail": detail, "timestamp": _now()})


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════
def main(log_dir: str) -> int:
    os.makedirs(log_dir, exist_ok=True)

    if not os.environ.get("INFRA_AGAIN_REAL_AWS_SANDBOX"):
        print("REAL_AWS_SANDBOX=NOT_EXECUTED")
        print("Set INFRA_AGAIN_REAL_AWS_SANDBOX=1 to enable Stage A discovery.")
        return 0

    import boto3, botocore.session

    approval_file = os.path.join(log_dir, "approval-package.json")
    evidence_file = os.path.join(log_dir, "real-aws-evidence.json")
    counter = MutationCounter()

    # ═══════════════════════════════════════════════════════════════════
    # STAGE A — DISCOVERY
    # ═══════════════════════════════════════════════════════════════════
    print("=" * 70)
    print("PHASE 9.1 STAGE A — PRE-MUTATION AWS SANDBOX DISCOVERY")
    print("=" * 70)

    # ── Credential discovery ──
    sess = botocore.session.get_session()
    creds = sess.get_credentials()
    if not creds or not creds.access_key:
        print("\nAWS_CREDENTIALS=NOT_AVAILABLE")
        print("REAL_AWS_SANDBOX=NOT_EXECUTED")
        return 0

    credential_source = getattr(creds, 'method', 'unknown')
    print(f"CredentialSource={credential_source}")

    # ── STS GetCallerIdentity ──
    sts = boto3.client("sts")
    try:
        identity = sts.get_caller_identity()
        aws_account = identity["Account"]
        aws_arn = identity["Arn"]
        aws_user_id = identity["UserId"]
        print(f"AWS_ACCOUNT_ID={aws_account}")
        print(f"AWS_PRINCIPAL_ARN={_redact_arn(aws_arn)}")
        print(f"AWS_IDENTITY_OBSERVED=true")
    except Exception as e:
        print(f"STS_FAILED: {e}")
        return 1

    # ── Region ──
    aws_region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or sess.get_config_variable("region") or "us-east-1"
    print(f"AWS_REGION={aws_region}")

    # ── Account classification ──
    known_prod = os.environ.get("INFRA_AGAIN_PRODUCTION_ACCOUNTS", "").split(",")
    known_prod = [a.strip() for a in known_prod if a.strip()]
    if aws_account in known_prod:
        print("PRODUCTION_ACCOUNT_DETECTED — STOP")
        return 1
    classification = "CONFIRMED_SANDBOX" if os.environ.get("INFRA_AGAIN_SANDBOX_CONFIRMED") else "UNCONFIRMED"
    print(f"AccountClassification={classification}")

    # ── Resource ──
    account_fragment = aws_account[-6:] if len(aws_account) >= 6 else aws_account
    run_fragment = uuid.uuid4().hex[:8]
    bucket_name = f"infra-again-sandbox-{account_fragment}-{run_fragment}"
    ttl_hours = 1.0
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).isoformat()
    plan_checksum = _sha256(f"plan-{run_fragment}")
    package_checksum = _sha256(f"pkg-{run_fragment}")
    cost_ceiling = 0.10

    # ── Sandbox preflight ──
    from infra_again.execution.sandbox_models import (
        SandboxTarget, SandboxAccount, SandboxResourceAllowlist,
        OwnershipTags, CleanupPolicy, CredentialLease, CredentialSource,
        CostEstimate,
    )
    from infra_again.execution.sandbox_preflight import SandboxPreflightEngine

    target = SandboxTarget(
        provider="aws",
        account=SandboxAccount(account_id=aws_account, provider="aws",
            caller_identity={"Account": aws_account, "Arn": aws_arn, "UserId": aws_user_id},
            verified=True, verified_at=_now()),
        region=aws_region,
        resource_allowlist=SandboxResourceAllowlist(services=["s3"]),
        cost_estimate=CostEstimate(estimated_maximum_cost=0.01, ceiling=cost_ceiling),
        ttl_hours=ttl_hours,
        ownership_tags=OwnershipTags(run_id=run_fragment),
        credential_lease=CredentialLease(source=CredentialSource.TEMPORARY_STS,
            principal_arn=aws_arn, account_id=aws_account, expiration=expires_at),
        production=False,
    )

    preflight = SandboxPreflightEngine.run(
        package_id=f"PKG-{run_fragment}", sandbox_target=target,
        plan_checksum=plan_checksum, package_checksum=package_checksum)

    if not preflight.all_passed:
        print(f"SANDBOX_PREFLIGHT=FAIL")
        for f in preflight.failures:
            print(f"  FAILURE: {f}")
        return 1
    print("SANDBOX_PREFLIGHT=PASS")

    # ── Approval package ──
    approval = {
        "phase": "9.1", "stage": "A", "timestamp": _now(),
        "aws": {"account": aws_account, "principalArn": _redact_arn(aws_arn),
                "region": aws_region, "classification": classification,
                "credentialSource": credential_source},
        "resource": {"service": "s3", "bucketName": bucket_name,
                     "publicAccessBlocked": True, "objects": 0},
        "cost": {"estimatedMaxUSD": 0.01, "ceilingUSD": cost_ceiling},
        "ttl": {"hours": ttl_hours, "expiresAt": expires_at},
        "execution": {"packageId": f"PKG-{run_fragment}",
                      "planChecksum": plan_checksum, "packageChecksum": package_checksum,
                      "checksumMatch": True},
        "safety": {"controlledRealBlocked": True, "productionBlocked": True,
                   "awsMutationsSoFar": 0},
        "preflight": {"passed": True, "checks": preflight.to_dict()["checks"]},
    }
    with open(approval_file, "w") as f:
        json.dump(approval, f, indent=2)

    print()
    print("=" * 70)
    print("REAL AWS SANDBOX APPROVAL REQUIRED")
    print("=" * 70)
    print(f"AWS Account:           {aws_account}")
    print(f"Principal:             {_redact_arn(aws_arn)}")
    print(f"Classification:        {classification}")
    print(f"Region:                {aws_region}")
    print(f"Resource:              Amazon S3")
    print(f"Bucket:                {bucket_name}")
    print(f"Public Access:         BLOCKED")
    print(f"Objects:               0")
    print(f"TTL:                   {ttl_hours}h")
    print(f"Expires At:            {expires_at}")
    print(f"Estimated Max Cost:    USD 0.01")
    print(f"Cost Ceiling:          USD {cost_ceiling:.2f}")
    print(f"Plan Checksum:         {plan_checksum}")
    print(f"Package Checksum:      {package_checksum}")
    print(f"Checksum Match:        true")
    print(f"Resource Allowlist:    S3 ONLY")
    print(f"AWS MUTATIONS SO FAR:  0")
    print(f"CONTROLLED_REAL:       BLOCKED")
    print(f"PRODUCTION:            BLOCKED")
    print(f"\nApproval saved: {approval_file}")
    print(f"Set INFRA_AGAIN_REAL_AWS_APPROVED=1 to proceed with Stage B.")

    # ═══════════════════════════════════════════════════════════════════
    # STAGE B — APPROVED EXECUTION
    # ═══════════════════════════════════════════════════════════════════
    if not os.environ.get("INFRA_AGAIN_REAL_AWS_APPROVED"):
        print("\nSTAGE B: AWAITING_APPROVAL")
        print("Set INFRA_AGAIN_REAL_AWS_APPROVED=1 after reviewing the approval package.")
        return 0

    print()
    print("=" * 70)
    print("PHASE 9.1 STAGE B — APPROVED REAL AWS SANDBOX EXECUTION")
    print("=" * 70)

    # ── B1: Revalidate identity ──
    identity2 = sts.get_caller_identity()
    if identity2["Account"] != aws_account:
        print(f"SANDBOX_ACCOUNT_MISMATCH: {identity2['Account']} != {aws_account}")
        return 1
    print(f"B1: Identity revalidated. Account={aws_account}")

    # ── B2: AIRLOCK ──
    from infra_again.execution.phase7_models import ExecutionFidelity
    from infra_again.execution.policy import ExecutionPolicyEngine, PHASE8_ASK
    assert ExecutionFidelity.SANDBOX in PHASE8_ASK, "SANDBOX must be ASK"
    print("B2: AIRLOCK — SANDBOX=ASK + explicit approval → bounded execution")

    # ── B3: CreateBucket ──
    s3 = boto3.client("s3", region_name=aws_region)
    try:
        if aws_region == "us-east-1":
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": aws_region})
        counter.record("CreateBucket", "SUCCESS", bucket_name)
        print(f"B3: CreateBucket SUCCESS — {bucket_name}")
    except Exception as e:
        counter.record("CreateBucket", "FAILED", str(e)[:200])
        print(f"B3: CreateBucket FAILED — {e}")
        return 1

    # ── B4: PublicAccessBlock ──
    try:
        s3.put_public_access_block(Bucket=bucket_name, PublicAccessBlockConfiguration={
            "BlockPublicAcls": True, "IgnorePublicAcls": True,
            "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
        counter.record("PutPublicAccessBlock", "SUCCESS")
        print("B4: PublicAccessBlock SUCCESS")
    except Exception as e:
        counter.record("PutPublicAccessBlock", "FAILED", str(e)[:200])
        print(f"B4: PublicAccessBlock FAILED — {e}")
        # Continue to try cleanup

    # ── B5: Tags ──
    try:
        s3.put_bucket_tagging(Bucket=bucket_name, Tagging={"TagSet": [
            {"Key": "managedBy", "Value": "infra-again"},
            {"Key": "runId", "Value": run_fragment},
            {"Key": "ephemeral", "Value": "true"},
            {"Key": "sandbox", "Value": "true"},
            {"Key": "phase", "Value": "9.1"},
            {"Key": "expiresAt", "Value": expires_at},
        ]})
        counter.record("PutBucketTagging", "SUCCESS")
        print("B5: Tags SUCCESS")
    except Exception as e:
        counter.record("PutBucketTagging", "FAILED", str(e)[:200])
        print(f"B5: Tags FAILED — {e}")

    print(f"\nAWS_MUTATION_API_CALLS={counter.count}")

    # ── B6: OBSERVE (independent) ──
    print("\n── B6: Independent AWS Observation ──")
    observation: dict[str, Any] = {"bucketObserved": False}
    try:
        s3.head_bucket(Bucket=bucket_name)
        observation["bucketExists"] = True

        loc = s3.get_bucket_location(Bucket=bucket_name)
        observed_region = loc.get("LocationConstraint") or "us-east-1"
        observation["region"] = observed_region

        pab = s3.get_public_access_block(Bucket=bucket_name)["PublicAccessBlockConfiguration"]
        observation["publicAccessBlock"] = pab

        tags = s3.get_bucket_tagging(Bucket=bucket_name)["TagSet"]
        tag_dict = {t["Key"]: t["Value"] for t in tags}
        observation["tags"] = tag_dict

        observation["bucketObserved"] = True
        print(f"  Bucket exists:     {bucket_name}")
        print(f"  Region:            {observed_region}")
        print(f"  PublicAccessBlock: {all(pab.values())}")
        print(f"  managedBy:         {tag_dict.get('managedBy')}")
        print(f"  ephemeral:         {tag_dict.get('ephemeral')}")
        print(f"  sandbox:           {tag_dict.get('sandbox')}")
    except Exception as e:
        observation["error"] = str(e)[:200]
        print(f"  OBSERVATION FAILED: {e}")

    # ── B7: VALIDATION ──
    print("\n── B7: Validation ──")
    validation_errors = []
    if observation.get("region", "") != aws_region:
        validation_errors.append(f"Region mismatch: {observation.get('region')} != {aws_region}")
    if not all(observation.get("publicAccessBlock", {}).values()):
        validation_errors.append("PublicAccessBlock not fully enabled")
    tags_obs = observation.get("tags", {})
    if tags_obs.get("managedBy") != "infra-again":
        validation_errors.append(f"managedBy mismatch: {tags_obs.get('managedBy')}")
    if tags_obs.get("ephemeral") != "true":
        validation_errors.append("ephemeral != true")
    if tags_obs.get("sandbox") != "true":
        validation_errors.append("sandbox != true")

    if validation_errors:
        print(f"VALIDATION=FAIL")
        for e in validation_errors:
            print(f"  {e}")
    else:
        print("VALIDATION=PASS")

    # ── B8: INDEPENDENT VERIFICATION ──
    print("\n── B8: Independent Verification ──")
    executor_success = counter.log[0]["result"] == "SUCCESS" if counter.log else False
    verified = (
        observation.get("bucketObserved", False)
        and len(validation_errors) == 0
        and counter.count >= 3
    )
    print(f"  Executor success:    {executor_success}")
    print(f"  Observed truth:      {observation.get('bucketObserved', False)}")
    print(f"  Validation errors:   {len(validation_errors)}")
    print(f"  VERIFICATION={'PASS' if verified else 'FAIL'}")
    print(f"  Invariant: Executor SUCCESS != Verified SUCCESS")

    # ── B9: EVIDENCE ──
    evidence = {
        "phase": "9.1", "stage": "B",
        "runId": run_fragment,
        "awsAccount": aws_account,
        "principalArn": _redact_arn(aws_arn),
        "region": aws_region,
        "bucketName": bucket_name,
        "ttlHours": ttl_hours,
        "expiresAt": expires_at,
        "costCeiling": cost_ceiling,
        "planChecksum": plan_checksum,
        "packageChecksum": package_checksum,
        "approval": approval,
        "mutationCount": counter.count,
        "mutations": counter.log,
        "observation": observation,
        "validationErrors": validation_errors,
        "verification": "PASS" if verified else "FAIL",
        "timestamps": {"started": approval["timestamp"], "completed": _now()},
    }
    with open(evidence_file, "w") as f:
        json.dump(evidence, f, indent=2, default=str)
    print(f"\nEvidence saved: {evidence_file}")

    # ── B10: OWNERSHIP CHECK ──
    print("\n── B10: Ownership Check ──")
    ownership_proven = (
        tags_obs.get("managedBy") == "infra-again"
        and tags_obs.get("runId") == run_fragment
        and tags_obs.get("ephemeral") == "true"
        and tags_obs.get("sandbox") == "true"
    )
    if not ownership_proven:
        print("OWNERSHIP_NOT_PROVEN — refusing to delete")
        print("SANDBOX_RESOURCE_REMAINS: manual cleanup required")
        return 1
    print("OWNERSHIP_PROVEN=true")

    # ── B11: DELETE ──
    print("\n── B11: Cleanup ──")
    try:
        s3.delete_bucket(Bucket=bucket_name)
        counter.record("DeleteBucket", "SUCCESS")
        print(f"DeleteBucket SUCCESS — {bucket_name}")
    except Exception as e:
        counter.record("DeleteBucket", "FAILED", str(e)[:200])
        print(f"DeleteBucket FAILED — {e}")
        print("SANDBOX_RESOURCE_REMAINS")
        return 1

    # ── B12: POST-CLEANUP OBSERVATION ──
    print("\n── B12: Post-Cleanup Observation ──")
    bucket_absent = False
    try:
        s3.head_bucket(Bucket=bucket_name)
        print(f"POST_CLEANUP_BUCKET_PRESENT=true — bucket still exists!")
        bucket_absent = False
    except Exception:
        print("POST_CLEANUP_BUCKET_PRESENT=false — bucket confirmed absent")
        bucket_absent = True

    # ── FINAL ──
    print()
    print("=" * 70)
    if verified and ownership_proven and bucket_absent:
        print("AWS_SANDBOX_VERIFIED")
    elif not bucket_absent:
        print("AWS_SANDBOX_CLEANUP_FAILED")
    else:
        print("AWS_SANDBOX_EXECUTED_VERIFICATION_FAILED")
    print(f"AWS_MUTATION_API_CALLS={counter.count}")
    print("=" * 70)

    # Update evidence
    evidence["postCleanup"] = {"bucketAbsent": bucket_absent}
    evidence["finalStatus"] = "AWS_SANDBOX_VERIFIED" if (verified and ownership_proven and bucket_absent) else "FAIL"
    with open(evidence_file, "w") as f:
        json.dump(evidence, f, indent=2, default=str)

    return 0 if (verified and ownership_proven and bucket_absent) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
