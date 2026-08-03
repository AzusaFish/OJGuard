import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

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

    def test_nonnegative_domain_does_not_require_negative_tests(self) -> None:
        base = Path.cwd() / ".test-tmp"
        base.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=base) as directory:
            root = Path(directory)
            manifest = {
                "input": {"a_i": {"min": 0, "max": 10}},
                "output": {"theoretical_max": 10},
            }
            (root / "problem.yaml").write_text(
                yaml.safe_dump(manifest), encoding="utf-8"
            )
            (root / "tests").mkdir()
            (root / "tests" / "001.in").write_text("2\n1 2\n", encoding="utf-8")
            report = BaselineAuditor().audit(root, package_id="clean", run_id="run")
            self.assertNotIn(
                "missing_negative_cases", {item.category for item in report.hypotheses}
            )


if __name__ == "__main__":
    unittest.main()
