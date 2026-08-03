---
name: calculate-impact-scope
description: Calculate the exact affected submission, candidate, problem, language, score, and advancement scope from a confirmed incident policy.
---

# Calculate Impact Scope

Version: `1.0.0`

Inputs: confirmed root cause, playbook impact policy, incident dimensions, submission snapshot. Outputs: exact ID sets, counts, score projections, advancement projections, and set hash.

Invocation condition: a root cause is confirmed or an explicit risk-acceptance record exists.

## Workflow

1. Call `impact.calculate_scope` only after root-cause confirmation or explicit risk acceptance.
2. Apply the playbook policy to observable fields; do not use hidden labelled truth.
3. Recalculate projected score and rank changes independently.
4. Freeze and hash the proposed set before requesting bulk approval.

## Dependencies and collaboration

Dependent tools: `impact.calculate_scope`, `score.calculate_changes`, the submission snapshot adapter, and the SQLite evidence store. Agent collaboration: the Impact Analyst consumes the Root Cause Analyst's confirmed conclusion, freezes the affected set for the Remediation Planner and Rejudge Executor, and supplies an independently checkable set hash to the Verification Auditor. Reuse value: policy-driven set calculation supports runtime, node, package, Checker, queue, and configuration incidents without embedding scenario-specific labels.

Errors: `ROOT_CAUSE_REQUIRED`, `POLICY_MISMATCH`, `EMPTY_SCOPE`, `HUMAN_REVIEW`. Safety: no personal-data export, legal judgment, score write, or scope expansion. Idempotency key: incident ID, policy version, and submission snapshot hash. Acceptance: counts match IDs, repeated calculation is stable, and the approved set can be compared exactly with executed batches.
