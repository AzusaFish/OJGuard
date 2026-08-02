---
name: verify-score-consistency
description: Independently verify rejudge coverage, duplicates, cross-scope execution, score changes, ranks, and advancement outcomes.
---

# Verify Score Consistency

Version: `1.0.0`

Inputs: approved impact set, completed batches, original snapshot, temporary results, approvals. Outputs: verification checks, coverage rate, discrepancy counts, and closure status.

Invocation condition: all approved rejudge batches have reached a terminal state.

## Workflow

1. Recompute the executed submission union independently from batch records.
2. Compare it exactly with the approved impact set and count missing, duplicate, and cross-scope IDs.
3. Recalculate scores, ranks, and advancement changes from snapshots.
4. Validate evidence and approval completeness.
5. Return `RESOLVED`, `RESOLVED_WITH_WARNING`, `ROLLBACK_REQUIRED`, or `HUMAN_REVIEW_REQUIRED`; do not close the incident.

Errors: `INCOMPLETE_BATCH`, `SCOPE_MISMATCH`, `SCORE_MISMATCH`, `EVIDENCE_MISSING`. Safety: read-only verification. Idempotency key: hashes of impact, batch, score, and approval snapshots. Acceptance: a resolved result requires 100% coverage, zero duplicates, zero cross-scope execution, and exact score agreement.
