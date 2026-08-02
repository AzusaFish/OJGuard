from __future__ import annotations

import hashlib
import unittest

from backend.app.domain import ExperimentState, IncidentType
from backend.app.services.scenario_analysis import ScenarioAnalyzer
from backend.app.services.scenario_data import ScenarioDataGenerator


def dataset_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ScenarioDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.generator = ScenarioDataGenerator(seed=20260802)
        self.analyzer = ScenarioAnalyzer()

    def test_runtime_dataset_is_reproducible_and_has_expected_signal(self) -> None:
        first = self.generator.runtime_regression()
        second = self.generator.runtime_regression()
        self.assertEqual(len(first.candidates), 5_000)
        self.assertEqual(len(first.submissions), 20_000)
        self.assertEqual(
            dataset_hash(first.model_dump_json()), dataset_hash(second.model_dump_json())
        )

        metrics = self.analyzer.metrics(first)
        self.assertEqual(metrics.incident_type, IncidentType.RUNTIME_REGRESSION)
        self.assertGreater(metrics.affected_submission_count, 500)
        self.assertGreater(metrics.observed_failure_rate, 0.35)
        self.assertLess(metrics.observed_failure_rate, 0.50)
        self.assertGreater(metrics.failure_rate_delta, 0.25)
        node_rates = list(metrics.per_group_failure_rate.values())
        self.assertLess(max(node_rates) - min(node_rates), 0.10)

    def test_node_scenario_distinguishes_node_from_runtime(self) -> None:
        dataset = self.generator.node_degradation()
        metrics = self.analyzer.metrics(dataset)
        node_03_rate = metrics.per_group_failure_rate["judge-node-03"]
        control_rates = [
            rate
            for node, rate in metrics.per_group_failure_rate.items()
            if node != "judge-node-03"
        ]
        self.assertGreater(node_03_rate, 0.35)
        self.assertLess(max(control_rates), 0.10)
        self.assertEqual(dataset.truth.expected_dimensions["judge_node"], ["judge-node-03"])

    def test_checker_scenario_is_scoped_to_one_problem_and_contract(self) -> None:
        dataset = self.generator.checker_defect()
        metrics = self.analyzer.metrics(dataset)
        self.assertGreater(metrics.per_group_failure_rate["P-CHECKER-001"], 0.25)
        self.assertEqual(metrics.per_group_failure_rate["P-CONTROL-001"], 0.0)
        self.assertEqual(metrics.per_group_failure_rate["P-CONTROL-002"], 0.0)

        hypotheses = self.analyzer.competing_hypotheses("INC-CHECKER", dataset)
        experiment = self.analyzer.run_comparison("INC-CHECKER", dataset, hypotheses)
        self.assertEqual(experiment.state, ExperimentState.PASSED)
        self.assertIn("checker:v1.4.1", experiment.conclusion or "")

    def test_only_three_scenarios_are_claimed_executable(self) -> None:
        for incident_type in (
            IncidentType.RUNTIME_REGRESSION,
            IncidentType.NODE_DEGRADATION,
            IncidentType.CHECKER_DEFECT,
        ):
            self.assertEqual(self.generator.generate(incident_type).truth.incident_type, incident_type)
        with self.assertRaises(ValueError):
            self.generator.generate(IncidentType.QUEUE_CONGESTION)


if __name__ == "__main__":
    unittest.main()
