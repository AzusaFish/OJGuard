import tempfile
import unittest
from pathlib import Path

from backend.app.domain import (
    AgentEvent,
    ConfidenceClass,
    Evidence,
    Finding,
    Severity,
    TaskContext,
)
from backend.app.services.repository import SQLiteRepository


class RepositoryTests(unittest.TestCase):
    @staticmethod
    def temporary_directory() -> tempfile.TemporaryDirectory[str]:
        base = Path(".test-tmp")
        base.mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(dir=base)

    def test_persists_run_event_finding_and_evidence(self) -> None:
        with self.temporary_directory() as directory:
            repository = SQLiteRepository(Path(directory) / "ojguard.sqlite3")
            context = TaskContext(task_id="T-1", package_id="P-1", run_id="R-1")
            repository.save_run(context)
            repository.append_event(
                AgentEvent(
                    id="AE-1",
                    task_id="T-1",
                    run_id="R-1",
                    agent="judge-manager",
                    event_type="task_created",
                    summary="Task created",
                )
            )
            repository.save_finding(
                Finding(
                    id="F-1",
                    package_id="P-1",
                    run_id="R-1",
                    source_agent="solution-analyst",
                    category="integer_overflow",
                    severity=Severity.CRITICAL,
                    confidence_class=ConfidenceClass.CONFIRMED,
                    description="confirmed overflow",
                )
            )
            repository.save_evidence(
                Evidence(
                    id="EV-1",
                    package_id="P-1",
                    run_id="R-1",
                    type="differential_execution",
                    producer="runner",
                    artifact_path="P-1/R-1/EV-1.json",
                    sha256="0" * 64,
                    tool_version="0.1.0",
                )
            )

            self.assertEqual(repository.get_run("R-1"), context)
            self.assertEqual(len(repository.list_events("R-1")), 1)
            self.assertEqual(len(repository.list_findings("R-1")), 1)
            self.assertEqual(len(repository.list_evidence("R-1")), 1)


if __name__ == "__main__":
    unittest.main()
