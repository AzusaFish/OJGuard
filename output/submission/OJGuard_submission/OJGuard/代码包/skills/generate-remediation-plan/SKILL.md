---
name: generate-remediation-plan
description: Generate a gated remediation plan with preconditions, success checks, stop conditions, rollback points, and approval requirements.
---

# Generate Remediation Plan

Version: `1.1.0`

Inputs: incident context, confirmed root cause, frozen impact set, playbook, optional failed canary and previous plan. Outputs: ordered remediation steps, plan revision/supersession, risk levels, requested approvals, and rollback actions.

Invocation condition: the impact set is calculated and the incident is at `REMEDIATION_PLANNING`, or a canary failed and the incident is at `PAUSED`.

## Workflow

1. Select only actions permitted by the incident playbook.
2. Define preconditions, success checks, stop conditions, and rollback for every step.
3. Plan control, canary, and bulk rejudge batches with stable idempotency keys.
4. Submit approval requests as pending; never approve them.
5. After canary failure, preserve the impact set, create `revision+1`, link the previous plan and failed batch, create only a `canary_retry`, and revoke the prior technical approvals.

## Dependencies and collaboration

Dependent tools: `rejudge.create_plan`, `incident.get_approvals`, the frozen impact-set hash, and the incident Playbook. Agent collaboration: the Remediation Planner consumes confirmed root cause and impact outputs, creates human approval requests for the Incident Manager to track, and supplies immutable batches and rollback points to the Rejudge Executor. Reuse value: policy-based action templates allow new incident types to reuse the same approval and rollback machinery while changing only Playbook conditions.

Errors: `IMPACT_REQUIRED`, `FAILED_CANARY_REQUIRED`, `UNSUPPORTED_ACTION`, `APPROVAL_REQUIRED`, `HUMAN_REVIEW`. Safety: plan-only; no execution, frozen-scope mutation, failed-batch rewriting, or formal score mutation. Idempotency key: incident ID, impact-set hash, playbook version, previous plan ID, and failed batch ID. Acceptance: every L2+ action has an explicit human gate, every step can stop or roll back safely, and recovery requires a new plan version plus fresh approval.
