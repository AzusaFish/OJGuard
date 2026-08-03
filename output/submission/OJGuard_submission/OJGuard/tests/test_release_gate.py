import unittest

from backend.app.domain import ConfidenceClass, Evidence, Finding, ReleaseDecision, Severity
from backend.app.services.release_gate import ReleaseGate


def evidence(evidence_id: str = "EV-1") -> Evidence:
    return Evidence(
        id=evidence_id,
        package_id="P-1",
        run_id="R-1",
        type="execution",
        producer="runner",
        artifact_path=f"P-1/R-1/{evidence_id}.json",
        sha256="0" * 64,
        tool_version="0.1.0",
    )


def finding(
    *,
    confidence: ConfidenceClass = ConfidenceClass.CONFIRMED,
    severity: Severity = Severity.CRITICAL,
    evidence_ids: list[str] | None = None,
) -> Finding:
    return Finding(
        id="F-1",
        package_id="P-1",
        run_id="R-1",
        source_agent="test",
        category="demo",
        severity=severity,
        confidence_class=confidence,
        description="demo finding",
        evidence_ids=evidence_ids if evidence_ids is not None else ["EV-1"],
    )


class ReleaseGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = ReleaseGate()

    def test_confirmed_critical_blocks(self) -> None:
        result = self.gate.evaluate(
            findings=[finding()], evidence=[evidence()], required_checks_passed=True
        )
        self.assertEqual(result.decision, ReleaseDecision.BLOCKED)
        self.assertEqual(result.blocking_finding_ids, ["F-1"])

    def test_missing_evidence_requires_review(self) -> None:
        result = self.gate.evaluate(
            findings=[finding(evidence_ids=["EV-missing"])],
            evidence=[],
            required_checks_passed=True,
        )
        self.assertEqual(result.decision, ReleaseDecision.HUMAN_REVIEW_REQUIRED)

    def test_suspected_finding_requires_review(self) -> None:
        result = self.gate.evaluate(
            findings=[finding(confidence=ConfidenceClass.SUSPECTED, evidence_ids=[])],
            evidence=[],
            required_checks_passed=True,
        )
        self.assertEqual(result.decision, ReleaseDecision.HUMAN_REVIEW_REQUIRED)

    def test_second_approval_is_required_after_regression(self) -> None:
        pending = self.gate.evaluate(
            findings=[],
            evidence=[],
            required_checks_passed=True,
            regression_passed=True,
            second_approval_granted=False,
        )
        approved = self.gate.evaluate(
            findings=[],
            evidence=[],
            required_checks_passed=True,
            regression_passed=True,
            second_approval_granted=True,
        )
        self.assertEqual(pending.decision, ReleaseDecision.HUMAN_REVIEW_REQUIRED)
        self.assertEqual(approved.decision, ReleaseDecision.PASS)


if __name__ == "__main__":
    unittest.main()
