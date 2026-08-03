---
name: reproduce-judge-failure
description: Reproduce an online-judge failure with fixed control and treatment environments through the locked-down runner.
---

# Reproduce Judge Failure

Version: `1.1.0`

Inputs: incident ID, Manager-selected experiment kind, submission or workload ID, control profile, treatment profile, resource limits, repetitions. Outputs: remaining experiment candidates, compile result, run metrics, comparison conclusion, and evidence IDs.

## Workflow

1. Resolve only declared workload identifiers and the Manager-selected `experiment_kind` through `judge.replay_submission`.
2. Hold source, input, CPU, memory, output, and time limits constant.
3. Run the control and treatment at least three times when the playbook requires stability.
4. Confirm a hypothesis only if the declared success threshold passes.
5. If the selected experiment cannot discriminate, persist `INCONCLUSIVE`, keep the incident in `INVESTIGATING`, and return the remaining bounded candidates.
6. Preserve all runs, including failures and inconclusive results.

## Dependencies and collaboration

Dependent tools: `judge.replay_submission`, the locked-down runner, immutable workload artifacts, and evidence hashing. Agent collaboration: the Root Cause Analyst designs and invokes the control experiment, returns reproducibility metrics to the Incident Manager, and provides the confirmed or inconclusive result to the Impact Analyst; it never delegates causal confirmation to the model alone. Reuse value: the fixed control-treatment contract supports runtime images, judge nodes, resource profiles, packages, and configuration regressions through replaceable runner adapters.

Invocation condition: falsifiable hypotheses exist and the Incident Manager selected one legal candidate. Errors: `RUNNER_UNAVAILABLE`, `COMPILE_ERROR`, `INCONCLUSIVE`, `RESOURCE_LIMIT`, `UNSUPPORTED_EXPERIMENT`. Safety: no network, host shell, arbitrary image, Docker API access, or self-selected next Agent. Idempotency key: workload hash, experiment kind, profiles, limits, and repetition count. Acceptance: the selected result is reproducible; a passed result distinguishes hypotheses, while an inconclusive result preserves the investigation and does not force state advancement.
