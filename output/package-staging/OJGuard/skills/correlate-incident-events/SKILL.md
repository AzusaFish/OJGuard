---
name: correlate-incident-events
description: Correlate judge anomalies with deployments, nodes, runtime images, packages, and time windows while keeping competing hypotheses explicit.
---

# Correlate Incident Events

Version: `1.0.0`

Inputs: normalized signals, playbook dimensions, deployment events. Outputs: correlation matrix, candidate hypotheses, controls, and open questions.

## Workflow

1. Group failures by the playbook dimensions and calculate baseline versus observed rates.
2. Align deployment changes and complaints on the same UTC timeline.
3. Propose at least one competing hypothesis and a falsification test for each.
4. Mark correlations as leads until deterministic comparison evidence exists.

Invocation condition: normalized signals exist. Errors: `INSUFFICIENT_DATA`, `CONFLICTING_WINDOWS`, `HUMAN_REVIEW`. Safety: read-only and no causal assertion without experiment evidence. Idempotency key: hash of signal IDs plus playbook version. Acceptance: every hypothesis names observable support, a control, and a rejection condition.
