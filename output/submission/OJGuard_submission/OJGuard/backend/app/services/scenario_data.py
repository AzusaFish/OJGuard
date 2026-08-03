from __future__ import annotations

import random
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from backend.app.domain import (
    IncidentType,
    ScenarioDataset,
    ScenarioTruth,
    SimulatedCandidate,
    SimulatedComplaint,
    SimulatedDeployment,
    SimulatedSubmission,
)

BASE_TIME = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
DEFAULT_SCENARIO_SEED = 20260802


class ScenarioDataGenerator:
    """Creates reproducible, fully labelled incident datasets for validation."""

    def __init__(self, seed: int = DEFAULT_SCENARIO_SEED) -> None:
        self.seed = seed

    def runtime_regression(self) -> ScenarioDataset:
        rng = random.Random(self.seed)
        submissions: list[SimulatedSubmission] = []
        baseline_scores: dict[str, float] = defaultdict(float)
        affected_submission_ids: list[str] = []
        affected_candidate_ids: set[str] = set()
        unaffected_submission_ids: list[str] = []
        incident_start = BASE_TIME + timedelta(hours=2)

        for candidate_index in range(1, 5_001):
            candidate_id = f"CAND-{candidate_index:05d}"
            for sequence in range(1, 5):
                submission_id = f"SUB-{candidate_index:05d}-{sequence}"
                language = rng.choices(["java", "cpp", "python"], [45, 35, 20], k=1)[0]
                submitted_at = BASE_TIME + timedelta(minutes=rng.randrange(0, 240))
                judge_node = f"judge-node-{rng.randrange(1, 6):02d}"
                problem_id = f"PROB-{sequence:02d}"
                in_window = incident_start <= submitted_at < incident_start + timedelta(hours=1)
                bad_image = language == "java" and in_window
                runtime_image = (
                    "java-runtime:v2.3.1"
                    if bad_image
                    else "java-runtime:v2.3.0"
                    if language == "java"
                    else f"{language}-runtime:stable"
                )

                baseline_tle = rng.random() < 0.08
                regression_tle = bad_image and not baseline_tle and rng.random() < 0.37
                actual_tle = baseline_tle or regression_tle
                baseline_duration = (
                    rng.randrange(720, 1_050)
                    if baseline_tle
                    else rng.randrange(210, 520)
                    if language == "java"
                    else rng.randrange(80, 410)
                )
                actual_duration = (
                    rng.randrange(800, 1_400)
                    if regression_tle
                    else baseline_duration + rng.randrange(10, 90)
                    if bad_image
                    else baseline_duration
                )
                baseline_verdict = "TIME_LIMIT_EXCEEDED" if baseline_tle else "ACCEPTED"
                verdict = "TIME_LIMIT_EXCEEDED" if actual_tle else "ACCEPTED"
                baseline_score = 0.0 if baseline_tle else 25.0
                score = 0.0 if actual_tle else 25.0
                baseline_scores[candidate_id] += baseline_score

                submissions.append(
                    SimulatedSubmission(
                        id=submission_id,
                        candidate_id=candidate_id,
                        problem_id=problem_id,
                        language=language,
                        judge_node=judge_node,
                        submitted_at=submitted_at,
                        runtime_image=runtime_image,
                        package_version="package:v1.0.0",
                        checker_version="checker:v1.0.0",
                        verdict=verdict,
                        baseline_verdict=baseline_verdict,
                        duration_ms=actual_duration,
                        baseline_duration_ms=baseline_duration,
                        score=score,
                        baseline_score=baseline_score,
                    )
                )
                if regression_tle:
                    affected_submission_ids.append(submission_id)
                    affected_candidate_ids.add(candidate_id)
                elif in_window and language != "java" and len(unaffected_submission_ids) < 200:
                    unaffected_submission_ids.append(submission_id)

        candidates = [
            SimulatedCandidate(
                id=f"CAND-{index:05d}",
                batch="BACKEND-2026-A",
                baseline_score=baseline_scores[f"CAND-{index:05d}"],
            )
            for index in range(1, 5_001)
        ]
        affected_sorted = sorted(affected_candidate_ids)
        complaints = [
            SimulatedComplaint(
                id=f"CASE-{index:03d}",
                created_at=incident_start + timedelta(minutes=20 + index),
                candidate_id=candidate_id,
                category="same_code_different_result",
                summary="同一份 Java 代码在镜像变更后出现超时",
            )
            for index, candidate_id in enumerate(affected_sorted[:20], start=1)
        ]
        return ScenarioDataset(
            scenario_id="runtime-regression-java",
            seed=self.seed,
            generated_at=BASE_TIME,
            candidates=candidates,
            submissions=submissions,
            deployments=[
                SimulatedDeployment(
                    id="DEPLOY-JAVA-001",
                    deployed_at=incident_start,
                    component="java-runtime",
                    before_version="v2.3.0",
                    after_version="v2.3.1",
                    scope=["java"],
                )
            ],
            complaints=complaints,
            truth=ScenarioTruth(
                incident_type=IncidentType.RUNTIME_REGRESSION,
                root_cause="java-runtime:v2.3.1 execution parameter regression",
                affected_submission_ids=affected_submission_ids,
                affected_candidate_ids=affected_sorted,
                control_submission_ids=affected_submission_ids[:20],
                unaffected_submission_ids=unaffected_submission_ids,
                expected_dimensions={
                    "language": ["java"],
                    "runtime_image": ["java-runtime:v2.3.1"],
                    "time_window": "2026-08-02T14:00:00Z/2026-08-02T15:00:00Z",
                },
            ),
        )

    def node_degradation(self) -> ScenarioDataset:
        rng = random.Random(self.seed + 101)
        submissions: list[SimulatedSubmission] = []
        baseline_scores: dict[str, float] = defaultdict(float)
        affected_submission_ids: list[str] = []
        affected_candidate_ids: set[str] = set()
        unaffected_submission_ids: list[str] = []
        incident_start = BASE_TIME + timedelta(hours=2)

        for candidate_index in range(1, 1_501):
            candidate_id = f"NODE-CAND-{candidate_index:05d}"
            for sequence in range(1, 3):
                submission_id = f"NODE-SUB-{candidate_index:05d}-{sequence}"
                language = rng.choice(["java", "cpp", "python"])
                judge_node = f"judge-node-{rng.randrange(1, 6):02d}"
                submitted_at = BASE_TIME + timedelta(minutes=rng.randrange(60, 180))
                in_window = incident_start <= submitted_at
                degraded = judge_node == "judge-node-03" and in_window
                baseline_error = rng.random() < 0.03
                injected_error = degraded and not baseline_error and rng.random() < 0.45
                actual_error = baseline_error or injected_error
                baseline_verdict = "RUNTIME_ERROR" if baseline_error else "ACCEPTED"
                verdict = "RUNTIME_ERROR" if actual_error else "ACCEPTED"
                baseline_score = 0.0 if baseline_error else 50.0
                score = 0.0 if actual_error else 50.0
                baseline_scores[candidate_id] += baseline_score
                baseline_duration = rng.randrange(100, 450)

                submissions.append(
                    SimulatedSubmission(
                        id=submission_id,
                        candidate_id=candidate_id,
                        problem_id=f"NODE-PROB-{sequence}",
                        language=language,
                        judge_node=judge_node,
                        submitted_at=submitted_at,
                        runtime_image=f"{language}-runtime:stable",
                        package_version="package:v1.0.0",
                        checker_version="checker:v1.0.0",
                        verdict=verdict,
                        baseline_verdict=baseline_verdict,
                        duration_ms=baseline_duration + (500 if injected_error else 0),
                        baseline_duration_ms=baseline_duration,
                        score=score,
                        baseline_score=baseline_score,
                    )
                )
                if injected_error:
                    affected_submission_ids.append(submission_id)
                    affected_candidate_ids.add(candidate_id)
                elif in_window and judge_node != "judge-node-03" and len(unaffected_submission_ids) < 100:
                    unaffected_submission_ids.append(submission_id)

        candidates = [
            SimulatedCandidate(
                id=f"NODE-CAND-{index:05d}",
                batch="NODE-VALIDATION",
                baseline_score=baseline_scores[f"NODE-CAND-{index:05d}"],
            )
            for index in range(1, 1_501)
        ]
        affected_sorted = sorted(affected_candidate_ids)
        return ScenarioDataset(
            scenario_id="node-degradation",
            seed=self.seed,
            generated_at=BASE_TIME,
            candidates=candidates,
            submissions=submissions,
            deployments=[
                SimulatedDeployment(
                    id="NODE-EVENT-001",
                    deployed_at=incident_start,
                    component="judge-node-03",
                    before_version="healthy",
                    after_version="cpu-pressure-injected",
                    scope=["judge-node-03"],
                )
            ],
            complaints=[],
            truth=ScenarioTruth(
                incident_type=IncidentType.NODE_DEGRADATION,
                root_cause="judge-node-03 resource degradation",
                affected_submission_ids=affected_submission_ids,
                affected_candidate_ids=affected_sorted,
                control_submission_ids=affected_submission_ids[:20],
                unaffected_submission_ids=unaffected_submission_ids,
                expected_dimensions={
                    "judge_node": ["judge-node-03"],
                    "time_window": "2026-08-02T14:00:00Z/2026-08-02T15:00:00Z",
                },
            ),
        )

    def checker_defect(self) -> ScenarioDataset:
        rng = random.Random(self.seed + 202)
        submissions: list[SimulatedSubmission] = []
        baseline_scores: dict[str, float] = defaultdict(float)
        affected_submission_ids: list[str] = []
        affected_candidate_ids: set[str] = set()
        unaffected_submission_ids: list[str] = []
        incident_start = BASE_TIME + timedelta(hours=2)

        for candidate_index in range(1, 801):
            candidate_id = f"CHECK-CAND-{candidate_index:05d}"
            for sequence in range(1, 3):
                submission_id = f"CHECK-SUB-{candidate_index:05d}-{sequence}"
                problem_id = rng.choice(["P-CHECKER-001", "P-CONTROL-001", "P-CONTROL-002"])
                submitted_at = BASE_TIME + timedelta(minutes=rng.randrange(60, 180))
                in_window = incident_start <= submitted_at
                defect_scope = problem_id == "P-CHECKER-001" and in_window
                baseline_accepted = rng.random() < 0.72
                checker_flip = defect_scope and rng.random() < 0.34
                actual_accepted = not baseline_accepted if checker_flip else baseline_accepted
                baseline_verdict = "ACCEPTED" if baseline_accepted else "WRONG_ANSWER"
                verdict = "ACCEPTED" if actual_accepted else "WRONG_ANSWER"
                baseline_score = 50.0 if baseline_accepted else 0.0
                score = 50.0 if actual_accepted else 0.0
                baseline_scores[candidate_id] += baseline_score

                submissions.append(
                    SimulatedSubmission(
                        id=submission_id,
                        candidate_id=candidate_id,
                        problem_id=problem_id,
                        language="cpp",
                        judge_node=f"judge-node-{rng.randrange(1, 6):02d}",
                        submitted_at=submitted_at,
                        runtime_image="cpp-runtime:stable",
                        package_version="package:v1.4.1" if defect_scope else "package:v1.4.0",
                        checker_version="checker:v1.4.1" if defect_scope else "checker:v1.4.0",
                        verdict=verdict,
                        baseline_verdict=baseline_verdict,
                        duration_ms=rng.randrange(30, 180),
                        baseline_duration_ms=rng.randrange(30, 180),
                        score=score,
                        baseline_score=baseline_score,
                    )
                )
                if checker_flip:
                    affected_submission_ids.append(submission_id)
                    affected_candidate_ids.add(candidate_id)
                elif in_window and problem_id != "P-CHECKER-001" and len(unaffected_submission_ids) < 100:
                    unaffected_submission_ids.append(submission_id)

        candidates = [
            SimulatedCandidate(
                id=f"CHECK-CAND-{index:05d}",
                batch="CHECKER-VALIDATION",
                baseline_score=baseline_scores[f"CHECK-CAND-{index:05d}"],
            )
            for index in range(1, 801)
        ]
        affected_sorted = sorted(affected_candidate_ids)
        return ScenarioDataset(
            scenario_id="checker-defect",
            seed=self.seed,
            generated_at=BASE_TIME,
            candidates=candidates,
            submissions=submissions,
            deployments=[
                SimulatedDeployment(
                    id="CHECKER-DEPLOY-001",
                    deployed_at=incident_start,
                    component="P-CHECKER-001/checker",
                    before_version="v1.4.0",
                    after_version="v1.4.1",
                    scope=["P-CHECKER-001"],
                )
            ],
            complaints=[],
            truth=ScenarioTruth(
                incident_type=IncidentType.CHECKER_DEFECT,
                root_cause="P-CHECKER-001 checker:v1.4.1 contract defect",
                affected_submission_ids=affected_submission_ids,
                affected_candidate_ids=affected_sorted,
                control_submission_ids=affected_submission_ids[:20],
                unaffected_submission_ids=unaffected_submission_ids,
                expected_dimensions={
                    "problem_id": ["P-CHECKER-001"],
                    "checker_version": ["checker:v1.4.1"],
                    "time_window": "2026-08-02T14:00:00Z/2026-08-02T15:00:00Z",
                },
            ),
        )

    def generate(self, incident_type: IncidentType) -> ScenarioDataset:
        generators = {
            IncidentType.RUNTIME_REGRESSION: self.runtime_regression,
            IncidentType.NODE_DEGRADATION: self.node_degradation,
            IncidentType.CHECKER_DEFECT: self.checker_defect,
        }
        try:
            return generators[incident_type]()
        except KeyError as exc:
            raise ValueError(f"no executable demo dataset for {incident_type}") from exc
