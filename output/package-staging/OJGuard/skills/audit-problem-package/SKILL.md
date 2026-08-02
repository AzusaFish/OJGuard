---
name: audit-problem-package
description: Audit a problem package, Validator, Checker, and data contract when an incident hypothesis points to package or Checker behavior.
---

# Audit Problem Package

Version: `1.0.0`

Inputs: package identifier, incident ID, suspected problem and version. Outputs: immutable manifest, contract findings, minimal counterexamples, and evidence IDs.

## Workflow

1. Resolve an uploaded immutable package by identifier, never a host path.
2. Compare statement, configuration, Validator, Checker, reference, and tests.
3. Use the runner only for declared sources and bounded probes.
4. Separate confirmed defects from hypotheses and semantic ambiguity.

Invocation condition: the playbook includes package or Checker as a live hypothesis. Errors: `PACKAGE_MISSING`, `UNSAFE_ARCHIVE`, `AMBIGUOUS_SEMANTICS`, `HUMAN_REVIEW`. Safety: originals remain read-only; no build hooks, links, network, or arbitrary execution. Idempotency key: package SHA-256 plus audit policy version. Acceptance: all findings cite artifact hashes and replayable evidence.
