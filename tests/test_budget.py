import unittest

from backend.app.services.budget import BudgetExceededError, BudgetGuard


class BudgetGuardTests(unittest.TestCase):
    def test_warning_and_stop_guard(self) -> None:
        guard = BudgetGuard(warning_cny=6, stop_cny=8)
        snapshot = guard.record(6)
        self.assertTrue(snapshot.warning_reached)
        self.assertFalse(snapshot.stopped)
        with self.assertRaises(BudgetExceededError):
            guard.authorize(2.01)

    def test_mock_call_with_zero_cost_is_allowed(self) -> None:
        guard = BudgetGuard(warning_cny=6, stop_cny=8)
        guard.authorize(0)
        self.assertEqual(guard.snapshot().spent_cny, 0)


if __name__ == "__main__":
    unittest.main()
