import hashlib
from pathlib import Path

from backend.app.domain import PatchStatus
from backend.app.runner import DockerRunner
from backend.app.services.demo_verifier import DemoVerifier
from backend.app.services.evidence import EvidenceStore
from backend.app.services.patch_workflow import PatchWorkflow
from backend.app.services.repository import SQLiteRepository
from backend.app.services.trace import TraceWriter


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> None:
    root = Path.cwd()
    original = root / "demo" / "maximum_segment_score"
    repository = SQLiteRepository(root / "data" / "ojguard.sqlite3")
    verifier = DemoVerifier(
        runner=DockerRunner(
            packages_root=root / "demo",
            sessions_root=root / "data" / "runner-sessions",
        ),
        repository=repository,
        evidence_store=EvidenceStore(root / "artifacts"),
        trace_writer=TraceWriter(root / "artifacts"),
    )
    before = tree_hash(original)
    audit = verifier.audit(original)
    workflow = PatchWorkflow(
        repository=repository,
        workspaces_root=root / "data" / "workspaces",
    )
    patch = workflow.propose_demo_patch(run_id=audit.context.run_id, original_root=original)
    workflow.approve_and_apply(
        patch_id=patch.id,
        original_root=original,
        actor="automated-integration-test",
        reason="Simulation only; not a production human approval.",
    )
    regression = workflow.run_demo_regression(patch_id=patch.id)
    if not regression.passed:
        raise RuntimeError(regression.model_dump_json(indent=2))
    workflow.confirm_release(
        patch_id=patch.id,
        actor="automated-integration-test",
        reason="Simulation only; verifies the second-approval gate.",
    )
    after = tree_hash(original)
    if before != after:
        raise RuntimeError("immutable original Demo changed during patch workflow")
    context = repository.get_run(audit.context.run_id)
    persisted_patch = repository.get_patch(patch.id)
    if persisted_patch is None or persisted_patch.status != PatchStatus.RELEASE_CONFIRMED:
        raise RuntimeError("patch did not reach RELEASE_CONFIRMED")
    print(f"run_id={audit.context.run_id}")
    print(f"patch_id={patch.id}")
    print(f"regression_checks={len(regression.checks)}")
    print(f"original_unchanged={before == after}")
    print(f"final_stage={context.stage.value if context else 'MISSING'}")
    print(f"patch_status={persisted_patch.status.value}")
    print("patch_workflow_smoke=PASS")


if __name__ == "__main__":
    main()
