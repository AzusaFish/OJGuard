from dataclasses import dataclass


class BudgetExceededError(RuntimeError):
    """Raised when another paid model call would exceed the stop limit."""


@dataclass(slots=True)
class BudgetSnapshot:
    spent_cny: float
    warning_cny: float
    stop_cny: float

    @property
    def warning_reached(self) -> bool:
        return self.spent_cny >= self.warning_cny

    @property
    def stopped(self) -> bool:
        return self.spent_cny >= self.stop_cny

    @property
    def remaining_before_stop_cny(self) -> float:
        return max(0.0, self.stop_cny - self.spent_cny)


class BudgetGuard:
    def __init__(self, warning_cny: float, stop_cny: float) -> None:
        if warning_cny < 0 or stop_cny <= 0 or warning_cny > stop_cny:
            raise ValueError("invalid budget thresholds")
        self._warning_cny = warning_cny
        self._stop_cny = stop_cny
        self._spent_cny = 0.0

    def snapshot(self) -> BudgetSnapshot:
        return BudgetSnapshot(self._spent_cny, self._warning_cny, self._stop_cny)

    def authorize(self, estimated_cost_cny: float, *, essential: bool = False) -> None:
        if estimated_cost_cny < 0:
            raise ValueError("estimated cost cannot be negative")
        projected = self._spent_cny + estimated_cost_cny
        if projected > self._stop_cny and not essential:
            raise BudgetExceededError(
                f"projected cost {projected:.4f} CNY exceeds stop limit {self._stop_cny:.2f} CNY"
            )

    def record(self, actual_cost_cny: float) -> BudgetSnapshot:
        if actual_cost_cny < 0:
            raise ValueError("actual cost cannot be negative")
        self._spent_cny += actual_cost_cny
        return self.snapshot()
