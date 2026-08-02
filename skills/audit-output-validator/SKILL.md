---
name: audit-output-validator
description: Audit a Checker, Special Judge or output validator using static inspection and constrained malicious outputs. Use when output parsing, EOF handling, NaN/Inf, multiple answers, tolerances, crashes or injection boundaries may let invalid submissions pass.
---

# Audit Output Validator

Verify Checker behavior by real sandbox execution and retain every bypass input.

## Workflow

1. Read the output contract, Checker source and representative answer artifacts.
2. Inspect token consumption, EOF checks, parse errors, numeric conversion, tolerance and multiple-answer behavior.
3. Generate bounded probes for trailing tokens, missing tokens, malformed numbers, `NaN`, `inf`, oversized values and whitespace variants when applicable.
4. Execute probes through `probe_checker` in the sandbox.
5. Replay any accepted invalid output.
6. Emit vulnerabilities, bypass evidence and candidate patch Diff identifiers.

## Safety

Limit probe size and count. Do not inject commands, paths or network requests. Treat Checker crash and timeout as safe rejection plus a reliability Finding, never as acceptance.

## Human Review

Require review before changing floating tolerance, multiple-answer semantics or any rule that may alter the problem meaning. Patch generation never grants patch approval.
