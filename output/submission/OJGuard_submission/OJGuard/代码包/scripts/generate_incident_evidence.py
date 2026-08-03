from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.app.domain import (
    IncidentApprovalAction,
    IncidentApprovalDecision,
    IncidentType,
)
from backend.app.services.incident_reporting import build_incident_report, render_report_html
from backend.app.services.incident_workflow import IncidentWorkflowService
from backend.app.services.repository import SQLiteRepository


def complete_incident(workflow: IncidentWorkflowService, incident_type: IncidentType):
    incident = workflow.prepare_demo(incident_type)
    actor = "single-team-demo-operator"
    for action, role in (
        (IncidentApprovalAction.APPROVE_REMEDIATION, "technical_approver"),
        (IncidentApprovalAction.RUN_CANARY_REJUDGE, "technical_approver"),
    ):
        workflow.record_approval(
            incident.incident_id,
            action=action,
            role_context=role,
            actor=actor,
            decision=IncidentApprovalDecision.APPROVED,
            reason="确定性演示审批",
        )
    workflow.execute_control_and_canary(incident.incident_id)
    workflow.record_approval(
        incident.incident_id,
        action=IncidentApprovalAction.RUN_BULK_REJUDGE,
        role_context="business_approver",
        actor=actor,
        decision=IncidentApprovalDecision.APPROVED,
        reason="控制组与灰度批次均通过",
    )
    workflow.execute_bulk(incident.incident_id)
    workflow.verify(incident.incident_id)
    workflow.record_approval(
        incident.incident_id,
        action=IncidentApprovalAction.CLOSE_INCIDENT,
        role_context="business_approver",
        actor=actor,
        decision=IncidentApprovalDecision.APPROVED,
        reason="闭环验证通过",
    )
    return workflow.close(incident.incident_id)


def generate(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {"deterministic_seed": 20260802, "scenarios": []}
    database_path = output_dir / ".evidence.sqlite3"
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(f"{database_path}{suffix}")
        if candidate.exists():
            candidate.unlink()
    try:
        repository = SQLiteRepository(database_path)
        workflow = IncidentWorkflowService(repository)
        for incident_type in (
            IncidentType.RUNTIME_REGRESSION,
            IncidentType.NODE_DEGRADATION,
            IncidentType.CHECKER_DEFECT,
        ):
            incident = complete_incident(workflow, incident_type)
            report = build_incident_report(repository, incident)
            stem = incident_type.value.replace("_", "-")
            (output_dir / f"{stem}-report.json").write_text(
                json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (output_dir / f"{stem}-report.html").write_text(
                render_report_html(report), encoding="utf-8"
            )
            scenarios = summary["scenarios"]
            assert isinstance(scenarios, list)
            scenarios.append(
                {
                    "incident_type": incident_type.value,
                    "incident_id": incident.incident_id,
                    "stage": report.stage,
                    "root_cause": report.root_cause,
                    "impact": report.impact,
                    "rejudge": report.rejudge,
                    "verification_status": report.verification.get("status"),
                }
            )
    finally:
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(f"{database_path}{suffix}")
            if candidate.exists():
                candidate.unlink()
    (output_dir / "scenario-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 OJGuard 三类事故的确定性闭环证据")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/evidence/incidents"),
        help="JSON/HTML 证据输出目录",
    )
    args = parser.parse_args()
    summary = generate(args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
