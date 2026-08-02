---
name: generate-adversarial-tests
description: Generate bounded, valid and reproducible test inputs for a specific OJGuard risk hypothesis. Use after a problem contract and verification plan exist, especially for boundary, overflow, missing-structure, wrong-solution and metamorphic test strategies.
---

# Generate Adversarial Tests

Generate tests for one explicit hypothesis within the assigned budget.

## Workflow

1. Read the ProblemContract, hypothesis, verification plan, case budget and seed.
2. Prefer deterministic boundary templates before model-generated free-form inputs.
3. Generate focused candidates with coverage tags and seed lineage.
4. Validate every candidate through the authorized Validator tool.
5. Discard invalid inputs and record the rejection reason.
6. Deduplicate canonical input bytes.
7. Return artifact identifiers, coverage tags, generation metrics and the next differential-test request.

## Guardrails

- Never exceed case, byte or execution budgets.
- Never invoke host commands or Docker directly.
- Do not alter the original or existing tests.
- Do not call an input valid merely because it looks consistent with the statement.

## Failure Handling and Validation

Retry deterministic generation with recorded seed lineage. Return `PARTIAL` when only some coverage goals are met. Escalate when no legal input is found. A generated case is usable only after Validator acceptance and artifact hashing.
