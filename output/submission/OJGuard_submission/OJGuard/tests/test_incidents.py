from __future__ import annotations

import unittest
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.domain import (
    IncidentApprovalDecision,
    IncidentContext,
    IncidentProfile,
    IncidentSeverity,
    IncidentSignal,
    IncidentStage,
    IncidentType,
    SignalKind,
)
from backend.app.main import app
from backend.app.services.incident_state_machine import (
    InvalidIncidentTransitionError,
    transition_incident,
)
from backend.app.services.playbooks import default_playbook_for, list_playbooks
from backend.app.services.repository import SQLiteRepository


def runtime_incident() -> IncidentContext:
    return IncidentContext(
        incident_id="INC-TEST-001",
        profile=IncidentProfile(
            incident_type=IncidentType.RUNTIME_REGRESSION,
            title="Java runtime regression",
            summary="TLE rate increased after runtime deployment",
            severity=IncidentSeverity.SEV1,
            playbook_id="runtime-regression-v1",
        ),
    )


class IncidentStateMachineTests(unittest.TestCase):
    def test_requires_signal_before_investigation(self) -> None:
        incident = transition_incident(runtime_incident(), IncidentStage.TRIAGING)
        with self.assertRaises(InvalidIncidentTransitionError):
            transition_incident(incident, IncidentStage.INVESTIGATING)

        incident.signal_ids.append("SIG-1")
        investigating = transition_incident(incident, IncidentStage.INVESTIGATING)
        self.assertEqual(investigating.stage, IncidentStage.INVESTIGATING)

    def test_high_risk_gates_cannot_be_skipped(self) -> None:
        incident = runtime_incident()
        incident.stage = IncidentStage.APPROVAL_PENDING
        with self.assertRaisesRegex(InvalidIncidentTransitionError, "approved"):
            transition_incident(incident, IncidentStage.EXECUTING)

        incident.approval_state["execute_plan"] = IncidentApprovalDecision.APPROVED
        executing = transition_incident(incident, IncidentStage.EXECUTING)
        with self.assertRaisesRegex(InvalidIncidentTransitionError, "control experiment"):
            transition_incident(executing, IncidentStage.REJUDGING)


class IncidentRepositoryTests(unittest.TestCase):
    def test_persists_incident_and_typed_entities(self) -> None:
        base = Path(".test-tmp")
        base.mkdir(exist_ok=True)
        database_path = base / f"incident-{uuid4().hex}.sqlite3"
        try:
            repository = SQLiteRepository(database_path)
            incident = runtime_incident()
            repository.save_incident(incident)
            signal = IncidentSignal(
                id="SIG-1",
                incident_id=incident.incident_id,
                kind=SignalKind.METRIC,
                source="monitoring",
                observed_at=datetime.now(UTC),
                summary="Java TLE rate increased",
                dimensions={"language": "java", "tle_rate": 0.42},
            )
            repository.save_incident_signal(signal)

            self.assertEqual(repository.get_incident(incident.incident_id), incident)
            self.assertEqual(repository.list_incident_signals(incident.incident_id), [signal])
        finally:
            database_path.unlink(missing_ok=True)


class PlaybookTests(unittest.TestCase):
    def test_all_incident_types_have_a_default_playbook(self) -> None:
        self.assertGreaterEqual(len(list_playbooks()), 5)
        for incident_type in IncidentType:
            playbook = default_playbook_for(incident_type)
            self.assertEqual(playbook.incident_type, incident_type)
            self.assertTrue(playbook.required_evidence)


class IncidentApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_create_attach_signal_and_transition(self) -> None:
        response = self.client.post(
            "/api/v1/incidents",
            json={
                "incident_type": "runtime_regression",
                "title": "Java TLE spike",
                "summary": "TLE rate increased after deployment",
                "source_systems": ["monitoring", "judge"],
            },
        )
        self.assertEqual(response.status_code, 201)
        incident_id = response.json()["incident_id"]

        triage = self.client.post(
            f"/api/v1/incidents/{incident_id}/transition",
            json={"target": "TRIAGING"},
        )
        self.assertEqual(triage.status_code, 200)

        blocked = self.client.post(
            f"/api/v1/incidents/{incident_id}/transition",
            json={"target": "INVESTIGATING"},
        )
        self.assertEqual(blocked.status_code, 409)

        signal = self.client.post(
            f"/api/v1/incidents/{incident_id}/signals",
            json={
                "kind": "metric",
                "source": "monitoring",
                "observed_at": datetime.now(UTC).isoformat(),
                "summary": "Java TLE rate increased",
                "dimensions": {"language": "java", "tle_rate": 0.42},
            },
        )
        self.assertEqual(signal.status_code, 200)

        investigating = self.client.post(
            f"/api/v1/incidents/{incident_id}/transition",
            json={"target": "INVESTIGATING"},
        )
        self.assertEqual(investigating.status_code, 200)
        self.assertEqual(investigating.json()["stage"], "INVESTIGATING")

        workspace = self.client.get(f"/api/v1/incidents/{incident_id}/workspace")
        self.assertEqual(workspace.status_code, 200)
        self.assertEqual(len(workspace.json()["signals"]), 1)
        self.assertEqual(workspace.json()["playbook"]["id"], "runtime-regression-v1")

    def test_playbook_must_match_incident_type(self) -> None:
        response = self.client.post(
            "/api/v1/incidents",
            json={
                "incident_type": "checker_defect",
                "playbook_id": "runtime-regression-v1",
                "title": "Mismatched playbook",
                "summary": "The request should fail deterministically",
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_precomputed_demo_is_not_exposed_as_public_api(self) -> None:
        response = self.client.post("/api/v1/incidents/demo/checker_defect")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
