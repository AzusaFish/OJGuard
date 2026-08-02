from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from backend.app.runner import DockerRunner, JavaRuntimeProfile, RunnerSecurityError


class RecordingJavaRunner(DockerRunner):
    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.commands: list[list[str]] = []

    def _invoke(self, command: list[str], *, timeout_seconds: float) -> None:
        self.commands.append(command)
        session_mount = next(item for item in command if "dst=/session" in item)
        session = Path(session_mount.split("src=", 1)[1].split(",dst=", 1)[0])
        if "compile-java" in command:
            (session / "classes").mkdir(exist_ok=True)
            (session / "classes" / "ControlWorkload.class").write_bytes(b"compiled")
            payload = {
                "status": "OK",
                "exit_code": 0,
                "compiler_stdout": "",
                "compiler_stderr": "",
                "binary_relative_path": "classes:ControlWorkload",
                "duration_ms": 100,
            }
            (session / "result.json").write_text(json.dumps(payload), encoding="utf-8")
        else:
            profile = "degraded" if "ojguard-java-runtime:degraded-17" in command else "normal"
            payload = {
                "status": "TIME_LIMIT_EXCEEDED" if profile == "degraded" else "OK",
                "exit_code": None if profile == "degraded" else 0,
                "stdout": "" if profile == "degraded" else "123\n",
                "stderr": "",
                "duration_ms": 1000 if profile == "degraded" else 100,
                "timed_out": profile == "degraded",
                "output_truncated": False,
            }
            result_name = command[-1].rsplit("/", 1)[-1]
            (session / result_name).write_text(json.dumps(payload), encoding="utf-8")


class JavaRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(".test-tmp") / f"java-runner-{uuid4().hex}"
        self.packages = self.root / "packages"
        self.sessions = self.root / "sessions"
        source = self.packages / "runtime" / "ControlWorkload.java"
        source.parent.mkdir(parents=True)
        source.write_text("public class ControlWorkload {}", encoding="utf-8")
        self.runner = RecordingJavaRunner(
            packages_root=self.packages,
            sessions_root=self.sessions,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_normal_and_degraded_profiles_use_pinned_images(self) -> None:
        compiled, session = self.runner.compile_java(
            source_relative_path="runtime/ControlWorkload.java"
        )
        self.assertEqual(compiled.binary_relative_path, "classes:ControlWorkload")

        normal = self.runner.execute_java(
            session=session,
            main_class="ControlWorkload",
            input_payload=b"100\n",
            profile=JavaRuntimeProfile.NORMAL,
        )
        degraded = self.runner.execute_java(
            session=session,
            main_class="ControlWorkload",
            input_payload=b"100\n",
            profile=JavaRuntimeProfile.DEGRADED,
        )
        self.assertEqual(normal.status, "OK")
        self.assertEqual(degraded.status, "TIME_LIMIT_EXCEEDED")
        self.assertIn("ojguard-java-runtime:normal-17", self.runner.commands[-2])
        self.assertIn("ojguard-java-runtime:degraded-17", self.runner.commands[-1])

    def test_rejects_untrusted_main_class(self) -> None:
        _, session = self.runner.compile_java(source_relative_path="runtime/ControlWorkload.java")
        with self.assertRaises(RunnerSecurityError):
            self.runner.execute_java(
                session=session,
                main_class="ControlWorkload;sh",
                input_payload=b"",
                profile=JavaRuntimeProfile.NORMAL,
            )


if __name__ == "__main__":
    unittest.main()
