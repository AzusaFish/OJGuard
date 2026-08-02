---
name: normalize-judge-signals
description: Normalize monitoring, submission, deployment, and complaint records into evidence-linked incident signals. Use at DETECTED or TRIAGING before root-cause analysis.
---

# Normalize Judge Signals

Version: `1.0.0`

Inputs: `incident_id`, source records, time window, source system. Outputs: normalized signals with kind, timestamp, dimensions, summary, and evidence IDs.

## Workflow

1. Read signals with `incident.list_signals`; never read arbitrary paths.
2. Normalize timestamps to UTC and keep the original source identifier.
3. Deduplicate by source event ID and content hash.
4. Separate metric, submission, deployment, complaint, package, and queue signals.
5. Return anomaly dimensions and missing-source questions without asserting a root cause.

Invocation condition: an incident has source records but no trusted signal timeline. Error states: `PARTIAL` for missing sources, `FAILED` for invalid timestamps, `HUMAN_REVIEW` for contradictory provenance.

Safety boundary: read-only; no replay, remediation, rejudge, score change, or approval. Idempotency key: `incident_id + source_event_id + content_hash`. Acceptance: repeated input produces the same normalized set and every signal retains provenance.
