---
name: audit-reference-solution
description: Audit C++ reference and known wrong solutions against a sourced problem contract. Use to identify numeric, boundary, complexity and undefined-behavior risks and convert them into testable hypotheses rather than unsupported correctness claims.
---

# Audit Reference Solution

Produce verification-ready hypotheses. Never declare a runtime defect confirmed without deterministic evidence.

## Workflow

1. Read the ProblemContract and selected source artifacts.
2. Summarize the implemented algorithm and compare it with any editorial claim.
3. Check numeric ranges, container bounds, empty cases, division, initialization, recursion depth and likely worst-case complexity.
4. Record exact source locations and the contract fields used by each inference.
5. Convert each risk into a hypothesis with severity, confidence and a concrete verification plan.
6. Route executable verification to adversarial testing.

## Evidence Classes

- Use `STATICALLY_PROVEN` only when a deterministic type/range or language rule is sufficient.
- Use `SUSPECTED` when the model interprets algorithm behavior.
- Use `HUMAN_REVIEW_REQUIRED` when problem semantics or implementation intent is unclear.

## Failure and Safety

Fall back to compiler diagnostics when parsing fails. Do not run binaries directly, modify source files, approve patches or make release decisions. Return structured hypotheses even when the audit is partial.
