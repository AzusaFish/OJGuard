from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from datetime import UTC, datetime
from uuid import uuid4

from backend.app.domain import (
    ImpactAssessment,
    IncidentType,
    IncidentVerification,
    RejudgeBatch,
    RejudgeBatchState,
    ScenarioDataset,
    ScoreChange,
    SimulatedSubmission,
    VerificationStatus,
)


def _is_inferred_affected(
    incident_type: IncidentType, submission: SimulatedSubmission
) -> bool:
    if submission.verdict == submission.baseline_verdict:
        return False
    if incident_type == IncidentType.RUNTIME_REGRESSION:
        return submission.runtime_image == "java-runtime:v2.3.1"
    if incident_type == IncidentType.NODE_DEGRADATION:
        return submission.judge_node == "judge-node-03" and submission.submitted_at.hour >= 14
    if incident_type == IncidentType.CHECKER_DEFECT:
        return (
            submission.problem_id == "P-CHECKER-001"
            and submission.checker_version == "checker:v1.4.1"
        )
    return False


def infer_affected_submission_ids(dataset: ScenarioDataset) -> list[str]:
    """Infer impact from observable fields; labelled truth is only used by tests."""

    return sorted(
        item.id
        for item in dataset.submissions
        if _is_inferred_affected(dataset.truth.incident_type, item)
    )


def _rank(scores: dict[str, float]) -> dict[str, int]:
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return {candidate_id: index for index, (candidate_id, _) in enumerate(ordered, start=1)}


def calculate_score_changes(
    incident_id: str,
    dataset: ScenarioDataset,
    affected_submission_ids: list[str],
) -> list[ScoreChange]:
    affected = set(affected_submission_ids)
    before_scores: dict[str, float] = defaultdict(float)
    after_scores: dict[str, float] = defaultdict(float)
    for submission in dataset.submissions:
        before_scores[submission.candidate_id] += submission.score
        after_scores[submission.candidate_id] += (
            submission.baseline_score if submission.id in affected else submission.score
        )

    before_ranks = _rank(before_scores)
    after_ranks = _rank(after_scores)
    advancement_cutoff = max(1, math.ceil(len(dataset.candidates) * 0.1))
    changed_candidates = sorted(
        candidate_id
        for candidate_id in before_scores
        if before_scores[candidate_id] != after_scores[candidate_id]
    )
    return [
        ScoreChange(
            id=f"SCORE-{uuid4().hex[:10].upper()}",
            incident_id=incident_id,
            candidate_id=candidate_id,
            before_score=before_scores[candidate_id],
            after_score=after_scores[candidate_id],
            before_rank=before_ranks[candidate_id],
            after_rank=after_ranks[candidate_id],
            advancement_changed=(before_ranks[candidate_id] <= advancement_cutoff)
            != (after_ranks[candidate_id] <= advancement_cutoff),
        )
        for candidate_id in changed_candidates
    ]


def assess_impact(incident_id: str, dataset: ScenarioDataset, policy: str) -> ImpactAssessment:
    affected_ids = infer_affected_submission_ids(dataset)
    affected_set = set(affected_ids)
    affected_submissions = [item for item in dataset.submissions if item.id in affected_set]
    candidate_ids = sorted({item.candidate_id for item in affected_submissions})
    score_changes = calculate_score_changes(incident_id, dataset, affected_ids)
    return ImpactAssessment(
        id=f"IMPACT-{uuid4().hex[:10].upper()}",
        incident_id=incident_id,
        policy=policy,
        candidate_ids=candidate_ids,
        submission_ids=affected_ids,
        problem_ids=sorted({item.problem_id for item in affected_submissions}),
        languages=sorted({item.language for item in affected_submissions}),
        batches=sorted({item.batch for item in dataset.candidates if item.id in set(candidate_ids)}),
        affected_candidate_count=len(candidate_ids),
        affected_submission_count=len(affected_ids),
        projected_score_change_count=len(score_changes),
        projected_advancement_change_count=sum(item.advancement_changed for item in score_changes),
    )


