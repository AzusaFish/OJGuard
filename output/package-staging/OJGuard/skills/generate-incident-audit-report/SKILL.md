---
name: generate-incident-audit-report
description: Generate a concise evidence-linked incident report after analysis or verification, including impact, approvals, batches, score changes, and remaining risks.
---

# Generate Incident Audit Report

Version: `1.0.0`

Inputs: persisted incident workspace and verification result. Outputs: stable JSON report and human-readable HTML report.

Invocation condition: a persisted incident exists; final wording additionally requires verification.

## Workflow

1. Call `report.generate_incident_report` for a persisted incident ID.
2. Include confirmed root cause, exact impact, remediation, approvals, batch coverage, score samples, and verification.
3. Cite evidence IDs rather than copying raw tool logs.
4. Disclose single-operator role simulation in the demo report.
5. Do not claim closure unless the state machine is `RESOLVED`.

Errors: `INCIDENT_NOT_FOUND`, `REPORT_INCOMPLETE`, `VERIFICATION_REQUIRED`. Safety: escape rendered text and omit secrets or unrestricted personal data. Idempotency key: incident updated timestamp plus report schema version. Acceptance: JSON validates, HTML renders without external assets, and every conclusion is supported by persisted records.
