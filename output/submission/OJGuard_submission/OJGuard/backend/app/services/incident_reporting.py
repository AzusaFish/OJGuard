from __future__ import annotations

from datetime import UTC, datetime
from html import escape
from typing import Any

from pydantic import BaseModel, Field

from backend.app.domain import IncidentContext
from backend.app.services.repository import SQLiteRepository


class IncidentReport(BaseModel):
    incident_id: str
    title: str
    incident_type: str
    severity: str
    stage: str
    generated_at: datetime
    root_cause: str
    impact: dict[str, int | list[str]]
    remediation: list[str]
    approvals: list[dict[str, str | None]]
    rejudge: dict[str, int | float | bool]
    verification: dict[str, Any]
    score_change_samples: list[dict[str, int | float | str | bool | None]]
    operation_note: str = Field(min_length=1)


def build_incident_report(
    repository: SQLiteRepository, incident: IncidentContext
) -> IncidentReport:
    incident_id = incident.incident_id
    hypotheses = repository.list_root_cause_hypotheses(incident_id)
    confirmed = [item for item in hypotheses if item.id in incident.confirmed_root_cause_ids]
    impacts = repository.list_impact_assessments(incident_id)
    plans = repository.list_remediation_plans(incident_id)
    approvals = repository.list_incident_approvals(incident_id)
    batches = repository.list_rejudge_batches(incident_id)
    score_changes = repository.list_score_changes(incident_id)
    verifications = repository.list_incident_verifications(incident_id)
    impact = impacts[-1] if impacts else None
    verification = verifications[-1] if verifications else None
    planned = sum(item.planned_count for item in batches)
    completed = sum(item.completed_count for item in batches)

    return IncidentReport(
        incident_id=incident_id,
        title=incident.profile.title,
        incident_type=incident.profile.incident_type.value,
        severity=incident.profile.severity.value,
        stage=incident.stage.value,
        generated_at=datetime.now(UTC),
        root_cause=confirmed[0].statement if confirmed else "尚未确认",
        impact={
            "candidate_count": impact.affected_candidate_count if impact else 0,
            "submission_count": impact.affected_submission_count if impact else 0,
            "projected_score_change_count": (
                impact.projected_score_change_count if impact else 0
            ),
            "projected_advancement_change_count": (
                impact.projected_advancement_change_count if impact else 0
            ),
            "problems": impact.problem_ids if impact else [],
            "languages": impact.languages if impact else [],
        },
        remediation=[step.action for plan in plans for step in plan.steps],
        approvals=[
            {
                "action": item.action.value,
                "level": item.level.value,
                "decision": item.decision.value,
                "role_context": item.role_context,
                "actor": item.actor,
                "reason": item.reason,
            }
            for item in approvals
        ],
        rejudge={
            "batch_count": len(batches),
            "planned_count": planned,
            "completed_count": completed,
            "coverage_rate": completed / planned if planned else 0,
            "complete": incident.rejudge_complete,
        },
        verification=(
            verification.model_dump(mode="json")
            if verification
            else {"status": "NOT_STARTED", "summary": "尚未执行闭环验证"}
        ),
        score_change_samples=[
            item.model_dump(
                mode="json",
                include={
                    "candidate_id",
                    "before_score",
                    "after_score",
                    "before_rank",
                    "after_rank",
                    "advancement_changed",
                },
            )
            for item in score_changes[:20]
        ],
        operation_note=(
            "本演示由单人团队操作；技术审批与业务审批是可审计的角色上下文切换，"
            "不代表真实多人组织签批。"
        ),
    )


def render_report_html(report: IncidentReport) -> str:
    impact = report.impact
    verification_status = str(report.verification.get("status", "NOT_STARTED"))
    rows = "".join(
        "<tr>"
        f"<td>{escape(str(item['candidate_id']))}</td>"
        f"<td>{item['before_score']}</td><td>{item['after_score']}</td>"
        f"<td>{item['before_rank']}</td><td>{item['after_rank']}</td>"
        "</tr>"
        for item in report.score_change_samples
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{escape(report.incident_id)} 事故报告</title>
<style>
body{{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;margin:0;background:#f4f7fb;color:#10213a}}
main{{max-width:1040px;margin:32px auto;padding:0 20px}} header,.card{{background:white;border:1px solid #dce4ef;border-radius:14px;padding:22px;margin-bottom:16px}}
h1{{font-size:25px;margin:0 0 8px}} h2{{font-size:17px;margin:0 0 12px}} .meta{{color:#5c6b80}} .grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
.metric{{background:#f7f9fc;border-radius:10px;padding:14px}} .metric b{{display:block;font-size:24px;margin-top:5px}}
table{{width:100%;border-collapse:collapse}} th,td{{padding:9px;border-bottom:1px solid #e6ebf2;text-align:left}}
.ok{{color:#087a55;font-weight:700}} .note{{font-size:13px;color:#5c6b80}}
</style></head><body><main>
<header><h1>{escape(report.title)}</h1><div class="meta">{escape(report.incident_id)} · {escape(report.severity)} · {escape(report.stage)}</div></header>
<section class="card"><h2>根因结论</h2><p>{escape(report.root_cause)}</p></section>
<section class="card"><h2>影响与重评</h2><div class="grid">
<div class="metric">受影响选手<b>{impact['candidate_count']}</b></div>
<div class="metric">受影响提交<b>{impact['submission_count']}</b></div>
<div class="metric">已重评<b>{report.rejudge['completed_count']}</b></div>
<div class="metric">覆盖率<b>{float(report.rejudge['coverage_rate']):.1%}</b></div>
</div></section>
<section class="card"><h2>验证结果</h2><p class="ok">{escape(verification_status)}</p><p>{escape(str(report.verification.get('summary', '')))}</p></section>
<section class="card"><h2>成绩变化样例</h2><table><thead><tr><th>选手</th><th>原成绩</th><th>新成绩</th><th>原排名</th><th>新排名</th></tr></thead><tbody>{rows}</tbody></table></section>
<p class="note">{escape(report.operation_note)}</p>
</main></body></html>"""
