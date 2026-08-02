from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from backend.app.domain import (
    ApprovalLevel,
    ExperimentState,
    HypothesisState,
    IncidentApprovalAction,
    IncidentApprovalDecision,
    IncidentApprovalRecord,
    IncidentContext,
    IncidentProfile,
    IncidentSeverity,
    IncidentStage,
    IncidentType,
    RemediationPlan,
    RemediationStep,
    VerificationStatus,
)
from backend.app.services.incident_state_machine import transition_incident
from backend.app.services.playbooks import default_playbook_for
from backend.app.services.repository import SQLiteRepository
from backend.app.services.scenario_analysis import ScenarioAnalyzer
from backend.app.services.scenario_data import ScenarioDataGenerator
from backend.app.services.trusted_rejudge import (
    assess_impact,
    calculate_score_changes,
    complete_batch,
    plan_rejudge_batches,
    verify_rejudge,
)


class IncidentWorkflowError(ValueError):
    """Raised when a controlled incident operation violates a workflow gate."""


APPROVAL_ROLE: dict[IncidentApprovalAction, str] = {
    IncidentApprovalAction.APPROVE_REMEDIATION: "technical_approver",
    IncidentApprovalAction.RUN_CANARY_REJUDGE: "technical_approver",
    IncidentApprovalAction.RUN_BULK_REJUDGE: "business_approver",
    IncidentApprovalAction.FREEZE_RESULTS: "business_approver",
    IncidentApprovalAction.SIMULATE_SCORE_WRITEBACK: "business_approver",
    IncidentApprovalAction.PREPARE_NOTIFICATION: "business_approver",
    IncidentApprovalAction.CLOSE_INCIDENT: "business_approver",
}

APPROVAL_LEVEL: dict[IncidentApprovalAction, ApprovalLevel] = {
    IncidentApprovalAction.APPROVE_REMEDIATION: ApprovalLevel.L2,
    IncidentApprovalAction.RUN_CANARY_REJUDGE: ApprovalLevel.L2,
    IncidentApprovalAction.RUN_BULK_REJUDGE: ApprovalLevel.L3,
    IncidentApprovalAction.FREEZE_RESULTS: ApprovalLevel.L3,
    IncidentApprovalAction.SIMULATE_SCORE_WRITEBACK: ApprovalLevel.L4,
    IncidentApprovalAction.PREPARE_NOTIFICATION: ApprovalLevel.L4,
    IncidentApprovalAction.CLOSE_INCIDENT: ApprovalLevel.L3,
}

APPROVAL_STATE_KEY: dict[IncidentApprovalAction, str] = {
    IncidentApprovalAction.APPROVE_REMEDIATION: "execute_plan",
    IncidentApprovalAction.RUN_CANARY_REJUDGE: "run_canary_rejudge",
    IncidentApprovalAction.RUN_BULK_REJUDGE: "run_bulk_rejudge",
    IncidentApprovalAction.FREEZE_RESULTS: "freeze_results",
    IncidentApprovalAction.SIMULATE_SCORE_WRITEBACK: "simulate_score_writeback",
    IncidentApprovalAction.PREPARE_NOTIFICATION: "prepare_notification",
    IncidentApprovalAction.CLOSE_INCIDENT: "close_incident",
}


