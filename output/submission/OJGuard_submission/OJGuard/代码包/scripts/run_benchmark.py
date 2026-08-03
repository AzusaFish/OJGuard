from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

import yaml

from backend.app.services.baseline_audit import BaselineAuditor

ORACLE = """#include <algorithm>
#include <iostream>
#include <limits>
int main() {
    int n; std::cin >> n;
    long long best = std::numeric_limits<long long>::lowest(), current = 0;
    for (int i = 0; i < n; ++i) {
        long long value; std::cin >> value;
        current = std::max(value, current + value);
        best = std::max(best, current);
    }
    std::cout << best << '\\n';
}
"""


def reference_source(uses_int: bool) -> str:
    value_type = "int" if uses_int else "long long"
    limits_type = "int" if uses_int else "long long"
    return f"""#include <algorithm>
#include <iostream>
#include <limits>
int main() {{
    int n; std::cin >> n;
    {value_type} best = std::numeric_limits<{limits_type}>::lowest();
    {value_type} current = 0;
    for (int i = 0; i < n; ++i) {{
        {value_type} value; std::cin >> value;
        current = std::max(value, current + value);
        best = std::max(best, current);
    }}
    std::cout << best << '\\n';
}}
"""


def validator_source(limit: int) -> str:
    return f"""#include <cstdlib>
#include <iostream>
int main() {{
    int n; if (!(std::cin >> n) || n < 1 || n > 1000) return 1;
    for (int i = 0; i < n; ++i) {{
        long long value; if (!(std::cin >> value)) return 1;
        if (std::llabs(value) > {limit}LL) return 1;
    }}
    std::string trailing; if (std::cin >> trailing) return 1;
    return 0;
}}
"""


def checker_source(checks_eof: bool) -> str:
    eof = "std::string trailing; if (output_file >> trailing) return 1;" if checks_eof else ""
    return f"""#include <fstream>
#include <string>
int main(int argc, char** argv) {{
    if (argc != 3) return 2;
    std::ifstream answer_file(argv[1]), output_file(argv[2]);
    long long expected, actual;
    if (!(answer_file >> expected) || !(output_file >> actual)) return 2;
    {eof}
    return expected == actual ? 0 : 1;
}}
"""


def write_package(root: Path, case: dict) -> None:
    root.mkdir(parents=True, exist_ok=True)
    value_min = int(case["value_min"])
    value_max = int(case["value_max"])
    validator_limit = int(case.get("validator_limit", max(abs(value_min), abs(value_max))))
    manifest = {
        "name": case["title"],
        "format_version": 1,
        "language": "cpp17",
        "input": {
            "n": {"type": "integer", "min": 1, "max": 1000},
            "a_i": {"type": "integer", "min": value_min, "max": value_max},
        },
        "output": {
            "type": "integer",
            "theoretical_max": int(case.get("theoretical_max", 1_000_000_000)),
        },
        "validator": "validators/validator.cpp",
        "checker": "checker/checker.cpp",
        "oracle": "solutions/oracle.cpp",
        "reference_solution": "solutions/reference.cpp",
        "known_wrong_solutions": ["solutions/wrong.cpp"],
    }
    files = {
        "problem.yaml": yaml.safe_dump(manifest, sort_keys=False),
        "statement.md": f"# {case['title']}\n\nOriginal OJGuard benchmark case.\n",
        "validators/validator.cpp": validator_source(validator_limit),
        "checker/checker.cpp": checker_source(bool(case.get("checker_checks_eof", True))),
        "solutions/oracle.cpp": ORACLE,
        "solutions/reference.cpp": reference_source(bool(case.get("reference_uses_int", False))),
        "solutions/wrong.cpp": "int main() { return 0; }\n",
        "tests/001.in": "3\n5 -100 6\n" if case.get("test_has_negative") else "3\n1 2 3\n",
        "tests/001.ans": "6\n",
    }
    for relative, content in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")


def ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def main() -> None:
    workspace = Path.cwd()
    definition = yaml.safe_load(
        (workspace / "benchmark" / "cases.yaml").read_text(encoding="utf-8")
    )
    generated_root = workspace / "data" / "benchmark" / "packages"
    rows: list[dict] = []
    true_positive = false_positive = false_negative = 0
    clean_count = clean_blocked = 0
    durations: list[float] = []
    for case in definition["cases"]:
        package_root = generated_root / case["package_id"]
        write_package(package_root, case)
        started = perf_counter()
        report = BaselineAuditor().audit(
            package_root,
            package_id=case["package_id"],
            run_id=f"BENCH-RUN-{case['package_id']}",
        )
        elapsed_ms = (perf_counter() - started) * 1000
        durations.append(elapsed_ms)
        expected = set(case.get("defects", []))
        observed = {item.category for item in report.hypotheses}
        true_positive += len(expected & observed)
        false_positive += len(observed - expected)
        false_negative += len(expected - observed)
        if case.get("clean_package", False):
            clean_count += 1
            clean_blocked += bool(observed)
        rows.append(
            {
                "package_id": case["package_id"],
                "clean_package": bool(case.get("clean_package", False)),
                "expected": sorted(expected),
                "observed": sorted(observed),
                "matched": expected == observed,
                "duration_ms": round(elapsed_ms, 3),
            }
        )
    durations_sorted = sorted(durations)
    p95_index = max(0, min(len(durations_sorted) - 1, int(len(durations_sorted) * 0.95) - 1))
    output = {
        "benchmark_version": definition["version"],
        "scope": "deterministic_baseline_only",
        "case_count": len(rows),
        "defect_count": true_positive + false_negative,
        "metrics": {
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
            "precision": ratio(true_positive, true_positive + false_positive),
            "recall": ratio(true_positive, true_positive + false_negative),
            "clean_package_false_block_rate": ratio(clean_blocked, clean_count),
            "mean_duration_ms": round(sum(durations) / len(durations), 3),
            "p95_duration_ms": round(durations_sorted[p95_index], 3),
            "llm_calls": 0,
        },
        "cases": rows,
    }
    target = workspace / "benchmark" / "results" / "baseline_report.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output["metrics"], ensure_ascii=False))
    print(f"report={target.resolve()}")


if __name__ == "__main__":
    main()
