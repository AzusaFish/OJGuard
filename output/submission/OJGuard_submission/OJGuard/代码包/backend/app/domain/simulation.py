from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .incidents import IncidentType


class SimulatedCandidate(BaseModel):
    id: str
    batch: str
    baseline_score: float = Field(ge=0)


class SimulatedSubmission(BaseModel):
    id: str
    candidate_id: str
    problem_id: str
    language: str
    judge_node: str
    submitted_at: datetime
    runtime_image: str
    package_version: str
    checker_version: str
    verdict: str
    baseline_verdict: str
    duration_ms: int = Field(ge=0)
    baseline_duration_ms: int = Field(ge=0)
    score: float = Field(ge=0)
    baseline_score: float = Field(ge=0)


class SimulatedDeployment(BaseModel):
    id: str
    deployed_at: datetime
    component: str
    before_version: str
    after_version: str
    scope: list[str]


class SimulatedComplaint(BaseModel):
    id: str
    created_at: datetime
    candidate_id: str
    category: str
    summary: str


class ScenarioTruth(BaseModel):
    incident_type: IncidentType
    root_cause: str
    affected_submission_ids: list[str]
    affected_candidate_ids: list[str]
    control_submission_ids: list[str]
    unaffected_submission_ids: list[str]
    expected_dimensions: dict[str, list[str] | str]


class ScenarioDataset(BaseModel):
    scenario_id: str
    seed: int
    generated_at: datetime
    candidates: list[SimulatedCandidate]
    submissions: list[SimulatedSubmission]
    deployments: list[SimulatedDeployment]
    complaints: list[SimulatedComplaint]
    truth: ScenarioTruth
