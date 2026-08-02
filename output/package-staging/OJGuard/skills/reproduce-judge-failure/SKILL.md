---
name: reproduce-judge-failure
description: Reproduce an online-judge failure with fixed control and treatment environments through the locked-down runner.
---

# Reproduce Judge Failure

Version: `1.0.0`

Inputs: incident ID, submission or workload ID, control profile, treatment profile, resource limits, repetitions. Outputs: compile result, run metrics, comparison conclusion, and evidence IDs.

## Workflow

1. Resolve only declared workload identifiers through `judge.replay_submission`.
2. Hold source, input, CPU, memory, output, and time limits constant.
3. Run the control and treatment at least three times when the playbook requires stability.
4. Confirm a hypothesis only if the declared success threshold passes.
5. Preserve all runs, including failures and inconclusive results.

Invocation condition: a falsifiable hypothesis exists. Errors: `RUNNER_UNAVAILABLE`, `COMPILE_ERROR`, `INCONCLUSIVE`, `RESOURCE_LIMIT`. Safety: no network, host shell, arbitrary image, or Docker API access. Idempotency key: workload hash, profiles, limits, and repetition count. Acceptance: result is reproducible and distinguishes control from treatment under identical limits.
