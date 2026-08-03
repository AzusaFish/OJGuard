from __future__ import annotations

from backend.app.domain import (
    IncidentApprovalDecision,
    IncidentContext,
    IncidentStage,
    RejudgeBatchState,
    RouteDecision,
    RouteOption,
)
from backend.app.services.incident_workflow import IncidentWorkflowService
from backend.app.services.repository import SQLiteRepository

EXPERIMENT_ACTIONS = {
    "cross_image_and_node_replay": "experiment_two_dimensional",
    "cross_image_replay": "experiment_cross_image",
    "cross_node_replay": "experiment_cross_node",
    "checker_contract_probe": "experiment_checker_contract",
    "checker_adversarial_probe": "experiment_checker_adversarial",
    "package_contract_audit": "experiment_package_contract",
}


class InvalidRouteDecisionError(ValueError):
    """Raised when a model route is outside the deterministic policy envelope."""


class AgentRoutingPolicy:
    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository
        self.workflow = IncidentWorkflowService(repository)

    @staticmethod
    def _option(
        *,
        action: str,
        worker: str,
        expected_result: str,
        evidence_refs: list[str],
        expected_stage: IncidentStage | None = None,
        expected_stages: list[IncidentStage] | None = None,
        tool: str | None = None,
        arguments: dict[str, str | int | float | bool] | None = None,
        experiment_kind: str | None = None,
    ) -> RouteOption:
        return RouteOption(
            action=action,
            worker=worker,
            tool=tool,
            arguments=arguments or {},
            expected_stages=expected_stages or ([expected_stage] if expected_stage else []),
            evidence_refs=evidence_refs,
            experiment_kind=experiment_kind,
            expected_result=expected_result,
        )

    def legal_options(self, incident: IncidentContext) -> list[RouteOption]:
        incident_id = incident.incident_id
        hypotheses = self.repository.list_root_cause_hypotheses(incident_id)
        experiments = self.repository.list_incident_experiments(incident_id)
        plans = self.repository.list_remediation_plans(incident_id)
        approvals = self.repository.list_incident_approvals(incident_id)
        batches = self.repository.list_rejudge_batches(incident_id)
        verifications = self.repository.list_incident_verifications(incident_id)

        if incident.stage == IncidentStage.TRIAGING:
            return [
                self._option(
                    action="triage",
                    worker="ojguard-signal-aggregator",
                    tool="incident.triage_signals",
                    arguments={"incident_id": incident_id},
                    expected_stage=IncidentStage.INVESTIGATING,
                    expected_result="形成可追溯时间线，但不确认根因",
                    evidence_refs=incident.signal_ids[:20],
                )
            ]

        if incident.stage == IncidentStage.INVESTIGATING:
            if not hypotheses:
                return [
                    self._option(
                        action="hypothesize",
                        worker="ojguard-root-cause-analyst",
                        tool="judge.replay_submission",
                        arguments={
                            "incident_id": incident_id,
                            "repetitions": 3,
                            "mode": "hypotheses",
                        },
                        expected_stage=IncidentStage.INVESTIGATING,
                        expected_result="持久化相互竞争且可证伪的根因假设",
                        evidence_refs=incident.signal_ids[:20],
                    )
                ]
            options: list[RouteOption] = []
            for candidate in self.workflow.list_experiment_candidates(incident_id):
                action = EXPERIMENT_ACTIONS[candidate.kind]
                options.append(
                    self._option(
                        action=action,
                        worker="ojguard-root-cause-analyst",
                        tool="judge.replay_submission",
                        arguments={
                            "incident_id": incident_id,
                            "repetitions": 3,
                            "mode": "experiment",
                            "experiment_kind": candidate.kind,
                        },
                        expected_stages=[
                            IncidentStage.INVESTIGATING,
                            IncidentStage.IMPACT_ASSESSING,
                        ],
                        expected_result=candidate.expected_discrimination,
                        evidence_refs=candidate.evidence_refs,
                        experiment_kind=candidate.kind,
                    )
                )
            return options

        if incident.stage == IncidentStage.IMPACT_ASSESSING:
            return [
                self._option(
                    action="impact",
                    worker="ojguard-impact-analyst",
                    tool="impact.calculate_scope",
                    arguments={"incident_id": incident_id},
                    expected_stage=IncidentStage.REMEDIATION_PLANNING,
                    expected_result="冻结可重现的精确影响集合",
                    evidence_refs=[
                        *incident.confirmed_root_cause_ids,
                        *[item.id for item in experiments[-2:]],
                    ],
                )
            ]

        if incident.stage == IncidentStage.REMEDIATION_PLANNING:
            return [
                self._option(
                    action="plan",
                    worker="ojguard-remediation-planner",
                    tool="rejudge.create_plan",
                    arguments={"incident_id": incident_id, "mode": "initial"},
                    expected_stage=IncidentStage.APPROVAL_PENDING,
                    expected_result="生成带停止条件和回滚动作的分批处置计划",
                    evidence_refs=[incident.impact_assessment_id]
                    if incident.impact_assessment_id
                    else [],
                )
            ]

        if incident.stage == IncidentStage.APPROVAL_PENDING:
            if (
                incident.approval_state.get("execute_plan")
                != IncidentApprovalDecision.APPROVED
                or incident.approval_state.get("run_canary_rejudge")
                != IncidentApprovalDecision.APPROVED
            ):
                return [
                    self._option(
                        action="request_technical_approval",
                        worker="HUMAN",
                        expected_stage=IncidentStage.APPROVAL_PENDING,
                        expected_result="由技术角色确认计划、范围和停止条件",
                        evidence_refs=[item.id for item in plans[-2:]],
                    )
                ]
            return [
                self._option(
                    action="control_canary",
                    worker="ojguard-rejudge-executor",
                    tool="rejudge.execute_batch",
                    arguments={"incident_id": incident_id, "phase": "control_canary"},
                    expected_stages=[IncidentStage.EXECUTING, IncidentStage.PAUSED],
                    expected_result="只执行已批准的控制组与灰度批次",
                    evidence_refs=[
                        *[item.id for item in plans[-2:]],
                        *[item.id for item in approvals[-4:]],
                    ],
                )
            ]

        if incident.stage == IncidentStage.PAUSED:
            failed_canary = [
                item
                for item in batches
                if item.kind in {"canary", "canary_retry"}
                and item.state == RejudgeBatchState.FAILED
            ]
            if failed_canary:
                return [
                    self._option(
                        action="recovery_plan",
                        worker="ojguard-remediation-planner",
                        tool="rejudge.create_plan",
                        arguments={"incident_id": incident_id, "mode": "recovery"},
                        expected_stage=IncidentStage.APPROVAL_PENDING,
                        expected_result="隔离失败环境并创建需要重新审批的恢复计划",
                        evidence_refs=[item.id for item in failed_canary[-2:]],
                    )
                ]
            return []

        if incident.stage == IncidentStage.EXECUTING:
            if not incident.canary_rejudge_passed:
                return [
                    self._option(
                        action="control_canary",
                        worker="ojguard-rejudge-executor",
                        tool="rejudge.execute_batch",
                        arguments={"incident_id": incident_id, "phase": "control_canary"},
                        expected_stage=IncidentStage.EXECUTING,
                        expected_result="完成恢复灰度且不产生范围漂移",
                        evidence_refs=[item.id for item in batches[-4:]],
                    )
                ]
            if (
                incident.approval_state.get("run_bulk_rejudge")
                != IncidentApprovalDecision.APPROVED
            ):
                return [
                    self._option(
                        action="request_business_approval",
                        worker="HUMAN",
                        expected_stage=IncidentStage.EXECUTING,
                        expected_result="由业务角色批准精确影响集合内的全量重评",
                        evidence_refs=[item.id for item in batches[-4:]],
                    )
                ]
            return [
                self._option(
                    action="bulk",
                    worker="ojguard-rejudge-executor",
                    tool="rejudge.execute_batch",
                    arguments={"incident_id": incident_id, "phase": "bulk"},
                    expected_stage=IncidentStage.REJUDGING,
                    expected_result="幂等执行批准范围内的全量重评",
                    evidence_refs=[
                        *[item.id for item in batches[-4:]],
                        *[item.id for item in approvals[-2:]],
                    ],
                )
            ]

        if incident.stage == IncidentStage.REJUDGING:
            if not incident.rejudge_complete:
                return [
                    self._option(
                        action="bulk",
                        worker="ojguard-rejudge-executor",
                        tool="rejudge.execute_batch",
                        arguments={"incident_id": incident_id, "phase": "bulk"},
                        expected_stage=IncidentStage.REJUDGING,
                        expected_result="完成剩余批准批次",
                        evidence_refs=[item.id for item in batches[-4:]],
                    )
                ]
            return [
                self._option(
                    action="verify",
                    worker="ojguard-verification-auditor",
                    tool="verification.verify_incident",
                    arguments={"incident_id": incident_id},
                    expected_stage=IncidentStage.VERIFYING,
                    expected_result="独立重算覆盖、重复、遗漏、越界和成绩一致性",
                    evidence_refs=[item.id for item in batches[-6:]],
                )
            ]

        if incident.stage == IncidentStage.VERIFYING:
            if not verifications:
                return [
                    self._option(
                        action="verify",
                        worker="ojguard-verification-auditor",
                        tool="verification.verify_incident",
                        arguments={"incident_id": incident_id},
                        expected_stage=IncidentStage.VERIFYING,
                        expected_result="持久化独立验证结果",
                        evidence_refs=[item.id for item in batches[-6:]],
                    )
                ]
            return [
                self._option(
                    action="request_close_approval",
                    worker="HUMAN",
                    expected_stage=IncidentStage.RESOLVED,
                    expected_result="由业务角色审核验证证据并批准关闭",
                    evidence_refs=[item.id for item in verifications[-2:]],
                )
            ]
        return []

    @staticmethod
    def validate_decision(
        decision: RouteDecision,
        options: list[RouteOption],
    ) -> RouteOption:
        option = next((item for item in options if item.action == decision.action), None)
        if option is None:
            raise InvalidRouteDecisionError("selected action is not legal in the current state")
        if decision.worker != option.worker:
            raise InvalidRouteDecisionError("selected worker does not match the action contract")
        if decision.experiment_kind != option.experiment_kind:
            raise InvalidRouteDecisionError("selected experiment does not match the action")
        if decision.failure_action != option.failure_action:
            raise InvalidRouteDecisionError("failure action must follow the policy contract")
        unsupported_refs = set(decision.evidence_refs) - set(option.evidence_refs)
        if unsupported_refs:
            raise InvalidRouteDecisionError("decision references evidence outside the route option")
        return option
