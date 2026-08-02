import tempfile
import unittest
from pathlib import Path

from backend.app.domain import AgentEvent
from backend.app.services.trace import TraceWriter


class TraceWriterTests(unittest.TestCase):
    @staticmethod
    def temporary_directory() -> tempfile.TemporaryDirectory[str]:
        base = Path(".test-tmp")
        base.mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(dir=base)

    def test_append_only_event_replay(self) -> None:
        with self.temporary_directory() as directory:
            writer = TraceWriter(Path(directory))
            first = AgentEvent(
                id="AE-1",
                task_id="T-1",
                run_id="R-1",
                agent="judge-manager",
                event_type="task_created",
                summary="created",
            )
            second = AgentEvent(
                id="AE-2",
                task_id="T-1",
                run_id="R-1",
                agent="solution-analyst",
                event_type="hypothesis_created",
                summary="overflow risk",
            )
            writer.append("P-1", first)
            writer.append("P-1", second)
            self.assertEqual(writer.read("P-1", "R-1"), [first, second])


if __name__ == "__main__":
    unittest.main()
