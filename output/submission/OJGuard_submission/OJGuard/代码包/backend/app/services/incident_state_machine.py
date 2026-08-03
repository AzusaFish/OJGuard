from __future__ import annotations

from datetime import UTC, datetime

from backend.app.domain import (
    IncidentApprovalDecision,
    IncidentContext,
    IncidentStage,
)


class InvalidIncidentTransitionError(ValueError):
    """Raised when an incident transition is invalid or bypasses a gate."""


ALLOWED_INCIDENT_TRANSITIONS: dict[IncidentStage, set[IncidentStage]] = {
    IncidentStage.DETECTED: {
        IncidentStage.TRIAGING,
        IncidentStage.HUMAN_REVIEW_REQUIRED,
        IncidentStage.FAILED,
    },
    IncidentStage.TRIAGING: {
        IncidentStage.INVESTIGATING,
        IncidentStage.HUMAN_REVIEW_REQUIRED,
        IncidentStage.FAILED,
    },
    IncidentStage.INVESTIGATING: {
        IncidentStage.IMPACT_ASSESSING,
        IncidentStage.HUMAN_REVIEW_REQUIRED,
        IncidentStage.PAUSED,
        IncidentStage.FAILED,
    },
    IncidentStage.IMPACT_ASSESSING: {
        IncidentStage.REMEDIATION_PLANNING,
        IncidentStage.INVESTIGATING,
        IncidentStage.HUMAN_REVIEW_REQUIRED,
        IncidentStage.FAILED,
    },
    IncidentStage.REMEDIATION_PLANNING: {
        IncidentStage.APPROVAL_PENDING,
        IncidentStage.IMPACT_ASSESSING,
        IncidentStage.HUMAN_REVIEW_REQUIRED,
        IncidentStage.FAILED,
    },
    IncidentStage.APPROVAL_PENDING: {
        IncidentStage.EXECUTING,
        IncidentStage.REMEDIATION_PLANNING,
        IncidentStage.HUMAN_REVIEW_REQUIRED,
        IncidentStage.PAUSED,
        IncidentStage.FAILED,
    },
    IncidentStage.EXECUTING: {
        IncidentStage.REJUDGING,
        IncidentStage.VERIFYING,
        IncidentStage.PAUSED,
        IncidentStage.ROLLED_BACK,
        IncidentStage.HUMAN_REVIEW_REQUIRED,
        IncidentStage.FAILED,
    },
    IncidentStage.REJUDGING: {
        IncidentStage.VERIFYING,
        IncidentStage.PAUSED,
        IncidentStage.ROLLED_BACK,
        IncidentStage.HUMAN_REVIEW_REQUIRED,
        IncidentStage.FAILED,
    },
    IncidentStage.VERIFYING: {
        IncidentStage.RESOLVED,
        IncidentStage.REJUDGING,
        IncidentStage.ROLLED_BACK,
        IncidentStage.HUMAN_REVIEW_REQUIRED,
        IncidentStage.FAILED,
    },
    IncidentStage.HUMAN_REVIEW_REQUIRED: {
        IncidentStage.INVESTIGATING,
        IncidentStage.IMPACT_ASSESSING,
        IncidentStage.REMEDIATION_PLANNING,
        IncidentStage.APPROVAL_PENDING,
        IncidentStage.PAUSED,
        IncidentStage.FAILED,
    },
    IncidentStage.PAUSED: {
        IncidentStage.INVESTIGATING,
        IncidentStage.APPROVAL_PENDING,
        IncidentStage.EXECUTING,
        IncidentStage.REJUDGING,
        IncidentStage.ROLLED_BACK,
        IncidentStage.FAILED,
    },
    IncidentStage.RESOLVED: set(),
    IncidentStage.ROLLED_BACK: set(),
    IncidentStage.FAILED: set(),
}


def _has_approval(context: IncidentContext, key: str) -> bool:
    return context.approval_state.get(key) == IncidentApprovalDecision.APPROVED


def _validate_gate(context: IncidentContext, target: IncidentStage) -> None:
    if target == IncidentStage.INVESTIGATING and not context.signal_ids:
        raise InvalidIncidentTransitionError("cannot investigate before signals are attached")
    if target == IncidentStage.IMPACT_ASSESSING:
        has_root_cause = bool(context.confirmed_root_cause_ids)
        if not has_root_cause and not _has_approval(context, "accept_unconfirmed_risk"):
            raise InvalidIncidentTransitionError(
                "cannot assess impact before a root cause is confirmed or risk is accepted"
            )
    if target == IncidentStage.REMEDIATION_PLANNING and not context.impact_assessment_id:
        raise InvalidIncidentTransitionError("cannot plan remediation before impact is assessed")
    if target == IncidentStage.APPROVAL_PENDING and not context.remediation_plan_ids:
        raise InvalidIncidentTransitionError("cannot request approval without a remediation plan")
    if target == IncidentStage.EXECUTING and not _has_approval(context, "execute_plan"):
        raise InvalidIncidentTransitionError("cannot execute before the remediation plan is approved")
    if target == IncidentStage.REJUDGING:
        if not context.control_experiment_passed:
            raise InvalidIncidentTransitionError("control experiment must pass before rejudging")
        if not context.canary_rejudge_passed:
            raise InvalidIncidentTransitionError("canary rejudge must pass before bulk rejudging")
        if not _has_approval(context, "run_bulk_rejudge"):
            raise InvalidIncidentTransitionError("bulk rejudge requires explicit approval")
    if (
        target == IncidentStage.VERIFYING
        and context.rejudge_batch_ids
        and not context.rejudge_complete
    ):
        raise InvalidIncidentTransitionError("all approved rejudge batches must finish first")
    if target == IncidentStage.RESOLVED:
        if not context.verification_id:
            raise InvalidIncidentTransitionError("incident cannot resolve without verification")
        if not _has_approval(context, "close_incident"):
            raise InvalidIncidentTransitionError("incident closure requires explicit approval")


def transition_incident(context: IncidentContext, target: IncidentStage) -> IncidentContext:
    allowed = ALLOWED_INCIDENT_TRANSITIONS.get(context.stage, set())
    if target not in allowed:
        raise InvalidIncidentTransitionError(
            f"cannot transition incident from {context.stage} to {target}"
        )
    _validate_gate(context, target)
    updated = context.model_copy(deep=True)
    updated.stage = target
    updated.updated_at = datetime.now(UTC)
    return updated
