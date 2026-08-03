from pathlib import Path

from backend.app.runner import DockerRunner
from backend.app.services.demo_verifier import DemoVerifier
from backend.app.services.evidence import EvidenceStore
from backend.app.services.repository import SQLiteRepository
from backend.app.services.trace import TraceWriter


def main() -> None:
    root = Path.cwd()
    verifier = DemoVerifier(
        runner=DockerRunner(
            packages_root=root / "demo",
            sessions_root=root / "data" / "runner-sessions",
        ),
        repository=SQLiteRepository(root / "data" / "ojguard.sqlite3"),
        evidence_store=EvidenceStore(root / "artifacts"),
        trace_writer=TraceWriter(root / "artifacts"),
    )
    result = verifier.audit(root / "demo" / "maximum_segment_score")
    report_path = root / "artifacts" / result.context.package_id / result.context.run_id / "report.html"
    print(f"run_id={result.context.run_id}")
    print(f"decision={result.release_gate.decision.value}")
    print(f"findings={len(result.findings)}")
    print(f"evidence={len(result.evidence)}")
    print(f"report={report_path.resolve()}")


if __name__ == "__main__":
    main()
