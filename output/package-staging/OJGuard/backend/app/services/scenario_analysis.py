from __future__ import annotations

from collections import defaultdict
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.app.domain import (
    ExperimentCandidate,
    ExperimentState,
    HypothesisState,
    IncidentExperiment,
    IncidentSignal,
    IncidentType,
    RootCauseHypothesis,
    ScenarioDataset,
    SignalKind,
)


class ScenarioMetrics(BaseModel):
    incident_type: IncidentType
    scoped_submission_count: int = Field(ge=0)
    affected_submission_count: int = Field(ge=0)
    affected_candidate_count: int = Field(ge=0)
    baseline_failure_rate: float = Field(ge=0, le=1)
    observed_failure_rate: float = Field(ge=0, le=1)
    failure_rate_delta: float = Field(ge=-1, le=1)
    per_group_failure_rate: dict[str, float]


def _is_failure(verdict: str) -> bool:
    return verdict != "ACCEPTED"


def _in_primary_scope(dataset: ScenarioDataset, submission_index: int) -> bool:
    submission = dataset.submissions[submission_index]
    if dataset.truth.incident_type == IncidentType.RUNTIME_REGRESSION:
        return submission.runtime_image == "java-runtime:v2.3.1"
    if dataset.truth.incident_type == IncidentType.NODE_DEGRADATION:
        return submission.judge_node == "judge-node-03" and submission.submitted_at.hour >= 14
    if dataset.truth.incident_type == IncidentType.CHECKER_DEFECT:
        return submission.checker_version == "checker:v1.4.1"
    return False


