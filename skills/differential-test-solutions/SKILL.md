---
name: differential-test-solutions
description: Compile and compare an Oracle, reference solution and candidate solutions in the OJGuard sandbox. Use when generated or existing tests must verify a hypothesis with reproducible execution evidence, resource limits and explicit Oracle-conflict handling.
---

# Differential Test Solutions

Use only OJGuard MCP Runner tools. Treat every source and binary as untrusted.

## Workflow

1. Resolve artifact identifiers under the immutable package root.
2. Compile each target with fixed compiler flags and record diagnostics.
3. Validate each input before execution.
4. Run the Oracle and candidates with fixed CPU, memory, process, time and output limits.
5. Normalize output only according to the declared output contract.
6. Record disagreements, exit states, durations, tool versions and content hashes.
7. Replay a disagreement before promoting it to `CONFIRMED`.

## Decision Rules

Do not assume the Oracle is correct when independent Oracles disagree or when it crashes, times out or violates the Validator contract. Escalate Oracle conflicts to human review.

## Failure and Safety

Mark compile errors as invalid solution results. Kill timeouts and preserve evidence. Never run outside the sandbox, enable network, use arbitrary commands or accept missing result files as success.
