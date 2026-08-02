import unittest

from fastapi.testclient import TestClient

from backend.app.main import app


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


if __name__ == "__main__":
    unittest.main()
