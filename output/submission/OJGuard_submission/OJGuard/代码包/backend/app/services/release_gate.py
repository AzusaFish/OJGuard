from __future__ import annotations

from collections.abc import Iterable

from backend.app.domain import ConfidenceClass, Evidence, Finding, ReleaseDecision
from backend.app.domain.release import ReleaseGateResult, ReleasePolicy


class ReleaseGate:
    """Deterministic release policy. This service never calls an LLM."""

    def __init__(self, policy: ReleasePolicy | None = None) -> None:
        self.policy = policy or ReleasePolicy()

    def evaluate(
        self,
        *,
        findings: Iterable[Finding],
        evidence: Iterable[Evidence],
        required_checks_passed: bool,
        regression_passed: bool | None = None,
        second_approval_granted: bool = False,
    ) -> ReleaseGateResult:
        evidence_by_id = {item.id: item for item in evidence}
        blocking: list[str] = []
        warnings: list[str] = []
        review: list[str] = []
        actions: list[str] = []
        rationale: list[str] = []

        if not required_checks_passed:
            return ReleaseGateResult(
                policy_version=self.policy.version,
                decision=ReleaseDecision.HUMAN_REVIEW_REQUIRED,
                required_actions=["complete_required_checks"],
                rationale=["one or more required tools failed or did not complete"],
            )

        for finding in findings:
            missing_evidence = [
                evidence_id for evidence_id in finding.evidence_ids if evidence_id not in evidence_by_id
            ]
            if finding.confidence_class in {
                ConfidenceClass.CONFIRMED,
                ConfidenceClass.STATICALLY_PROVEN,
            } and (not finding.evidence_ids or missing_evidence):
                review.append(finding.id)
                rationale.append(f"{finding.id} has incomplete evidence references")
                continue

            if finding.confidence_class in {
                ConfidenceClass.SUSPECTED,
                ConfidenceClass.HUMAN_REVIEW_REQUIRED,
            }:
                review.append(finding.id)
                continue

            severity = finding.severity.value
            if severity in self.policy.block_confirmed_severities:
                blocking.append(finding.id)
            elif severity in self.policy.warning_confirmed_severities:
                warnings.append(finding.id)

        if review:
            actions.append("resolve_review_findings")
            decision = ReleaseDecision.HUMAN_REVIEW_REQUIRED
        elif blocking:
            actions.append("resolve_blocking_findings")
            decision = ReleaseDecision.BLOCKED
        elif regression_passed is False:
            actions.append("fix_failed_regression")
            decision = ReleaseDecision.BLOCKED
            rationale.append("post-patch regression failed")
        elif regression_passed and self.policy.require_second_approval and not second_approval_granted:
            actions.append("obtain_second_release_approval")
            decision = ReleaseDecision.HUMAN_REVIEW_REQUIRED
            rationale.append("regression passed but final human confirmation is missing")
        elif warnings:
            decision = ReleaseDecision.WARNING
        else:
            decision = ReleaseDecision.PASS

        return ReleaseGateResult(
            policy_version=self.policy.version,
            decision=decision,
            blocking_finding_ids=blocking,
            warning_finding_ids=warnings,
            review_finding_ids=review,
            required_actions=actions,
            rationale=rationale,
        )