class IncidentWorkflowService:
    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository
        self.generator = ScenarioDataGenerator()
        self.analyzer = ScenarioAnalyzer()

    def _require_incident(self, incident_id: str) -> IncidentContext:
        incident = self.repository.get_incident(incident_id)
        if incident is None:
            raise IncidentWorkflowError("incident not found")
        return incident

    def prepare_demo(self, incident_type: IncidentType) -> IncidentContext:
        dataset = self.generator.generate(incident_type)
        playbook = default_playbook_for(incident_type)
        incident_id = f"INC-{uuid4().hex[:10].upper()}"
        incident = IncidentContext(
            incident_id=incident_id,
            profile=IncidentProfile(
                incident_type=incident_type,
                title={
                    IncidentType.RUNTIME_REGRESSION: "Java 运行时回归导致批量异常超时",
                    IncidentType.NODE_DEGRADATION: "评测节点退化导致运行错误集中",
                    IncidentType.CHECKER_DEFECT: "Checker 缺陷导致判定结果漂移",
                }[incident_type],
                summary="从异常信号到可信重评与结果验证的可复现事故演练。",
                severity=IncidentSeverity.SEV2,
                playbook_id=playbook.id,
                resource_scope={"scenario_id": dataset.scenario_id, "seed": dataset.seed},
                source_systems=["monitoring", "submission-store", "deployment-log"],
                dimensions=playbook.signal_dimensions,
            ),
        )
        self.repository.save_incident(incident)

        signals = self.analyzer.signals(incident_id, dataset)
        for signal in signals:
            self.repository.save_incident_signal(signal)
        incident.signal_ids = [item.id for item in signals]
        incident = transition_incident(incident, IncidentStage.TRIAGING)
        incident = transition_incident(incident, IncidentStage.INVESTIGATING)

        hypotheses = self.analyzer.competing_hypotheses(incident_id, dataset)
        experiment = self.analyzer.run_comparison(incident_id, dataset, hypotheses)
        primary_category = {
            IncidentType.RUNTIME_REGRESSION: "runtime_image",
            IncidentType.NODE_DEGRADATION: "judge_node",
            IncidentType.CHECKER_DEFECT: "checker",
        }[incident_type]
        for hypothesis in hypotheses:
            hypothesis.state = (
                HypothesisState.CONFIRMED
                if hypothesis.category == primary_category
                and experiment.state == ExperimentState.PASSED
                else HypothesisState.REJECTED
            )
            hypothesis.confidence = 0.96 if hypothesis.state == HypothesisState.CONFIRMED else 0.08
            hypothesis.updated_at = datetime.now(UTC)
            self.repository.save_root_cause_hypothesis(hypothesis)
        self.repository.save_incident_experiment(experiment)
        incident.active_hypothesis_ids = [item.id for item in hypotheses]
        incident.confirmed_root_cause_ids = [
            item.id for item in hypotheses if item.state == HypothesisState.CONFIRMED
        ]
        incident.experiment_ids = [experiment.id]
        incident.control_experiment_passed = experiment.state == ExperimentState.PASSED
        incident = transition_incident(incident, IncidentStage.IMPACT_ASSESSING)

        impact = assess_impact(incident_id, dataset, playbook.impact_policy)
        self.repository.save_impact_assessment(impact)
        incident.impact_assessment_id = impact.id
        incident = transition_incident(incident, IncidentStage.REMEDIATION_PLANNING)

        plan = self._build_remediation_plan(incident, impact.id)
        self.repository.save_remediation_plan(plan)
        incident.remediation_plan_ids = [plan.id]
        batches = plan_rejudge_batches(incident_id, plan.id, impact.submission_ids)
        for batch in batches:
            self.repository.save_rejudge_batch(batch)
        incident.rejudge_batch_ids = [item.id for item in batches]
        incident = transition_incident(incident, IncidentStage.APPROVAL_PENDING)
        self.repository.save_incident(incident)
        return incident

    @staticmethod
    def _build_remediation_plan(incident: IncidentContext, impact_id: str) -> RemediationPlan:
        actions = {
            IncidentType.RUNTIME_REGRESSION: ("回滚 Java 运行时镜像", "恢复已验证镜像"),
            IncidentType.NODE_DEGRADATION: ("隔离退化评测节点", "重新纳管健康节点"),
            IncidentType.CHECKER_DEFECT: ("冻结问题并切换 Checker 副本", "恢复已验证 Checker"),
        }
        action, rollback = actions[incident.profile.incident_type]
        plan_id = f"PLAN-{uuid4().hex[:10].upper()}"
        return RemediationPlan(
            id=plan_id,
            incident_id=incident.incident_id,
            title=f"{action}与分批可信重评",
            approved_impact_id=impact_id,
            steps=[
                RemediationStep(
                    id=f"{plan_id}-01",
                    action=action,
                    risk_level=ApprovalLevel.L2,
                    preconditions=["根因对照实验通过", "影响集合已固化"],
                    success_checks=["控制组结果恢复", "无跨范围回归"],
                    stop_conditions=["控制组出现新错误", "基础设施不可用"],
                    rollback_action=rollback,
                ),
                RemediationStep(
                    id=f"{plan_id}-02",
                    action="控制组、灰度组、全量组分批重评",
                    risk_level=ApprovalLevel.L3,
                    preconditions=["技术审批通过", "业务审批通过后才可全量"],
                    success_checks=["覆盖率 100%", "无重复且无越界"],
                    stop_conditions=["灰度失败率大于 0", "成绩变化超出影响集合"],
                    rollback_action="暂停后续批次并保留原始成绩快照",
                ),
            ],
        )

    def record_approval(
        self,
        incident_id: str,
        *,
        action: IncidentApprovalAction,
        role_context: str,
        actor: str,
        decision: IncidentApprovalDecision,
        reason: str | None = None,
    ) -> IncidentApprovalRecord:
        incident = self._require_incident(incident_id)
        required_role = APPROVAL_ROLE[action]
        if role_context != required_role:
            raise IncidentWorkflowError(
                f"{action.value} requires role_context={required_role}"
            )
        target_id = (
            incident.remediation_plan_ids[-1]
            if incident.remediation_plan_ids
            else incident.incident_id
        )
        approval = IncidentApprovalRecord(
            id=f"APPROVAL-{uuid4().hex[:10].upper()}",
            incident_id=incident_id,
            action=action,
            level=APPROVAL_LEVEL[action],
            decision=decision,
            role_context=role_context,
            actor=actor,
            target_id=target_id,
            reason=reason,
            decided_at=datetime.now(UTC),
        )
        self.repository.save_incident_approval(approval)
        incident.approval_state[APPROVAL_STATE_KEY[action]] = decision
        incident.updated_at = datetime.now(UTC)
        self.repository.save_incident(incident)
        return approval

    def execute_control_and_canary(self, incident_id: str) -> IncidentContext:
        incident = self._require_incident(incident_id)
        if incident.stage == IncidentStage.APPROVAL_PENDING:
            incident = transition_incident(incident, IncidentStage.EXECUTING)
        elif incident.stage != IncidentStage.EXECUTING:
            raise IncidentWorkflowError("control and canary require APPROVAL_PENDING or EXECUTING")
        if (
            incident.approval_state.get("run_canary_rejudge")
            != IncidentApprovalDecision.APPROVED
        ):
            raise IncidentWorkflowError("canary rejudge requires technical approval")

        batches = self.repository.list_rejudge_batches(incident_id)
        selected = [item for item in batches if item.kind in {"control", "canary"}]
        if not selected:
            raise IncidentWorkflowError("no control or canary batches were planned")
        for batch in selected:
            self.repository.save_rejudge_batch(complete_batch(batch))
        incident.canary_rejudge_passed = all(
            complete_batch(item).state.value == "COMPLETED" for item in selected
        )
        incident.updated_at = datetime.now(UTC)
        self.repository.save_incident(incident)
        return incident

    def execute_bulk(self, incident_id: str) -> IncidentContext:
        incident = self._require_incident(incident_id)
        if incident.stage == IncidentStage.EXECUTING:
            incident = transition_incident(incident, IncidentStage.REJUDGING)
        elif incident.stage != IncidentStage.REJUDGING:
            raise IncidentWorkflowError("bulk rejudge requires EXECUTING or REJUDGING")

        batches = self.repository.list_rejudge_batches(incident_id)
        for batch in batches:
            self.repository.save_rejudge_batch(complete_batch(batch))
        completed_batches = self.repository.list_rejudge_batches(incident_id)
        incident.rejudge_complete = all(item.state.value == "COMPLETED" for item in completed_batches)

        dataset = self.generator.generate(incident.profile.incident_type)
        impact = self.repository.list_impact_assessments(incident_id)[-1]
        existing = self.repository.list_score_changes(incident_id)
        if not existing:
            for score_change in calculate_score_changes(
                incident_id, dataset, impact.submission_ids
            ):
                self.repository.save_score_change(score_change)
        incident.score_change_ids = [
            item.id for item in self.repository.list_score_changes(incident_id)
        ]
        incident.updated_at = datetime.now(UTC)
        self.repository.save_incident(incident)
        return incident

    def verify(self, incident_id: str) -> IncidentContext:
        incident = self._require_incident(incident_id)
        if incident.stage == IncidentStage.REJUDGING:
            incident = transition_incident(incident, IncidentStage.VERIFYING)
        elif incident.stage != IncidentStage.VERIFYING:
            raise IncidentWorkflowError("verification requires REJUDGING or VERIFYING")
        impact = self.repository.list_impact_assessments(incident_id)[-1]
        verification = verify_rejudge(
            incident_id,
            impact,
            self.repository.list_rejudge_batches(incident_id),
            self.repository.list_score_changes(incident_id),
        )
        self.repository.save_incident_verification(verification)
        incident.verification_id = verification.id
        if verification.status == VerificationStatus.HUMAN_REVIEW_REQUIRED:
            incident.stage = IncidentStage.HUMAN_REVIEW_REQUIRED
        incident.updated_at = datetime.now(UTC)
        self.repository.save_incident(incident)
        return incident

    def close(self, incident_id: str) -> IncidentContext:
        incident = self._require_incident(incident_id)
        incident = transition_incident(incident, IncidentStage.RESOLVED)
        self.repository.save_incident(incident)
        return incident
