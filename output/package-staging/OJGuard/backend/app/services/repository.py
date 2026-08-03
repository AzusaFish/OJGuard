from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from backend.app.domain import (
    AgentEvent,
    AgentRun,
    AgentRunEvent,
    AgentRunEventType,
    AgentRunStatus,
    ApprovalRecord,
    Evidence,
    Finding,
    ImpactAssessment,
    IncidentApprovalRecord,
    IncidentContext,
    IncidentExperiment,
    IncidentSignal,
    IncidentVerification,
    PatchCandidate,
    RejudgeBatch,
    RemediationPlan,
    RootCauseHypothesis,
    ScoreChange,
    TaskContext,
)

IncidentEntity = TypeVar("IncidentEntity", bound=BaseModel)


class SQLiteRepository:
    """Small durable store for the single-node OJGuard deployment."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    package_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    document_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at DESC);

                CREATE TABLE IF NOT EXISTS agent_events (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    document_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_run_created
                    ON agent_events(run_id, created_at ASC);

                CREATE TABLE IF NOT EXISTS findings (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    confidence_class TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    document_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_findings_run ON findings(run_id, severity);

                CREATE TABLE IF NOT EXISTS evidence (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    document_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_evidence_run ON evidence(run_id, created_at);

                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    document_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_approvals_run ON approvals(run_id, created_at);

                CREATE TABLE IF NOT EXISTS patch_candidates (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    document_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_patches_run
                    ON patch_candidates(run_id, created_at);

                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id TEXT PRIMARY KEY,
                    incident_type TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    document_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_incidents_created_at
                    ON incidents(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_incidents_type_stage
                    ON incidents(incident_type, stage);

                CREATE TABLE IF NOT EXISTS incident_entities (
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    incident_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    document_json TEXT NOT NULL,
                    PRIMARY KEY(entity_type, entity_id),
                    FOREIGN KEY(incident_id) REFERENCES incidents(incident_id)
                        ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_incident_entities_lookup
                    ON incident_entities(incident_id, entity_type, created_at);

                CREATE TABLE IF NOT EXISTS orchestration_runs (
                    run_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    incident_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    document_json TEXT NOT NULL,
                    FOREIGN KEY(incident_id) REFERENCES incidents(incident_id)
                        ON DELETE CASCADE
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_orchestration_runs_task
                    ON orchestration_runs(task_id);
                CREATE INDEX IF NOT EXISTS idx_orchestration_runs_incident
                    ON orchestration_runs(incident_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS orchestration_events (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    incident_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    document_json TEXT NOT NULL,
                    UNIQUE(run_id, sequence),
                    FOREIGN KEY(run_id) REFERENCES orchestration_runs(run_id)
                        ON DELETE CASCADE,
                    FOREIGN KEY(incident_id) REFERENCES incidents(incident_id)
                        ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_orchestration_events_stream
                    ON orchestration_events(run_id, sequence ASC);
                """
            )

    @staticmethod
    def _json(model: object) -> str:
        return json.dumps(model.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)

    def save_run(self, context: TaskContext) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO runs(run_id, package_id, stage, created_at, updated_at, document_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    stage=excluded.stage,
                    updated_at=excluded.updated_at,
                    document_json=excluded.document_json
                """,
                (
                    context.run_id,
                    context.package_id,
                    context.stage.value,
                    context.created_at.isoformat(),
                    context.updated_at.isoformat(),
                    self._json(context),
                ),
            )

    def get_run(self, run_id: str) -> TaskContext | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT document_json FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return TaskContext.model_validate_json(row["document_json"]) if row else None

    def list_runs(self, limit: int = 100) -> list[TaskContext]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT document_json FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [TaskContext.model_validate_json(row["document_json"]) for row in rows]

    def append_event(self, event: AgentEvent) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO agent_events(id, run_id, created_at, document_json)
                VALUES (?, ?, ?, ?)
                """,
                (event.id, event.run_id, event.created_at.isoformat(), self._json(event)),
            )

    def list_events(self, run_id: str) -> list[AgentEvent]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT document_json FROM agent_events
                WHERE run_id = ? ORDER BY created_at ASC
                """,
                (run_id,),
            ).fetchall()
        return [AgentEvent.model_validate_json(row["document_json"]) for row in rows]

    def save_agent_run(self, run: AgentRun) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO orchestration_runs(
                    run_id, task_id, incident_id, status, created_at, updated_at,
                    document_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    task_id=excluded.task_id,
                    incident_id=excluded.incident_id,
                    status=excluded.status,
                    updated_at=excluded.updated_at,
                    document_json=excluded.document_json
                """,
                (
                    run.run_id,
                    run.task_id,
                    run.incident_id,
                    run.status.value,
                    run.created_at.isoformat(),
                    run.updated_at.isoformat(),
                    self._json(run),
                ),
            )

    def get_agent_run(self, run_id: str) -> AgentRun | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT document_json FROM orchestration_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return AgentRun.model_validate_json(row["document_json"]) if row else None

    def get_agent_run_by_task(self, task_id: str) -> AgentRun | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT document_json FROM orchestration_runs WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        return AgentRun.model_validate_json(row["document_json"]) if row else None

    def get_latest_agent_run_for_incident(self, incident_id: str) -> AgentRun | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT document_json FROM orchestration_runs
                WHERE incident_id = ? ORDER BY created_at DESC LIMIT 1
                """,
                (incident_id,),
            ).fetchone()
        return AgentRun.model_validate_json(row["document_json"]) if row else None

    def list_agent_runs(self, limit: int = 100) -> list[AgentRun]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT document_json FROM orchestration_runs
                ORDER BY created_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [AgentRun.model_validate_json(row["document_json"]) for row in rows]

    def append_agent_run_event(self, event: AgentRunEvent) -> AgentRunEvent:
        response_event_types = {
            AgentRunEventType.ROUTE_DECISION.value,
            AgentRunEventType.WORKER_RESULT.value,
            AgentRunEventType.FINAL_REPORT.value,
        }
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT document_json FROM orchestration_events WHERE id = ?",
                (event.id,),
            ).fetchone()
            if existing:
                return AgentRunEvent.model_validate_json(existing["document_json"])

            run_row = connection.execute(
                "SELECT document_json FROM orchestration_runs WHERE run_id = ?",
                (event.run_id,),
            ).fetchone()
            if run_row is None:
                raise ValueError("agent run not found")
            run = AgentRun.model_validate_json(run_row["document_json"])
            next_sequence = connection.execute(
                """
                SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence
                FROM orchestration_events WHERE run_id = ?
                """,
                (event.run_id,),
            ).fetchone()["next_sequence"]
            stored = event.model_copy(update={"sequence": next_sequence})
            connection.execute(
                """
                INSERT INTO orchestration_events(
                    id, run_id, incident_id, sequence, event_type, created_at,
                    document_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stored.id,
                    stored.run_id,
                    stored.incident_id,
                    stored.sequence,
                    stored.event_type.value,
                    stored.created_at.isoformat(),
                    self._json(stored),
                ),
            )

            updated = run.model_copy(deep=True)
            updated.last_event_sequence = stored.sequence
            updated.current_agent = stored.worker or stored.agent
            updated.current_action = stored.action
            updated.updated_at = stored.created_at
            if stored.event_type == AgentRunEventType.RUN_STARTED:
                updated.status = AgentRunStatus.RUNNING
                updated.started_at = updated.started_at or stored.created_at
            elif stored.event_type == AgentRunEventType.RUN_PAUSED:
                updated.status = AgentRunStatus.PAUSED
                updated.failure_reason = stored.summary
            elif stored.event_type == AgentRunEventType.RUN_RESUMED:
                updated.status = AgentRunStatus.RUNNING
                updated.failure_reason = None
            elif stored.event_type == AgentRunEventType.FINAL_REPORT:
                updated.status = AgentRunStatus.COMPLETED
                updated.completed_at = stored.created_at
            elif stored.event_type == AgentRunEventType.ERROR:
                updated.status = AgentRunStatus.FAILED
                updated.failure_reason = stored.summary
                updated.completed_at = stored.created_at
            if stored.event_type.value in response_event_types:
                updated.model_response_count += 1
            connection.execute(
                """
                UPDATE orchestration_runs
                SET status = ?, updated_at = ?, document_json = ?
                WHERE run_id = ?
                """,
                (
                    updated.status.value,
                    updated.updated_at.isoformat(),
                    self._json(updated),
                    updated.run_id,
                ),
            )
        return stored

    def list_agent_run_events(
        self,
        run_id: str,
        *,
        after_sequence: int = 0,
        limit: int = 500,
    ) -> list[AgentRunEvent]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT document_json FROM orchestration_events
                WHERE run_id = ? AND sequence > ?
                ORDER BY sequence ASC LIMIT ?
                """,
                (run_id, max(after_sequence, 0), min(max(limit, 1), 2_000)),
            ).fetchall()
        return [AgentRunEvent.model_validate_json(row["document_json"]) for row in rows]

    def save_finding(self, finding: Finding) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO findings(
                    id, run_id, severity, confidence_class, created_at, document_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET document_json=excluded.document_json
                """,
                (
                    finding.id,
                    finding.run_id,
                    finding.severity.value,
                    finding.confidence_class.value,
                    finding.created_at.isoformat(),
                    self._json(finding),
                ),
            )

    def list_findings(self, run_id: str) -> list[Finding]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT document_json FROM findings WHERE run_id = ? ORDER BY created_at ASC",
                (run_id,),
            ).fetchall()
        return [Finding.model_validate_json(row["document_json"]) for row in rows]

    def save_evidence(self, evidence: Evidence) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO evidence(id, run_id, sha256, created_at, document_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET document_json=excluded.document_json
                """,
                (
                    evidence.id,
                    evidence.run_id,
                    evidence.sha256,
                    evidence.created_at.isoformat(),
                    self._json(evidence),
                ),
            )

    def list_evidence(self, run_id: str) -> list[Evidence]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT document_json FROM evidence WHERE run_id = ? ORDER BY created_at ASC",
                (run_id,),
            ).fetchall()
        return [Evidence.model_validate_json(row["document_json"]) for row in rows]

    def save_approval(self, approval: ApprovalRecord) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO approvals(id, run_id, state, created_at, document_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    state=excluded.state,
                    document_json=excluded.document_json
                """,
                (
                    approval.id,
                    approval.run_id,
                    approval.state.value,
                    approval.created_at.isoformat(),
                    self._json(approval),
                ),
            )

    def list_approvals(self, run_id: str) -> list[ApprovalRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT document_json FROM approvals WHERE run_id = ? ORDER BY created_at ASC",
                (run_id,),
            ).fetchall()
        return [ApprovalRecord.model_validate_json(row["document_json"]) for row in rows]

    def save_patch(self, patch: PatchCandidate) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO patch_candidates(id, run_id, status, created_at, document_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    document_json=excluded.document_json
                """,
                (
                    patch.id,
                    patch.run_id,
                    patch.status.value,
                    patch.created_at.isoformat(),
                    self._json(patch),
                ),
            )

    def get_patch(self, patch_id: str) -> PatchCandidate | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT document_json FROM patch_candidates WHERE id = ?", (patch_id,)
            ).fetchone()
        return PatchCandidate.model_validate_json(row["document_json"]) if row else None

    def list_patches(self, run_id: str) -> list[PatchCandidate]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT document_json FROM patch_candidates
                WHERE run_id = ? ORDER BY created_at ASC
                """,
                (run_id,),
            ).fetchall()
        return [PatchCandidate.model_validate_json(row["document_json"]) for row in rows]

    def save_incident(self, incident: IncidentContext) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO incidents(
                    incident_id, incident_type, stage, created_at, updated_at, document_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(incident_id) DO UPDATE SET
                    incident_type=excluded.incident_type,
                    stage=excluded.stage,
                    updated_at=excluded.updated_at,
                    document_json=excluded.document_json
                """,
                (
                    incident.incident_id,
                    incident.profile.incident_type.value,
                    incident.stage.value,
                    incident.created_at.isoformat(),
                    incident.updated_at.isoformat(),
                    self._json(incident),
                ),
            )

    def get_incident(self, incident_id: str) -> IncidentContext | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT document_json FROM incidents WHERE incident_id = ?", (incident_id,)
            ).fetchone()
        return IncidentContext.model_validate_json(row["document_json"]) if row else None

    def list_incidents(self, limit: int = 100) -> list[IncidentContext]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT document_json FROM incidents ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [IncidentContext.model_validate_json(row["document_json"]) for row in rows]

    def _save_incident_entity(
        self,
        *,
        entity_type: str,
        entity_id: str,
        incident_id: str,
        created_at: str,
        entity: BaseModel,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO incident_entities(
                    entity_type, entity_id, incident_id, created_at, document_json
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(entity_type, entity_id) DO UPDATE SET
                    incident_id=excluded.incident_id,
                    created_at=excluded.created_at,
                    document_json=excluded.document_json
                """,
                (entity_type, entity_id, incident_id, created_at, self._json(entity)),
            )

    def _list_incident_entities(
        self,
        incident_id: str,
        entity_type: str,
        model: type[IncidentEntity],
    ) -> list[IncidentEntity]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT document_json FROM incident_entities
                WHERE incident_id = ? AND entity_type = ?
                ORDER BY created_at ASC, entity_id ASC
                """,
                (incident_id, entity_type),
            ).fetchall()
        return [model.model_validate_json(row["document_json"]) for row in rows]

    def save_incident_signal(self, signal: IncidentSignal) -> None:
        self._save_incident_entity(
            entity_type="signal",
            entity_id=signal.id,
            incident_id=signal.incident_id,
            created_at=signal.created_at.isoformat(),
            entity=signal,
        )

    def list_incident_signals(self, incident_id: str) -> list[IncidentSignal]:
        return self._list_incident_entities(incident_id, "signal", IncidentSignal)

    def save_root_cause_hypothesis(self, hypothesis: RootCauseHypothesis) -> None:
        self._save_incident_entity(
            entity_type="hypothesis",
            entity_id=hypothesis.id,
            incident_id=hypothesis.incident_id,
            created_at=hypothesis.created_at.isoformat(),
            entity=hypothesis,
        )

    def list_root_cause_hypotheses(self, incident_id: str) -> list[RootCauseHypothesis]:
        return self._list_incident_entities(incident_id, "hypothesis", RootCauseHypothesis)

    def save_incident_experiment(self, experiment: IncidentExperiment) -> None:
        self._save_incident_entity(
            entity_type="experiment",
            entity_id=experiment.id,
            incident_id=experiment.incident_id,
            created_at=experiment.created_at.isoformat(),
            entity=experiment,
        )

    def list_incident_experiments(self, incident_id: str) -> list[IncidentExperiment]:
        return self._list_incident_entities(incident_id, "experiment", IncidentExperiment)

    def save_impact_assessment(self, impact: ImpactAssessment) -> None:
        self._save_incident_entity(
            entity_type="impact",
            entity_id=impact.id,
            incident_id=impact.incident_id,
            created_at=impact.created_at.isoformat(),
            entity=impact,
        )

    def list_impact_assessments(self, incident_id: str) -> list[ImpactAssessment]:
        return self._list_incident_entities(incident_id, "impact", ImpactAssessment)

    def save_remediation_plan(self, plan: RemediationPlan) -> None:
        self._save_incident_entity(
            entity_type="remediation_plan",
            entity_id=plan.id,
            incident_id=plan.incident_id,
            created_at=plan.created_at.isoformat(),
            entity=plan,
        )

    def list_remediation_plans(self, incident_id: str) -> list[RemediationPlan]:
        return self._list_incident_entities(incident_id, "remediation_plan", RemediationPlan)

    def save_incident_approval(self, approval: IncidentApprovalRecord) -> None:
        self._save_incident_entity(
            entity_type="incident_approval",
            entity_id=approval.id,
            incident_id=approval.incident_id,
            created_at=approval.created_at.isoformat(),
            entity=approval,
        )

    def list_incident_approvals(self, incident_id: str) -> list[IncidentApprovalRecord]:
        return self._list_incident_entities(
            incident_id, "incident_approval", IncidentApprovalRecord
        )

    def save_rejudge_batch(self, batch: RejudgeBatch) -> None:
        self._save_incident_entity(
            entity_type="rejudge_batch",
            entity_id=batch.id,
            incident_id=batch.incident_id,
            created_at=batch.created_at.isoformat(),
            entity=batch,
        )

    def list_rejudge_batches(self, incident_id: str) -> list[RejudgeBatch]:
        return self._list_incident_entities(incident_id, "rejudge_batch", RejudgeBatch)

    def save_score_change(self, score_change: ScoreChange) -> None:
        self._save_incident_entity(
            entity_type="score_change",
            entity_id=score_change.id,
            incident_id=score_change.incident_id,
            created_at=score_change.created_at.isoformat(),
            entity=score_change,
        )

    def list_score_changes(self, incident_id: str) -> list[ScoreChange]:
        return self._list_incident_entities(incident_id, "score_change", ScoreChange)

    def save_incident_verification(self, verification: IncidentVerification) -> None:
        self._save_incident_entity(
            entity_type="verification",
            entity_id=verification.id,
            incident_id=verification.incident_id,
            created_at=verification.created_at.isoformat(),
            entity=verification,
        )

    def list_incident_verifications(self, incident_id: str) -> list[IncidentVerification]:
        return self._list_incident_entities(incident_id, "verification", IncidentVerification)
