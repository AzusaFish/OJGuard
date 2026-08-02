from datetime import datetime, timezone

from backend.app.domain import RunStage, TaskContext


class InvalidTransitionError(ValueError):
    """Raised when a run attempts an invalid state transition."""


ALLOWED_TRANSITIONS: dict[RunStage, set[RunStage]] = {
    RunStage.RECEIVED: {RunStage.BASELINE_VALIDATING, RunStage.CANCELLED, RunStage.FAILED},
    RunStage.BASELINE_VALIDATING: {RunStage.ANALYZING, RunStage.BLOCKED, RunStage.FAILED},
    RunStage.ANALYZING: {
        RunStage.TESTING,
        RunStage.HUMAN_REVIEW_REQUIRED,
        RunStage.BUDGET_EXHAUSTED,
        RunStage.FAILED,
    },
    RunStage.TESTING: {
        RunStage.EVIDENCE_REVIEW,
        RunStage.HUMAN_REVIEW_REQUIRED,
        RunStage.BUDGET_EXHAUSTED,
        RunStage.FAILED,
    },
    RunStage.EVIDENCE_REVIEW: {
        RunStage.BLOCKED,
        RunStage.HUMAN_REVIEW_REQUIRED,
        RunStage.PASS_CANDIDATE,
        RunStage.FAILED,
    },
    RunStage.BLOCKED: {RunStage.PATCH_PENDING_APPROVAL, RunStage.CANCELLED},
    RunStage.HUMAN_REVIEW_REQUIRED: {
        RunStage.ANALYZING,
        RunStage.TESTING,
        RunStage.BLOCKED,
        RunStage.CANCELLED,
    },
    RunStage.PASS_CANDIDATE: {RunStage.READY_FOR_RELEASE, RunStage.BLOCKED},
    RunStage.PATCH_PENDING_APPROVAL: {RunStage.REVALIDATING, RunStage.BLOCKED, RunStage.CANCELLED},
    RunStage.REVALIDATING: {
        RunStage.READY_FOR_RELEASE,
        RunStage.BLOCKED,
        RunStage.HUMAN_REVIEW_REQUIRED,
        RunStage.FAILED,
    },
    RunStage.BUDGET_EXHAUSTED: {RunStage.ANALYZING, RunStage.CANCELLED},
    RunStage.READY_FOR_RELEASE: set(),
    RunStage.FAILED: set(),
    RunStage.CANCELLED: set(),
}


def transition(context: TaskContext, target: RunStage) -> TaskContext:
    allowed = ALLOWED_TRANSITIONS.get(context.stage, set())
    if target not in allowed:
        raise InvalidTransitionError(f"cannot transition from {context.stage} to {target}")
    updated = context.model_copy(deep=True)
    updated.stage = target
    updated.updated_at = datetime.now(timezone.utc)
    return updated
