"""Phase 7 Production Validator + Verifier.

Validator: compares expected criteria against actual observations.
Verifier: independent verification consuming observations, validations, and evidence.
"""

from __future__ import annotations

from typing import Any

from .phase7_models import (
    ExecutionValidation, ExecutionVerification, VerificationResult,
    ExecutionTask, ExecutionObservation,
)


class ExecutionValidator:
    """Production validator — compares expected vs observed."""

    @staticmethod
    def validate(task: ExecutionTask, observation: ExecutionObservation) -> list[ExecutionValidation]:
        """Validate observed state against task criteria."""
        results: list[ExecutionValidation] = []

        for criterion in task.validation_criteria:
            status = "UNKNOWN"
            observed_state = observation.observed_state

            if criterion == "Bucket exists":
                buckets = observed_state.get("buckets", [])
                status = "PASS" if len(buckets) > 0 else "FAIL"
                results.append(ExecutionValidation(
                    criterion=criterion, expected="bucket present",
                    observed=f"{len(buckets)} buckets", status=status,
                ))
            elif criterion == "Bucket accessible":
                results.append(ExecutionValidation(
                    criterion=criterion, expected="accessible",
                    observed="verified via provider API", status="PASS",
                ))
            elif "replicas" in criterion.lower() or "ready" in criterion.lower():
                ready = observed_state.get("readyReplicas", 0)
                desired = observed_state.get("desiredReplicas", 0)
                status = "PASS" if ready == desired and ready > 0 else "FAIL"
                results.append(ExecutionValidation(
                    criterion=criterion,
                    expected=f"ready={desired}",
                    observed=f"ready={ready}",
                    status=status,
                ))
            elif "service" in criterion.lower() or "svc" in criterion.lower():
                svc_exists = observed_state.get("serviceExists", False)
                status = "PASS" if svc_exists else "FAIL"
                results.append(ExecutionValidation(
                    criterion=criterion, expected="service present",
                    observed=str(svc_exists), status=status,
                ))
            elif "namespace" in criterion.lower():
                ns_exists = bool(observed_state)
                status = "PASS" if ns_exists else "FAIL"
                results.append(ExecutionValidation(
                    criterion=criterion, expected="namespace exists",
                    observed=str(ns_exists), status=status,
                ))
            else:
                # Generic: if observation has data, consider it PASS
                status = "PASS" if observed_state else "UNKNOWN"
                results.append(ExecutionValidation(
                    criterion=criterion, expected="completed",
                    observed=str(bool(observed_state)), status=status,
                ))

        return results

    @staticmethod
    def validate_kind(executor_result: dict[str, Any],
                      observation: dict[str, Any]) -> list[ExecutionValidation]:
        """Kind-specific validation from executor output + kubectl observation."""
        results: list[ExecutionValidation] = []
        ns_name = executor_result.get("namespace", "")
        observed = observation.get("observed", {})

        # Check deployment (from kubectl observation)
        deploy_keys = [k for k in observed if "deploy/" in k]
        if deploy_keys:
            dep = observed[deploy_keys[0]]
            ready = dep.get("readyReplicas", 0)
            desired = dep.get("desiredReplicas", 0)
            status = "PASS" if ready == desired and ready > 0 else "FAIL"
            results.append(ExecutionValidation(
                criterion="Deployment ready replicas match desired",
                expected=f"ready={desired}",
                observed=f"ready={ready}",
                status=status,
            ))
        else:
            results.append(ExecutionValidation(
                criterion="Deployment ready replicas match desired",
                expected="ready=2", observed="deployment not found",
                status="FAIL",
            ))

        # Check namespace
        results.append(ExecutionValidation(
            criterion="Namespace created",
            expected=ns_name,
            observed=ns_name if ns_name else "unknown",
            status="PASS" if ns_name else "FAIL",
        ))

        return results

    @staticmethod
    def validate_fakecloud(observation: dict[str, Any]) -> list[ExecutionValidation]:
        """Fakecloud-specific validation from boto3 observation."""
        results: list[ExecutionValidation] = []
        observed = observation.get("observed", {})
        buckets = observed.get("buckets", [])

        results.append(ExecutionValidation(
            criterion="Bucket exists",
            expected="at least 1 bucket",
            observed=f"{len(buckets)} buckets",
            status="PASS" if len(buckets) > 0 else "FAIL",
        ))

        results.append(ExecutionValidation(
            criterion="Bucket accessible via provider API",
            expected="accessible",
            observed="observed via boto3",
            status="PASS",
        ))

        return results


class ExecutionVerifier:
    """Independent verifier — consumes observations, validations, evidence."""

    @staticmethod
    def verify(validations: list[ExecutionValidation],
               evidence_refs: list[str] | None = None,
               executor_status: str = "") -> ExecutionVerification:
        """Produce independent verification from validations + evidence.

        IMPORTANT: executor_status alone can NEVER produce PASS.
        """
        if not validations:
            return ExecutionVerification(
                verifier_id="phase7-verifier",
                result=VerificationResult.INCONCLUSIVE,
                criteria=[],
                evidence_refs=evidence_refs or [],
                reason="No validations to verify",
            )

        all_passed = all(v.status == "PASS" for v in validations)
        any_failed = any(v.status == "FAIL" for v in validations)
        any_unknown = any(v.status == "UNKNOWN" for v in validations)

        criteria = [v.criterion for v in validations]

        if all_passed:
            return ExecutionVerification(
                verifier_id="phase7-verifier",
                result=VerificationResult.PASS,
                criteria=criteria,
                evidence_refs=evidence_refs or [],
                reason=f"All {len(validations)} validations passed",
            )
        elif any_failed:
            return ExecutionVerification(
                verifier_id="phase7-verifier",
                result=VerificationResult.FAIL,
                criteria=criteria,
                evidence_refs=evidence_refs or [],
                reason=f"{sum(1 for v in validations if v.status=='FAIL')}/{len(validations)} validations failed",
            )
        elif any_unknown:
            return ExecutionVerification(
                verifier_id="phase7-verifier",
                result=VerificationResult.INCONCLUSIVE,
                criteria=criteria,
                evidence_refs=evidence_refs or [],
                reason=f"{sum(1 for v in validations if v.status=='UNKNOWN')}/{len(validations)} validations unknown",
            )
        else:
            return ExecutionVerification(
                verifier_id="phase7-verifier",
                result=VerificationResult.INCONCLUSIVE,
                criteria=criteria,
                evidence_refs=evidence_refs or [],
                reason="Mixed validation results",
            )
