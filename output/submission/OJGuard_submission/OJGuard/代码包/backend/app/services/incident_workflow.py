from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from backend.app.domain import (
    ApprovalLevel,
    ExperimentCandidate,
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
    RejudgeBatchState,
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
    fail_batch,
    plan_recovery_canary_batch,
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

    def start_triage_demo(self, incident_type: IncidentType) -> IncidentContext:
        """Create only the observable incident input used by live AgentTeams orchestration."""
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
        self.repository.save_incident(incident)
        return incident

    def begin_investigation(self, incident_id: str) -> IncidentContext:
        """Advance normalized signals into investigation without precomputing a diagnosis."""
        incident = self._require_incident(incident_id)
        if incident.stage == IncidentStage.TRIAGING:
            incident = transition_incident(incident, IncidentStage.INVESTIGATING)
            self.repository.save_incident(incident)
        elif incident.stage != IncidentStage.INVESTIGATING:
            raise IncidentWorkflowError("signal triage requires TRIAGING or INVESTIGATING")
        return incident

    def list_experiment_candidates(self, incident_id: str) -> list[ExperimentCandidate]:
        incident = self._require_incident(incident_id)
        if incident.stage != IncidentStage.INVESTIGATING:
            return []
        hypotheses = self.repository.list_root_cause_hypotheses(incident_id)
        if not hypotheses:
            return []
        dataset = self.generator.generate(incident.profile.incident_type)
        executed = {
            item.kind for item in self.repository.list_incident_experiments(incident_id)
        }
        return [
            item
            for item in self.analyzer.experiment_candidates(dataset, hypotheses)
            if item.kind not in executed
        ]

    def run_root_cause_analysis(
        self,
        incident_id: str,
        experiment_kind: str | None = None,
    ) -> IncidentContext:
        """Persist competing hypotheses and their deterministic comparison experiment."""
        incident = self._require_incident(incident_id)
        if incident.stage not in {
            IncidentStage.INVESTIGATING,
            IncidentStage.IMPACT_ASSESSING,
        }:
            existing = self.repository.list_incident_experiments(incident_id)
            if existing and incident.confirmed_root_cause_ids:
                return incident
            raise IncidentWorkflowError(
                "root-cause analysis requires INVESTIGATING"
            )

        if incident.confirmed_root_cause_ids:
            return incident

        hypotheses = self.repository.list_root_cause_hypotheses(incident_id)
        if not hypotheses:
            incident = self.propose_root_cause_hypotheses(incident_id)
            hypotheses = self.repository.list_root_cause_hypotheses(incident_id)

        dataset = self.generator.generate(incident.profile.incident_type)
        selected_kind = experiment_kind or self.analyzer._experiment_kind(
            incident.profile.incident_type
        )
        existing_experiment = next(
            (
                item
                for item in self.repository.list_incident_experiments(incident_id)
                if item.kind == selected_kind
            ),
            None,
        )
        if existing_experiment is not None:
            return incident
        experiment = self.analyzer.run_comparison(
            incident_id,
            dataset,
            hypotheses,
            selected_kind,
        )
        primary_category = {
            IncidentType.RUNTIME_REGRESSION: "runtime_image",
            IncidentType.NODE_DEGRADATION: "judge_node",
            IncidentType.CHECKER_DEFECT: "checker",
        }[incident.profile.incident_type]
        for hypothesis in hypotheses:
            if experiment.state == ExperimentState.PASSED:
                hypothesis.state = (
                    HypothesisState.CONFIRMED
                    if hypothesis.category == primary_category
                    else HypothesisState.REJECTED
                )
                hypothesis.confidence = (
                    0.96 if hypothesis.state == HypothesisState.CONFIRMED else 0.08
                )
            else:
                hypothesis.state = HypothesisState.INCONCLUSIVE
                hypothesis.confidence = 0.5
            hypothesis.updated_at = datetime.now(UTC)
            self.repository.save_root_cause_hypothesis(hypothesis)
        experiment.started_at = datetime.now(UTC)
        experiment.completed_at = datetime.now(UTC)
        self.repository.save_incident_experiment(experiment)
        incident.active_hypothesis_ids = [item.id for item in hypotheses]
        incident.confirmed_root_cause_ids = [
            item.id for item in hypotheses if item.state == HypothesisState.CONFIRMED
        ]
        incident.experiment_ids = [*incident.experiment_ids, experiment.id]
        incident.control_experiment_passed = experiment.state == ExperimentState.PASSED
        if experiment.state == ExperimentState.PASSED:
            incident = transition_incident(incident, IncidentStage.IMPACT_ASSESSING)
        else:
            question = f"实验 {selected_kind} 无法区分竞争假设，需要选择补充实验"
            if question not in incident.open_questions:
                incident.open_questions.append(question)
        self.repository.save_incident(incident)
        return incident

    def propose_root_cause_hypotheses(self, incident_id: str) -> IncidentContext:
        """Persist competing hypotheses without executing or precomputing the experiment."""
        incident = self._require_incident(incident_id)
        if incident.stage != IncidentStage.INVESTIGATING:
            raise IncidentWorkflowError("hypothesis proposal requires INVESTIGATING")
        existing = self.repository.list_root_cause_hypotheses(incident_id)
        if existing:
            return incident

        dataset = self.generator.generate(incident.profile.incident_type)
        hypotheses = self.analyzer.competing_hypotheses(incident_id, dataset)
        for hypothesis in hypotheses:
            self.repository.save_root_cause_hypothesis(hypothesis)
        incident.active_hypothesis_ids = [item.id for item in hypotheses]
        incident.updated_at = datetime.now(UTC)
        self.repository.save_incident(incident)
        return incident

    def calculate_impact(self, incident_id: str) -> IncidentContext:
        """Calculate and freeze the exact impact set only after root-cause confirmation."""
        incident = self._require_incident(incident_id)
        if incident.impact_assessment_id:
            return incident
        if incident.stage != IncidentStage.IMPACT_ASSESSING:
            raise IncidentWorkflowError("impact calculation requires IMPACT_ASSESSING")

        dataset = self.generator.generate(incident.profile.incident_type)
        playbook = default_playbook_for(incident.profile.incident_type)
        impact = assess_impact(incident_id, dataset, playbook.impact_policy)
        self.repository.save_impact_assessment(impact)
        incident.impact_assessment_id = impact.id
        incident = transition_incident(incident, IncidentStage.REMEDIATION_PLANNING)
        self.repository.save_incident(incident)
        return incident

    def create_remediation_plan(self, incident_id: str) -> IncidentContext:
        """Create a gated plan and batches without granting execution permission."""
        incident = self._require_incident(incident_id)
        if incident.remediation_plan_ids:
            return incident
        if incident.stage != IncidentStage.REMEDIATION_PLANNING:
            raise IncidentWorkflowError(
                "remediation planning requires REMEDIATION_PLANNING"
            )
        if not incident.impact_assessment_id:
            raise IncidentWorkflowError("remediation planning requires frozen impact")

        impacts = self.repository.list_impact_assessments(incident_id)
        if not impacts:
            raise IncidentWorkflowError("remediation planning requires frozen impact")
        impact = impacts[-1]
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

    def prepare_demo(self, incident_type: IncidentType) -> IncidentContext:
        """Build the deterministic browser demo while reusing incremental operations."""
        incident = self.start_triage_demo(incident_type)
        incident = self.begin_investigation(incident.incident_id)
        incident = self.run_root_cause_analysis(incident.incident_id)
        incident = self.calculate_impact(incident.incident_id)
        return self.create_remediation_plan(incident.incident_id)

    def revise_plan_after_canary_failure(self, incident_id: str) -> IncidentContext:
        incident = self._require_incident(incident_id)
        if incident.stage != IncidentStage.PAUSED:
            raise IncidentWorkflowError("recovery planning requires PAUSED")
        failed_batches = [
            item
            for item in self.repository.list_rejudge_batches(incident_id)
            if item.kind in {"canary", "canary_retry"}
            and item.state == RejudgeBatchState.FAILED
        ]
        if not failed_batches:
            raise IncidentWorkflowError("no failed canary batch requires recovery")
        failed = failed_batches[-1]
        previous_plan = self.repository.list_remediation_plans(incident_id)[-1]
        recovery_plan = self._build_recovery_plan(incident, previous_plan, failed.id)
        recovery_batch = plan_recovery_canary_batch(
            incident_id,
            recovery_plan.id,
            failed,
        )
        failed.state = RejudgeBatchState.ROLLED_BACK
        failed.superseded_by_batch_id = recovery_batch.id
        failed.updated_at = datetime.now(UTC)
        self.repository.save_rejudge_batch(failed)
        self.repository.save_remediation_plan(recovery_plan)
        self.repository.save_rejudge_batch(recovery_batch)
        incident.remediation_plan_ids.append(recovery_plan.id)
        incident.rejudge_batch_ids.append(recovery_batch.id)
        incident.approval_state["execute_plan"] = IncidentApprovalDecision.REVOKED
        incident.approval_state["run_canary_rejudge"] = IncidentApprovalDecision.REVOKED
        incident.canary_rejudge_passed = False
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

    @staticmethod
    def _build_recovery_plan(
        incident: IncidentContext,
        previous_plan: RemediationPlan,
        failed_batch_id: str,
    ) -> RemediationPlan:
        plan_id = f"PLAN-{uuid4().hex[:10].upper()}"
        return RemediationPlan(
            id=plan_id,
            incident_id=incident.incident_id,
            title="灰度失败后的隔离、复核与受控恢复",
            approved_impact_id=previous_plan.approved_impact_id,
            revision=previous_plan.revision + 1,
            supersedes_plan_id=previous_plan.id,
            reason=f"灰度批次 {failed_batch_id} 触发停止条件",
            steps=[
                RemediationStep(
                    id=f"{plan_id}-01",
                    action="隔离失败执行环境并保留原始证据",
                    risk_level=ApprovalLevel.L2,
                    preconditions=["灰度批次已暂停", "失败样本和环境指纹已保存"],
                    success_checks=["失败环境已隔离", "影响集合哈希未变化"],
                    stop_conditions=["无法确认隔离边界", "影响集合发生漂移"],
                    rollback_action="保持 PAUSED 并转人工复核",
                ),
                RemediationStep(
                    id=f"{plan_id}-02",
                    action="在修复环境重试原灰度集合",
                    risk_level=ApprovalLevel.L2,
                    preconditions=["新计划重新获得技术审批"],
                    success_checks=["重试批次零失败", "未产生重复或越界执行"],
                    stop_conditions=["任一重试提交失败", "幂等键或范围不一致"],
                    rollback_action="撤销恢复批次并维持原始结果",
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

    def execute_control_and_canary(
        self,
        incident_id: str,
        *,
        inject_canary_failure: bool = False,
    ) -> IncidentContext:
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
        active_plan_id = incident.remediation_plan_ids[-1]
        selected = [
            item
            for item in batches
            if item.plan_id == active_plan_id
            and item.kind in {"control", "canary", "canary_retry"}
            and item.state not in {RejudgeBatchState.COMPLETED, RejudgeBatchState.ROLLED_BACK}
        ]
        if not selected:
            if incident.canary_rejudge_passed:
                return incident
            raise IncidentWorkflowError("no active control or canary batches were planned")
        for batch in selected:
            if inject_canary_failure and batch.kind in {"canary", "canary_retry"}:
                self.repository.save_rejudge_batch(
                    fail_batch(batch, "injected canary mismatch for recovery verification")
                )
                incident.canary_rejudge_passed = False
                incident = transition_incident(incident, IncidentStage.PAUSED)
                incident.open_questions.append(
                    "灰度结果与控制组不一致，需要隔离失败环境并生成恢复计划"
                )
                incident.updated_at = datetime.now(UTC)
                self.repository.save_incident(incident)
                return incident
            self.repository.save_rejudge_batch(complete_batch(batch))
        active_batches = [
            item
            for item in self.repository.list_rejudge_batches(incident_id)
            if item.plan_id == active_plan_id
            and item.kind in {"control", "canary", "canary_retry"}
            and item.state != RejudgeBatchState.ROLLED_BACK
        ]
        incident.canary_rejudge_passed = bool(active_batches) and all(
            item.state == RejudgeBatchState.COMPLETED for item in active_batches
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
            if batch.kind == "bulk":
                self.repository.save_rejudge_batch(complete_batch(batch))
        completed_batches = self.repository.list_rejudge_batches(incident_id)
        incident.rejudge_complete = all(
            item.state in {RejudgeBatchState.COMPLETED, RejudgeBatchState.ROLLED_BACK}
            for item in completed_batches
        )

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
