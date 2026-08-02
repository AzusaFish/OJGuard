---
name: release-gate-problem-package
description: Apply deterministic OJGuard release policy to findings, evidence, execution results and approval records. Use after specialist checks or revalidation to produce PASS, WARNING, BLOCKED or HUMAN_REVIEW_REQUIRED without allowing an LLM to override missing evidence or human approval.
---

# Release Gate Problem Package

Apply policy as a deterministic decision step. Do not improvise release rules.

## Workflow

1. Validate every Finding and referenced Evidence identifier.
2. Reject stale, missing, hash-invalid or unreplayable blocking evidence.
3. Apply severity and confidence rules from the versioned release policy.
4. Verify first approval before accepting a patch-applied working copy.
5. Require complete baseline and regression results after any modification.
6. Produce a release recommendation, blocking issues, required actions and audit report identifier.
7. Require second human confirmation before `READY_FOR_RELEASE` becomes the recorded final decision.

## Mandatory Outcomes

- Return `BLOCKED` for confirmed critical defects.
- Return `HUMAN_REVIEW_REQUIRED` for unresolved semantic or Oracle conflicts.
- Never return PASS when a required tool failed or evidence is incomplete.
- Never publish to a real OJ in the initial-round implementation.

## Auditability

Record policy version, inputs, decision trace, approvals and artifact hashes. Preserve previous decisions when policy versions change.
