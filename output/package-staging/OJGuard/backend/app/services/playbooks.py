from __future__ import annotations

from backend.app.domain import (
    DiagnosticPlaybook,
    IncidentType,
)

PLAYBOOKS: dict[str, DiagnosticPlaybook] = {
    "runtime-regression-v1": DiagnosticPlaybook(
        id="runtime-regression-v1",
        version="1.0.0",
        incident_type=IncidentType.RUNTIME_REGRESSION,
        display_name="运行环境回归",
        signal_dimensions=["language", "runtime_image", "judge_node", "time_window"],
        hypothesis_templates=[
            "运行镜像或启动参数导致性能回归",
            "特定评测节点退化导致超时或运行错误",
            "队列拥塞导致端到端延迟升高",
        ],
        experiment_kinds=["cross_image_replay", "cross_node_replay"],
        impact_policy="runtime-window-and-language",
        remediation_actions=["rollback_runtime", "freeze_results", "controlled_rejudge"],
        verification_checks=[
            "control_submission_consistency",
            "rejudge_coverage",
            "score_recalculation",
            "cross_language_regression",
        ],
        required_evidence=["signal_slice", "deployment_change", "replay_result", "impact_set"],
        failure_policy="实验无结论或灰度失败时暂停并转人工复核",
    ),
    "node-degradation-v1": DiagnosticPlaybook(
        id="node-degradation-v1",
        version="1.0.0",
        incident_type=IncidentType.NODE_DEGRADATION,
        display_name="评测节点退化",
        signal_dimensions=["judge_node", "language", "verdict", "time_window"],
        hypothesis_templates=[
            "特定评测节点资源或守护进程异常",
            "运行镜像在所有节点发生一致回归",
        ],
        experiment_kinds=["cross_node_replay", "node_health_probe"],
        impact_policy="node-and-time-window",
        remediation_actions=["isolate_node", "drain_queue", "controlled_rejudge"],
        verification_checks=["node_health", "rejudge_coverage", "unaffected_node_regression"],
        required_evidence=["node_metric_slice", "cross_node_replay", "impact_set"],
        failure_policy="无法隔离节点影响时不得扩大重评范围",
    ),
    "checker-defect-v1": DiagnosticPlaybook(
        id="checker-defect-v1",
        version="1.0.0",
        incident_type=IncidentType.CHECKER_DEFECT,
        display_name="Checker 缺陷",
        signal_dimensions=["problem_id", "package_version", "checker_version", "verdict"],
        hypothesis_templates=[
            "Checker 接受非法输出",
            "Checker 错误拒绝合法输出",
            "题面、Validator 与 Checker 契约不一致",
        ],
        experiment_kinds=["checker_adversarial_probe", "package_contract_audit"],
        impact_policy="problem-version-and-submission",
        remediation_actions=["freeze_problem", "patch_checker_copy", "controlled_rejudge"],
        verification_checks=["checker_regression", "rejudge_coverage", "unrelated_problem_regression"],
        required_evidence=["package_hash", "checker_probe", "minimal_counterexample", "impact_set"],
        failure_policy="涉及题意解释时必须转人工确认，不自动修改正式题包",
    ),
    "queue-congestion-v1": DiagnosticPlaybook(
        id="queue-congestion-v1",
        version="1.0.0",
        incident_type=IncidentType.QUEUE_CONGESTION,
        display_name="评测队列拥塞",
        signal_dimensions=["queue", "wait_time", "worker_pool", "time_window"],
        hypothesis_templates=["任务到达率超过处理能力", "部分 Worker 不可用导致积压"],
        experiment_kinds=["queue_capacity_analysis", "worker_health_probe"],
        impact_policy="queue-and-time-window",
        remediation_actions=["throttle_intake", "restore_worker_pool"],
        verification_checks=["queue_recovery", "submission_completion"],
        required_evidence=["queue_metrics", "worker_health"],
        failure_policy="当前仅提供契约，不宣称生产执行器已实现",
    ),
    "configuration-drift-v1": DiagnosticPlaybook(
        id="configuration-drift-v1",
        version="1.0.0",
        incident_type=IncidentType.CONFIGURATION_DRIFT,
        display_name="评测配置漂移",
        signal_dimensions=["configuration_key", "judge_node", "deployment", "time_window"],
        hypothesis_templates=["节点配置与批准基线不一致"],
        experiment_kinds=["configuration_diff", "baseline_replay"],
        impact_policy="configuration-scope",
        remediation_actions=["restore_configuration", "controlled_rejudge"],
        verification_checks=["configuration_integrity", "rejudge_coverage"],
        required_evidence=["configuration_diff", "approved_baseline"],
        failure_policy="当前仅提供契约，不宣称生产执行器已实现",
    ),
}


DEFAULT_PLAYBOOK_BY_TYPE: dict[IncidentType, str] = {
    playbook.incident_type: playbook.id for playbook in PLAYBOOKS.values()
}


def get_playbook(playbook_id: str) -> DiagnosticPlaybook:
    try:
        return PLAYBOOKS[playbook_id]
    except KeyError as exc:
        raise KeyError(f"unknown incident playbook: {playbook_id}") from exc


def default_playbook_for(incident_type: IncidentType) -> DiagnosticPlaybook:
    return get_playbook(DEFAULT_PLAYBOOK_BY_TYPE[incident_type])


def list_playbooks() -> list[DiagnosticPlaybook]:
    return sorted(PLAYBOOKS.values(), key=lambda item: item.id)
