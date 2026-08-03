from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from backend.app.runner import DockerRunner
from backend.app.services.java_regression_experiment import JavaRegressionExperiment


class ComparisonRunner(DockerRunner):
    def _invoke(self, command: list[str], *, timeout_seconds: float) -> None:
        session_mount = next(item for item in command if "dst=/session" in item)
        session = Path(session_mount.split("src=", 1)[1].split(",dst=", 1)[0])
        if "compile-java" in command:
            (session / "classes").mkdir(exist_ok=True)
            payload = {
                "status": "OK",
                "exit_code": 0,
                "compiler_stdout": "",
                "compiler_stderr": "",
                "binary_relative_path": "classes:ControlWorkload",
                "duration_ms": 80,
            }
            (session / "result.json").write_text(json.dumps(payload), encoding="utf-8")
            return

        degraded = "ojguard-java-runtime:degraded-17" in command
        payload = {
            "status": "TIME_LIMIT_EXCEEDED" if degraded else "OK",
            "exit_code": None if degraded else 0,
            "stdout": "" if degraded else "123\n",
            "stderr": "",
            "duration_ms": 80 if degraded else 40,
            "timed_out": degraded,
            "output_truncated": False,
        }
        result_name = command[-1].rsplit("/", 1)[-1]
        (session / result_name).write_text(json.dumps(payload), encoding="utf-8")


class JavaRegressionExperimentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(".test-tmp") / f"java-experiment-{uuid4().hex}"
        source = self.root / "packages" / "runtime_regression" / "ControlWorkload.java"
        source.parent.mkdir(parents=True)
        source.write_text("public class ControlWorkload {}", encoding="utf-8")
        self.runner = ComparisonRunner(
            packages_root=self.root / "packages",
            sessions_root=self.root / "sessions",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_reproducible_control_experiment_passes(self) -> None:
        result = JavaRegressionExperiment(self.runner).run(repetitions=3)
        self.assertTrue(result.passed)
        self.assertEqual(result.normal_pass_rate, 1)
        self.assertEqual(result.degraded_timeout_rate, 1)
        self.assertEqual(len(result.normal_runs), 3)
        self.assertEqual(len(result.degraded_runs), 3)

    def test_repetitions_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            JavaRegressionExperiment(self.runner).run(repetitions=0)


if __name__ == "__main__":
    unittest.main()
