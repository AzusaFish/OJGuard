import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.agentteams_dispatcher import AgentTeamsDispatcherError


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_does_not_expose_secret(self) -> None:
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["service"], "OJGuard")
        self.assertNotIn("api_key", payload)

    def test_rag_is_explicitly_disabled(self) -> None:
        response = self.client.get("/api/v1/rag/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "RAG_DISABLED")

    def test_system_contract_exposes_ports_but_not_secret(self) -> None:
        response = self.client.get("/api/v1/system")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["rag"]["port"], 8010)
        self.assertEqual(payload["mcp"]["port"], 8020)
        self.assertEqual(payload["agentteams"]["version"], "v1.2.0")
        self.assertNotIn("api_key", response.text.casefold())

    def test_benchmark_report_is_served(self) -> None:
        response = self.client.get("/api/v1/benchmark/report")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["case_count"], 10)

    def test_run_transition_contract(self) -> None:
        response = self.client.post("/api/v1/runs", json={"package_id": "PKG-001"})
        self.assertEqual(response.status_code, 201)
        run_id = response.json()["run_id"]
        transitioned = self.client.post(
            f"/api/v1/runs/{run_id}/transition",
            json={"target": "BASELINE_VALIDATING"},
        )
        self.assertEqual(transitioned.status_code, 200)
        self.assertEqual(transitioned.json()["stage"], "BASELINE_VALIDATING")

    def test_agent_run_snapshot_and_event_query_contract(self) -> None:
        task_id = f"API-AGENT-RUN-{uuid4().hex[:8]}"
        created = self.client.post(
            "/api/v1/agent-runs",
            json={
                "incident_type": "node_degradation",
                "task_id": task_id,
                "max_model_responses": 8,
            },
        )
        self.assertEqual(created.status_code, 201)
        payload = created.json()
        run_id = payload["run"]["run_id"]
        self.assertEqual(payload["incident"]["stage"], "TRIAGING")
        self.assertEqual(payload["legal_options"][0]["action"], "triage")
        incident_id = payload["incident"]["incident_id"]

        workspace = self.client.get(f"/api/v1/incidents/{incident_id}/workspace")
        self.assertEqual(workspace.status_code, 200)
        self.assertEqual(workspace.json()["hypotheses"], [])
        self.assertEqual(workspace.json()["experiments"], [])
        self.assertEqual(workspace.json()["impacts"], [])
        self.assertEqual(workspace.json()["remediation_plans"], [])

        by_incident = self.client.get(
            "/api/v1/agent-runs",
            params={"incident_id": incident_id},
        )
        self.assertEqual(by_incident.status_code, 200)
        self.assertEqual(by_incident.json()[0]["run_id"], run_id)

        snapshot = self.client.get(f"/api/v1/agent-runs/{run_id}")
        self.assertEqual(snapshot.status_code, 200)
        self.assertEqual(snapshot.json()["run"]["task_id"], task_id)
        events = self.client.get(f"/api/v1/agent-runs/{run_id}/events")
        self.assertEqual(events.status_code, 200)
        self.assertEqual(events.json()[0]["event_type"], "RUN_CREATED")

        with patch(
            "backend.app.api.agent_runs.AgentTeamsDispatcher.launch",
            side_effect=AgentTeamsDispatcherError("runtime not ready"),
        ):
            launch = self.client.post(
                f"/api/v1/agent-runs/{run_id}/launch",
                json={"approval_actor": "test-operator"},
            )
        self.assertEqual(launch.status_code, 409)
        rolled_back = self.client.get(f"/api/v1/agent-runs/{run_id}")
        self.assertEqual(rolled_back.json()["run"]["status"], "QUEUED")

    def test_agent_run_launch_claim_prevents_duplicate_processes(self) -> None:
        created = self.client.post(
            "/api/v1/agent-runs",
            json={
                "incident_type": "runtime_regression",
                "task_id": f"API-LAUNCH-CLAIM-{uuid4().hex[:8]}",
                "max_model_responses": 8,
            },
        )
        self.assertEqual(created.status_code, 201)
        run_id = created.json()["run"]["run_id"]
        with patch(
            "backend.app.api.agent_runs.AgentTeamsDispatcher.launch",
            return_value=SimpleNamespace(pid=12345),
        ) as launch_process:
            first = self.client.post(
                f"/api/v1/agent-runs/{run_id}/launch",
                json={"approval_actor": "test-operator"},
            )
            second = self.client.post(
                f"/api/v1/agent-runs/{run_id}/launch",
                json={"approval_actor": "test-operator"},
            )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["status"], "STARTING")
        self.assertEqual(second.status_code, 409)
        self.assertEqual(launch_process.call_count, 1)
        snapshot = self.client.get(f"/api/v1/agent-runs/{run_id}")
        self.assertEqual(snapshot.json()["run"]["status"], "STARTING")


if __name__ == "__main__":
    unittest.main()
