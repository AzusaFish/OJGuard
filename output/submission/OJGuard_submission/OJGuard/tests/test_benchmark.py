import unittest
from pathlib import Path

import yaml


class BenchmarkDefinitionTests(unittest.TestCase):
    def test_has_ten_original_cases_and_two_clean_controls(self) -> None:
        path = Path(__file__).parents[1] / "benchmark" / "cases.yaml"
        cases = yaml.safe_load(path.read_text(encoding="utf-8"))["cases"]
        self.assertEqual(len(cases), 10)
        self.assertEqual(sum(bool(item.get("clean_package")) for item in cases), 2)
        categories = {category for item in cases for category in item.get("defects", [])}
        self.assertEqual(
            categories,
            {
                "integer_overflow",
                "statement_validator_mismatch",
                "missing_negative_cases",
                "checker_trailing_output",
            },
        )


if __name__ == "__main__":
    unittest.main()
