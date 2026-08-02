import tempfile
import unittest
from pathlib import Path

from backend.app.domain import PatchStatus, RunStage, TaskContext
from backend.app.services.patch_workflow import PatchWorkflow, PatchWorkflowError
from backend.app.services.repository import SQLiteRepository


class PatchWorkflowTests(unittest.TestCase):
    @staticmethod
    def temporary_directory():
        base = Path.cwd() / ".test-tmp"
        base.mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(dir=base)

    @staticmethod
    def make_demo(root: Path) -> None:
        files = {
            "solutions/reference.cpp": (
                "int best = std::numeric_limits<int>::lowest();\n"
                "int current = 0;\n"
                "int value;\n        std::cin >> value;\n"
            ),
            "validators/validator.cpp": "std::llabs(value) > 1000000LL\n",
            "checker/checker.cpp": (
                "// Intentional defect: trailing contestant output is not rejected.\n"
                "    return expected == actual ? 0 : 1;\n"
            ),
        }
        for relative, content in files.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    def test_candidate_does_not_modify_original_and_requires_approval(self) -> None:
        with self.temporary_directory() as directory:
            root = Path(directory)
            original = root / "original"
            self.make_demo(original)
            repository = SQLiteRepository(root / "ojguard.sqlite3")
            repository.save_run(
                TaskContext(
                    task_id="TASK-1",
                    package_id="demo",
                    run_id="RUN-1",
                    stage=RunStage.BLOCKED,
                    confirmed_finding_ids=["F-1"],
                )
            )
            workflow = PatchWorkflow(
                repository=repository, workspaces_root=root / "workspaces"
            )
            before = (original / "solutions/reference.cpp").read_text(encoding="utf-8")
            patch = workflow.propose_demo_patch(run_id="RUN-1", original_root=original)
            self.assertEqual(patch.status, PatchStatus.CANDIDATE)
            self.assertEqual(
                (original / "solutions/reference.cpp").read_text(encoding="utf-8"), before
            )
            self.assertFalse((root / "workspaces" / "RUN-1").exists())

            applied = workflow.approve_and_apply(
                patch_id=patch.id,
                original_root=original,
                actor="unit-test",
                reason="simulated approval",
            )
            self.assertEqual(applied.status, PatchStatus.APPLIED)
            self.assertTrue((root / "workspaces" / "RUN-1" / "tests/002.in").is_file())
            self.assertEqual(
                (original / "solutions/reference.cpp").read_text(encoding="utf-8"), before
            )
            self.assertEqual(len(repository.list_approvals("RUN-1")), 1)
            self.assertEqual(repository.get_run("RUN-1").stage, RunStage.REVALIDATING)

    def test_cannot_apply_without_pending_state(self) -> None:
        with self.temporary_directory() as directory:
            root = Path(directory)
            repository = SQLiteRepository(root / "ojguard.sqlite3")
            workflow = PatchWorkflow(
                repository=repository, workspaces_root=root / "workspaces"
            )
            with self.assertRaises(PatchWorkflowError):
                workflow.approve_and_apply(
                    patch_id="missing",
                    original_root=root,
                    actor="unit-test",
                )


if __name__ == "__main__":
    unittest.main()
