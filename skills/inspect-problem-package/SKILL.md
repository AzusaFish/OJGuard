---
name: inspect-problem-package
description: Validate an uploaded OJGuard or Kattis-style ZIP problem package before analysis. Use when a package is first received, when its structure or build targets may be unsafe or incomplete, or before any untrusted code is compiled.
---

# Inspect Problem Package

Treat the uploaded archive as untrusted and the original copy as immutable.

## Workflow

1. Call `inspect_package` with a package identifier, never an arbitrary host path.
2. Verify archive size, expanded size, file count, duplicate paths, traversal paths and symlinks.
3. Identify the statement, configuration, Validator, Checker, Oracle, reference solution and known wrong solutions.
4. Validate required metadata and declared language targets.
5. Request compiler diagnostics through the Runner only for known source targets.
6. Return a manifest, blocking errors, warnings and evidence identifiers.

## Output Rules

Return `SUCCESS`, `PARTIAL`, `FAILED` or `HUMAN_REVIEW`. Include `package_id`, normalized file roles, findings, `evidence_ids`, metrics and a structured error. Never treat a tool failure as a valid package.

## Safety

- Keep the original archive read-only.
- Reject absolute paths, `..`, links, devices and unsupported executable hooks.
- Do not execute generators, Validators or build scripts during structural inspection.
- Do not access the network, Docker API, host shell or credentials.

## Validation

Require a manifest hash and a reproducible list of normalized paths. A successful result must prove that every selected artifact resolves inside the immutable package root.