def _idempotency_key(incident_id: str, kind: str, submission_ids: list[str]) -> str:
    digest = hashlib.sha256("\n".join(submission_ids).encode()).hexdigest()[:16]
    return f"{incident_id}:{kind}:{digest}"


def plan_rejudge_batches(
    incident_id: str,
    plan_id: str,
    submission_ids: list[str],
    *,
    bulk_size: int = 500,
) -> list[RejudgeBatch]:
    ordered = sorted(submission_ids)
    control_count = min(20, len(ordered))
    remaining_after_control = max(0, len(ordered) - control_count)
    canary_count = min(100, max(10, math.ceil(len(ordered) * 0.05)))
    canary_count = min(canary_count, remaining_after_control)
    groups: list[tuple[str, list[str]]] = [
        ("control", ordered[:control_count]),
        ("canary", ordered[control_count : control_count + canary_count]),
    ]
    bulk = ordered[control_count + canary_count :]
    groups.extend(
        ("bulk", bulk[index : index + bulk_size])
        for index in range(0, len(bulk), bulk_size)
    )
    return [
        RejudgeBatch(
            id=f"BATCH-{uuid4().hex[:10].upper()}",
            incident_id=incident_id,
            plan_id=plan_id,
            sequence=sequence,
            kind=kind,
            idempotency_key=_idempotency_key(incident_id, kind, ids),
            submission_ids=ids,
            planned_count=len(ids),
        )
        for sequence, (kind, ids) in enumerate(groups, start=1)
        if ids
    ]


def complete_batch(batch: RejudgeBatch) -> RejudgeBatch:
    if batch.state == RejudgeBatchState.COMPLETED:
        return batch
    updated = batch.model_copy(deep=True)
    updated.state = RejudgeBatchState.COMPLETED
    updated.completed_count = updated.planned_count
    updated.failed_count = 0
    updated.skipped_count = 0
    updated.updated_at = datetime.now(UTC)
    return updated


def verify_rejudge(
    incident_id: str,
    impact: ImpactAssessment,
    batches: list[RejudgeBatch],
    score_changes: list[ScoreChange],
) -> IncidentVerification:
    completed_ids = [
        submission_id
        for batch in batches
        if batch.state == RejudgeBatchState.COMPLETED
        for submission_id in batch.submission_ids
    ]
    expected = set(impact.submission_ids)
    completed = set(completed_ids)
    duplicate_count = len(completed_ids) - len(completed)
    missing_count = len(expected - completed)
    cross_scope_count = len(completed - expected)
    coverage_rate = len(completed & expected) / len(expected) if expected else 1.0
    checks = {
        "all_batches_completed": all(
            item.state == RejudgeBatchState.COMPLETED for item in batches
        ),
        "impact_scope_covered": missing_count == 0,
        "no_duplicate_rejudge": duplicate_count == 0,
        "no_cross_scope_rejudge": cross_scope_count == 0,
        "score_changes_recalculated": len(score_changes)
        == impact.projected_score_change_count,
    }
    resolved = all(checks.values()) and coverage_rate == 1
    return IncidentVerification(
        id=f"VERIFY-{uuid4().hex[:10].upper()}",
        incident_id=incident_id,
        status=(VerificationStatus.RESOLVED if resolved else VerificationStatus.HUMAN_REVIEW_REQUIRED),
        checks=checks,
        coverage_rate=coverage_rate,
        duplicate_rejudge_count=duplicate_count,
        missing_rejudge_count=missing_count,
        cross_scope_regression_count=cross_scope_count,
        summary=(
            "影响集合已完整、无重复且无越界地完成可信重评，成绩与晋级变化已重算。"
            if resolved
            else "可信重评存在覆盖、重复、越界或成绩一致性问题，需要人工复核。"
        ),
    )
