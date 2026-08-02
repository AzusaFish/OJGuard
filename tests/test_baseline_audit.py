import unittest
from pathlib import Path

from backend.app.services.baseline_audit import BaselineAuditor


class BaselineAuditorTests(unittest.TestCase):
    def test_demo_produces_four_verification_hypotheses(self) -> None:
        root = Path("demo/maximum_segment_score")
        report = BaselineAuditor().audit(root, package_id="demo", run_id="run")
        categories = {hypothesis.category for hypothesis in report.hypotheses}
        self.assertEqual(
            categories,
            {
                "statement_validator_mismatch",
                "integer_overflow",
                "missing_negative_cases",
                "checker_trailing_output",
            },
        )
        self.assertTrue(all(h.status == "PENDING_VERIFICATION" for h in report.hypotheses))


if __name__ == "__main__":
    unittest.main()
