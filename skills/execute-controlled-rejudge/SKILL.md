---
name: execute-controlled-rejudge
description: Execute approved control, canary, and bulk rejudge batches with exact scope and idempotency enforcement.
---

# Execute Controlled Rejudge

Version: `1.0.0`

Inputs: incident ID, approved plan, batch ID, idempotency key, approval state. Outputs: planned/completed/failed/skipped counts, temporary results, and evidence IDs.

Invocation condition: the requested batch exists and its state-machine and human-approval gates pass.

## Workflow

1. Verify plan, impact set, state-machine stage, and required approval.
2. Complete the control batch, then the canary batch; stop on any failed check.
3. Execute bulk batches only after business approval.
4. Retry only with the original idempotency key and never duplicate completed submissions.
5. Leave formal score writeback simulated.

## Dependencies and collaboration

Dependent tools: `rejudge.execute_batch`, `rejudge.pause_batch`, the locked-down runner, the persisted approval ledger, and the frozen impact-set hash. Agent collaboration: the Rejudge Executor accepts only the Remediation Planner's approved batches, publishes counts and temporary results to shared state, and hands terminal batch evidence to the Verification Auditor; failures return control to the Incident Manager. Reuse value: the control-canary-bulk pattern and idempotency contract can govern any high-risk batch repair, not only OJ rejudging.

Errors: `APPROVAL_REQUIRED`, `CANARY_FAILED`, `SCOPE_DRIFT`, `BATCH_PAUSED`, `RUNNER_UNAVAILABLE`. Safety: no arbitrary IDs, Docker, host shell, or original-result overwrite. Idempotency key: the persisted batch key. Acceptance: executed union equals approved impact set, intersection duplicates are empty, and failed gates stop later batches.
