from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.app.runner import DockerRunner
from backend.app.services.java_regression_experiment import JavaRegressionExperiment


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the isolated Java runtime comparison")
    parser.add_argument("--iterations", type=int, default=12_000_000)
    parser.add_argument("--time-limit-ms", type=int, default=80)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    runner = DockerRunner(
        packages_root=root / "demo" / "incidents",
        sessions_root=root / ".runtime" / "java-sessions",
    )
    result = JavaRegressionExperiment(runner).run(
        iterations=args.iterations,
        time_limit_ms=args.time_limit_ms,
        repetitions=args.repetitions,
    )
    content = json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2)
    if args.output:
        output = args.output if args.output.is_absolute() else root / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
    print(content)
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
