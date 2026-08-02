from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from backend.app.domain import (
    AgentEvent,
    ApprovalRecord,
    Evidence,
    Finding,
    PatchCandidate,
    TaskContext,
)


class SQLiteRepository:
    """Small durable store for the initial-round single-user deployment."""

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
