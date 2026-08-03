# OJGuard original benchmark

This benchmark contains ten deterministic, team-authored C++17 problem-package
variants: two integer-range defects, two statement/Validator mismatches, two
missing-negative-test defects, two Checker trailing-output defects, and two
clean controls.

Run `python -m scripts.run_benchmark`. The script materializes complete packages
under ignored local data, runs the deterministic baseline auditor, and rewrites
`benchmark/results/baseline_report.json`. The report contains the exact expected
and observed labels plus defect-level precision/recall and clean-package false
block rate. It does not claim to measure LLM or AgentTeams quality.
