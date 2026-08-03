---
name: normalize-judge-signals
description: Normalize monitoring, submission, deployment, and complaint records into evidence-linked incident signals. Use at DETECTED or TRIAGING before root-cause analysis.
---

# Normalize Judge Signals

Version: `1.0.0`

Inputs: `incident_id`, source records, time window, source system. Outputs: normalized signals with kind, timestamp, dimensions, summary, and evidence IDs.

## Workflow

1. At `TRIAGING`, call `incident.triage_signals`; it reads bounded signals and advances the shared incident to `INVESTIGATING` without precomputing a diagnosis.
2. Normalize timestamps to UTC and keep the original source identifier.
3. Deduplicate by source event ID and content hash.
4. Separate metric, submission, deployment, complaint, package, and queue signals.
5. Return anomaly dimensions and missing-source questions without asserting a root cause.

## Dependencies and collaboration

Dependent tools: `incident.triage_signals`, `submission.aggregate_verdicts`, and `deployment.list_changes`. Agent collaboration: the Signal Aggregator invokes this Skill first and publishes a provenance-preserving timeline to shared IncidentContext; the Root Cause Analyst and Incident Manager consume only those normalized records and evidence IDs. Reuse value: source adapters can normalize monitoring, ticket, log, submission, deployment, or billing events into one stable signal contract without changing downstream Agents.

Invocation condition: an incident has source records but no trusted signal timeline. Error states: `PARTIAL` for missing sources, `FAILED` for invalid timestamps, `HUMAN_REVIEW` for contradictory provenance.

Safety boundary: read-only; no replay, remediation, rejudge, score change, or approval. Idempotency key: `incident_id + source_event_id + content_hash`. Acceptance: repeated input produces the same normalized set and every signal retains provenance.
