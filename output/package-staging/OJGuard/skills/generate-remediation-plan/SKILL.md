---
name: generate-remediation-plan
description: Generate a gated remediation plan with preconditions, success checks, stop conditions, rollback points, and approval requirements.
---

# Generate Remediation Plan

Version: `1.0.0`

Inputs: incident context, confirmed root cause, frozen impact set, playbook. Outputs: ordered remediation steps, risk levels, requested approvals, and rollback actions.

Invocation condition: the impact set is calculated and the incident is at `REMEDIATION_PLANNING`.

## Workflow

1. Select only actions permitted by the incident playbook.
2. Define preconditions, success checks, stop conditions, and rollback for every step.
3. Plan control, canary, and bulk rejudge batches with stable idempotency keys.
4. Submit approval requests as pending; never approve them.

Errors: `IMPACT_REQUIRED`, `UNSUPPORTED_ACTION`, `APPROVAL_REQUIRED`, `HUMAN_REVIEW`. Safety: plan-only; no execution or formal score mutation. Idempotency key: incident ID, impact set hash, and playbook version. Acceptance: every L2+ action has an explicit human gate and every step can stop or roll back safely.
