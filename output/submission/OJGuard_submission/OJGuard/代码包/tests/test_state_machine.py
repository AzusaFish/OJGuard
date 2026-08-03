import unittest

from backend.app.domain import RunStage, TaskContext
from backend.app.services.state_machine import InvalidTransitionError, transition


class StateMachineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = TaskContext(task_id="T-1", package_id="P-1", run_id="R-1")

    def test_valid_transition(self) -> None:
        updated = transition(self.context, RunStage.BASELINE_VALIDATING)
        self.assertEqual(updated.stage, RunStage.BASELINE_VALIDATING)
        self.assertEqual(self.context.stage, RunStage.RECEIVED)

    def test_invalid_transition(self) -> None:
        with self.assertRaises(InvalidTransitionError):
            transition(self.context, RunStage.READY_FOR_RELEASE)


if __name__ == "__main__":
    unittest.main()
