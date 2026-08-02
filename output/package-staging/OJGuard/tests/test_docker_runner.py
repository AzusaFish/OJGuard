import unittest
from pathlib import Path

from backend.app.runner import DockerRunner, RunnerSecurityError


class DockerRunnerSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path.cwd().resolve()
        self.runner = DockerRunner(
            packages_root=self.root / "demo",
            sessions_root=self.root / ".test-tmp" / "runner-sessions",
        )

    def test_resolves_source_under_packages_root(self) -> None:
        source = self.runner.resolve_source("maximum_segment_score/solutions/oracle.cpp")
        self.assertTrue(source.name == "oracle.cpp")
        self.assertIn("maximum_segment_score", source.parts)

    def test_rejects_source_outside_packages_root(self) -> None:
        with self.assertRaises(RunnerSecurityError):
            self.runner.resolve_source("../.env")


if __name__ == "__main__":
    unittest.main()