class ScenarioAnalyzer:
    def metrics(self, dataset: ScenarioDataset) -> ScenarioMetrics:
        scoped = [
            submission
            for index, submission in enumerate(dataset.submissions)
            if _in_primary_scope(dataset, index)
        ]
        checker_mode = dataset.truth.incident_type == IncidentType.CHECKER_DEFECT
        baseline_failures = 0 if checker_mode else sum(
            _is_failure(item.baseline_verdict) for item in scoped
        )
        observed_failures = (
            sum(item.verdict != item.baseline_verdict for item in scoped)
            if checker_mode
            else sum(_is_failure(item.verdict) for item in scoped)
        )
        if dataset.truth.incident_type == IncidentType.RUNTIME_REGRESSION:
            group_population = scoped
        else:
            group_population = [item for item in dataset.submissions if item.submitted_at.hour >= 14]
        grouped_total: dict[str, int] = defaultdict(int)
        grouped_failure: dict[str, int] = defaultdict(int)
        for item in group_population:
            group = (
                item.judge_node
                if dataset.truth.incident_type != IncidentType.CHECKER_DEFECT
                else item.problem_id
            )
            grouped_total[group] += 1
            grouped_failure[group] += int(
                item.verdict != item.baseline_verdict if checker_mode else _is_failure(item.verdict)
            )

        scoped_count = len(scoped)
        baseline_rate = baseline_failures / scoped_count if scoped_count else 0.0
        observed_rate = observed_failures / scoped_count if scoped_count else 0.0
        return ScenarioMetrics(
            incident_type=dataset.truth.incident_type,
            scoped_submission_count=scoped_count,
            affected_submission_count=len(dataset.truth.affected_submission_ids),
            affected_candidate_count=len(dataset.truth.affected_candidate_ids),
            baseline_failure_rate=baseline_rate,
            observed_failure_rate=observed_rate,
            failure_rate_delta=observed_rate - baseline_rate,
            per_group_failure_rate={
                group: grouped_failure[group] / total
                for group, total in sorted(grouped_total.items())
            },
        )

    def signals(self, incident_id: str, dataset: ScenarioDataset) -> list[IncidentSignal]:
        metrics = self.metrics(dataset)
        signals = [
            IncidentSignal(
                id=f"SIG-{uuid4().hex[:10].upper()}",
                incident_id=incident_id,
                kind=SignalKind.METRIC,
                source="simulated-monitoring",
                observed_at=dataset.generated_at,
                summary=(
                    f"作用域内失败率从 {metrics.baseline_failure_rate:.1%} "
                    f"上升到 {metrics.observed_failure_rate:.1%}"
                ),
                dimensions={
                    "scoped_submission_count": metrics.scoped_submission_count,
                    "failure_rate_delta": round(metrics.failure_rate_delta, 4),
                },
            )
        ]
        for deployment in dataset.deployments:
            signals.append(
                IncidentSignal(
                    id=f"SIG-{uuid4().hex[:10].upper()}",
                    incident_id=incident_id,
                    kind=SignalKind.DEPLOYMENT,
                    source="simulated-deployment",
                    observed_at=deployment.deployed_at,
                    summary=(
                        f"{deployment.component} 从 {deployment.before_version} "
                        f"变更到 {deployment.after_version}"
                    ),
                    dimensions={"component": deployment.component},
                )
            )
        for complaint in dataset.complaints:
            signals.append(
                IncidentSignal(
                    id=f"SIG-{uuid4().hex[:10].upper()}",
                    incident_id=incident_id,
                    kind=SignalKind.COMPLAINT,
                    source="simulated-support",
                    observed_at=complaint.created_at,
                    summary=complaint.summary,
                    dimensions={"category": complaint.category},
                )
            )
        return signals

    def competing_hypotheses(
        self,
        incident_id: str,
        dataset: ScenarioDataset,
    ) -> list[RootCauseHypothesis]:
        if dataset.truth.incident_type == IncidentType.RUNTIME_REGRESSION:
            definitions = [
                ("runtime_image", "Java 运行镜像或启动参数导致性能回归"),
                ("judge_node", "部分评测节点退化导致 Java 提交集中超时"),
            ]
        elif dataset.truth.incident_type == IncidentType.NODE_DEGRADATION:
            definitions = [
                ("judge_node", "judge-node-03 资源退化导致运行错误"),
                ("runtime_image", "某一语言运行镜像在所有节点发生回归"),
            ]
        else:
            definitions = [
                ("checker", "Checker 新版本违反输出契约"),
                ("runtime", "选手程序运行环境导致结果变化"),
            ]

        hypothesis_ids = [f"HYP-{uuid4().hex[:10].upper()}" for _ in definitions]
        return [
            RootCauseHypothesis(
                id=hypothesis_ids[index],
                incident_id=incident_id,
                proposed_by="root-cause-analyst",
                category=category,
                statement=statement,
                confidence=0.5,
                state=HypothesisState.PROPOSED,
                competing_hypothesis_ids=[
                    item for item in hypothesis_ids if item != hypothesis_ids[index]
                ],
                required_experiment_kinds=self._experiment_kinds(
                    dataset.truth.incident_type
                ),
            )
            for index, (category, statement) in enumerate(definitions)
        ]

    @staticmethod
    def _experiment_kind(incident_type: IncidentType) -> str:
        return {
            IncidentType.RUNTIME_REGRESSION: "cross_image_and_node_replay",
            IncidentType.NODE_DEGRADATION: "cross_node_replay",
            IncidentType.CHECKER_DEFECT: "checker_contract_probe",
        }[incident_type]

    @staticmethod
    def _experiment_kinds(incident_type: IncidentType) -> list[str]:
        return {
            IncidentType.RUNTIME_REGRESSION: [
                "cross_image_and_node_replay",
                "cross_image_replay",
                "cross_node_replay",
            ],
            IncidentType.NODE_DEGRADATION: [
                "cross_node_replay",
                "cross_image_and_node_replay",
                "cross_image_replay",
            ],
            IncidentType.CHECKER_DEFECT: [
                "checker_contract_probe",
                "checker_adversarial_probe",
                "package_contract_audit",
            ],
        }[incident_type]

    def experiment_candidates(
        self,
        dataset: ScenarioDataset,
        hypotheses: list[RootCauseHypothesis],
    ) -> list[ExperimentCandidate]:
        hypothesis_ids = [item.id for item in hypotheses]
        descriptions = {
            "cross_image_and_node_replay": (
                "镜像与节点二维对照",
                ["runtime_image", "judge_node"],
                "同时区分镜像回归、节点退化和二者交互影响",
            ),
            "cross_image_replay": (
                "跨运行镜像对照",
                ["runtime_image"],
                "在固定节点上比较基线镜像与观测镜像",
            ),
            "cross_node_replay": (
                "跨评测节点对照",
                ["judge_node"],
                "在固定运行环境下比较健康节点与异常节点",
            ),
            "checker_contract_probe": (
                "Checker 契约探针",
                ["checker_version", "problem_id"],
                "比较已验证 Checker 与当前 Checker 的判定一致性",
            ),
            "checker_adversarial_probe": (
                "Checker 对抗样例探针",
                ["checker_version", "adversarial_case"],
                "使用最小反例区分 Checker 缺陷与选手程序问题",
            ),
            "package_contract_audit": (
                "题包契约审计",
                ["statement", "validator", "checker"],
                "检查题面、Validator 与 Checker 的静态契约一致性",
            ),
        }
        return [
            ExperimentCandidate(
                kind=kind,
                title=descriptions[kind][0],
                hypothesis_ids=hypothesis_ids,
                dimensions=descriptions[kind][1],
                expected_discrimination=descriptions[kind][2],
                evidence_refs=hypothesis_ids,
            )
            for kind in self._experiment_kinds(dataset.truth.incident_type)
        ]

    def run_comparison(
        self,
        incident_id: str,
        dataset: ScenarioDataset,
        hypotheses: list[RootCauseHypothesis],
        experiment_kind: str | None = None,
    ) -> IncidentExperiment:
        metrics = self.metrics(dataset)
        supported_kinds = self._experiment_kinds(dataset.truth.incident_type)
        selected_kind = experiment_kind or self._experiment_kind(dataset.truth.incident_type)
        if selected_kind not in supported_kinds:
            raise ValueError(
                f"experiment kind {selected_kind} is not supported for "
                f"{dataset.truth.incident_type.value}"
            )
        primary_category = {
            IncidentType.RUNTIME_REGRESSION: "runtime_image",
            IncidentType.NODE_DEGRADATION: "judge_node",
            IncidentType.CHECKER_DEFECT: "checker",
        }[dataset.truth.incident_type]
        primary = next(item for item in hypotheses if item.category == primary_category)
        comparison = next(item for item in hypotheses if item.id != primary.id)
        discriminating_kinds = {
            IncidentType.RUNTIME_REGRESSION: {
                "cross_image_and_node_replay",
                "cross_image_replay",
            },
            IncidentType.NODE_DEGRADATION: {
                "cross_image_and_node_replay",
                "cross_node_replay",
            },
            IncidentType.CHECKER_DEFECT: {
                "checker_contract_probe",
                "checker_adversarial_probe",
            },
        }[dataset.truth.incident_type]
        discriminates = (
            selected_kind in discriminating_kinds and metrics.failure_rate_delta >= 0.15
        )
        title = next(
            item.title
            for item in self.experiment_candidates(dataset, hypotheses)
            if item.kind == selected_kind
        )
        return IncidentExperiment(
            id=f"EXP-{uuid4().hex[:10].upper()}",
            incident_id=incident_id,
            hypothesis_ids=[primary.id, comparison.id],
            kind=selected_kind,
            title=title,
            control={"baseline": dataset.truth.expected_dimensions},
            treatment={"observed": dataset.truth.expected_dimensions},
            success_criteria={"minimum_failure_rate_delta": 0.15},
            state=(
                ExperimentState.PASSED if discriminates else ExperimentState.INCONCLUSIVE
            ),
            conclusion=(
                dataset.truth.root_cause
                if discriminates
                else f"{selected_kind} 未能区分当前竞争假设，需要补充实验"
            ),
            metrics={
                "baseline_failure_rate": round(metrics.baseline_failure_rate, 6),
                "observed_failure_rate": round(metrics.observed_failure_rate, 6),
                "failure_rate_delta": round(metrics.failure_rate_delta, 6),
                "scoped_submission_count": metrics.scoped_submission_count,
                **{
                    f"group:{group}": round(rate, 6)
                    for group, rate in metrics.per_group_failure_rate.items()
                },
            },
        )
