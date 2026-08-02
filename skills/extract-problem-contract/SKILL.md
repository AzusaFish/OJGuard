---
name: extract-problem-contract
description: Extract a source-linked problem contract from statements, configuration, samples and Validator code. Use after package inspection when downstream solution analysis and test generation need explicit types, ranges, output rules and unresolved conflicts.
---

# Extract Problem Contract

Build a contract whose every field retains its source. Do not silently resolve conflicting authorities.

## Workflow

1. Read only the artifacts selected by package inspection.
2. Extract input variables, types, ranges, relations, output type, answer bounds, multiple-answer rules and tolerance rules.
3. Record each value with file, line or structured-field provenance.
4. Compare statement, configuration, samples and Validator constraints.
5. Mark absent or uncertain fields as `unknown` instead of inventing values.
6. Emit inconsistencies, ambiguities and evidence identifiers.

## Confidence Rules

Use `STATICALLY_PROVEN` only for deterministic parsed constraints or valid mathematical range derivations. Use `SUSPECTED` for language interpretation. Send unresolved semantic conflicts to human review.

## Failure Handling

Return a partial contract on parse failure. Preserve all conflicting values. Do not block downstream work unless a required execution constraint is missing or unsafe.

## Safety and Validation

Use read-only artifact tools without network or code execution. Validate the final document against the ProblemContract schema and require source provenance for every non-unknown constraint.
