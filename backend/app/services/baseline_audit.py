from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from backend.app.domain import Hypothesis, Severity


class BaselineAuditReport(BaseModel):
    package_id: str
    run_id: str
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    inspected_files: list[str] = Field(default_factory=list)


class BaselineAuditor:
    """Deterministic, narrow first-pass rules for the C++17 initial scope."""

    def audit(self, package_root: Path, *, package_id: str, run_id: str) -> BaselineAuditReport:
        package_root = package_root.resolve()
        manifest_path = package_root / "problem.yaml"
        if not manifest_path.is_file():
            raise ValueError("problem.yaml is required for the initial OJGuard format")
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        hypotheses: list[Hypothesis] = []
        inspected = ["problem.yaml"]

        validator_rel = manifest.get("validator")
        if validator_rel:
            validator_path = self._inside(package_root, validator_rel)
            validator_source = validator_path.read_text(encoding="utf-8")
            inspected.append(validator_rel)
            configured_min = int(manifest["input"]["a_i"]["min"])
            configured_max = int(manifest["input"]["a_i"]["max"])
            validator_limit = self._extract_absolute_validator_limit(validator_source)
            statement_limit = max(abs(configured_min), abs(configured_max))
            if validator_limit is not None and validator_limit != statement_limit:
                hypotheses.append(
                    Hypothesis(
                        id="H-SPEC-001",
                        package_id=package_id,
                        run_id=run_id,
                        source_agent="specification-auditor",
                        category="statement_validator_mismatch",
                        description=(
                            f"manifest allows |a_i| <= {statement_limit}, while Validator enforces "
                            f"|a_i| <= {validator_limit}"
                        ),
                        confidence=1.0,
                        severity=Severity.HIGH,
                        verification_plan={"strategy": "source_contract_comparison"},
                        source_locations=["problem.yaml:input.a_i", validator_rel],
                    )
                )

        reference_rel = manifest.get("reference_solution")
        if reference_rel:
            reference_path = self._inside(package_root, reference_rel)
            reference_source = reference_path.read_text(encoding="utf-8")
            inspected.append(reference_rel)
            theoretical_max = int(manifest.get("output", {}).get("theoretical_max", 0))
            int_accumulators = re.findall(r"\bint\s+(best|current|answer|sum|prefix)\b", reference_source)
            if theoretical_max > 2_147_483_647 and int_accumulators:
                hypotheses.append(
                    Hypothesis(
                        id="H-OVERFLOW-001",
                        package_id=package_id,
                        run_id=run_id,
                        source_agent="solution-analyst",
                        category="integer_overflow",
                        description=(
                            f"int accumulators {sorted(set(int_accumulators))} cannot represent "
                            f"theoretical maximum {theoretical_max}"
                        ),
                        confidence=0.98,
                        severity=Severity.CRITICAL,
                        verification_plan={
                            "strategy": "extreme_case_differential_test",
                            "oracle": manifest.get("oracle"),
                        },
                        source_locations=[reference_rel, "problem.yaml:output.theoretical_max"],
                    )
                )

        test_paths = sorted((package_root / "tests").glob("*.in"))
        inspected.extend(path.relative_to(package_root).as_posix() for path in test_paths)
        input_min = int(manifest.get("input", {}).get("a_i", {}).get("min", 0))
        if input_min < 0 and test_paths and not self._contains_negative_test_value(test_paths):
            hypotheses.append(
                Hypothesis(
                    id="H-COVERAGE-001",
                    package_id=package_id,
                    run_id=run_id,
                    source_agent="adversarial-test-engineer",
                    category="missing_negative_cases",
                    description="existing tests contain no negative array values",
                    confidence=1.0,
                    severity=Severity.HIGH,
                    verification_plan={
                        "strategy": "wrong_solution_driven_search",
                        "candidates": manifest.get("known_wrong_solutions", []),
                    },
                    source_locations=[path.relative_to(package_root).as_posix() for path in test_paths],
                )
            )

        checker_rel = manifest.get("checker")
        if checker_rel:
            checker_path = self._inside(package_root, checker_rel)
            checker_source = checker_path.read_text(encoding="utf-8")
            inspected.append(checker_rel)
            checker_code = re.sub(r"//.*?$|/\*.*?\*/", "", checker_source, flags=re.MULTILINE | re.DOTALL)
            has_output_read = "output_file >>" in checker_code
            has_eof_check = any(
                marker in checker_code
                for marker in ("output_file.eof", "output_file.peek", "trailing", "extra_token")
            )
            if has_output_read and not has_eof_check:
                hypotheses.append(
                    Hypothesis(
                        id="H-CHECKER-001",
                        package_id=package_id,
                        run_id=run_id,
                        source_agent="checker-auditor",
                        category="checker_trailing_output",
                        description="Checker reads an answer token without an observable EOF check",
                        confidence=0.9,
                        severity=Severity.CRITICAL,
                        verification_plan={"strategy": "trailing_token_probe"},
                        source_locations=[checker_rel],
                    )
                )

        return BaselineAuditReport(
            package_id=package_id,
            run_id=run_id,
            hypotheses=hypotheses,
            inspected_files=sorted(set(inspected)),
        )

    @staticmethod
    def _inside(root: Path, relative_path: str) -> Path:
        target = (root / relative_path).resolve()
        if root not in target.parents or not target.is_file():
            raise ValueError(f"artifact path is unsafe or missing: {relative_path}")
        return target

    @staticmethod
    def _extract_absolute_validator_limit(source: str) -> int | None:
        match = re.search(r"(?:llabs|abs)\s*\([^)]*\)\s*>\s*(\d+)(?:LL|L)?", source)
        return int(match.group(1)) if match else None

    @staticmethod
    def _contains_negative_test_value(test_paths: list[Path]) -> bool:
        for path in test_paths:
            tokens = path.read_text(encoding="utf-8").split()
            for token in tokens[1:]:
                try:
                    if int(token) < 0:
                        return True
                except ValueError:
                    continue
        return False
