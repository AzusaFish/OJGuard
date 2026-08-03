import unittest
from pathlib import Path

from backend.app.config import Settings
from backend.app.services.agentteams_dispatcher import AgentTeamsDispatcher


class AgentTeamsPrimaryFlowTests(unittest.TestCase):
    def test_live_dispatch_is_disabled_until_explicitly_authorized(self) -> None:
        settings = Settings(
            _env_file=None,
            llm_real_calls_enabled=False,
            deepseek_api_key=None,
        )
        readiness = AgentTeamsDispatcher(
            settings,
            repository_root=Path("missing-agentteams-runtime"),
        ).readiness()
        self.assertFalse(readiness.ready)
        self.assertFalse(readiness.real_calls_enabled)
        self.assertFalse(readiness.api_key_configured)
        self.assertIn("尚未允许真实模型调用", readiness.message)

    def test_frontend_uses_agent_run_instead_of_precomputed_demo(self) -> None:
        root = Path(__file__).resolve().parents[1]
        store = (root / "frontend" / "src" / "stores" / "incidents.ts").read_text(
            encoding="utf-8"
        )
        incident_list = (
            root / "frontend" / "src" / "views" / "IncidentsView.vue"
        ).read_text(encoding="utf-8")
        detail = (
            root / "frontend" / "src" / "views" / "IncidentDetailView.vue"
        ).read_text(encoding="utf-8")
        launcher = (root / "scripts" / "run_agentteams_demo.ps1").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("/incidents/demo/", store)
        self.assertNotIn("prepareDemo", store)
        self.assertNotIn("async operate(", store)
        self.assertIn("/agent-runs", store)
        self.assertIn("startAgentIncident", incident_list)
        self.assertIn("Agent 协同", detail)
        self.assertNotIn("执行控制组与灰度</button>", detail)
        self.assertNotIn("执行全量重评</button>", detail)
        self.assertIn("function Wait-ApprovalGate", launcher)
        self.assertIn("Real AgentTeams model calls are disabled", launcher)
        self.assertIn("if ($AutoApprove)", launcher)
        self.assertIn("Wait-ApprovalGate -Gate $gate", launcher)
        self.assertNotIn("-AutoApprove", detail)
        self.assertIn('Invoke-RuntimeControl @("events", "--run-id"', launcher)
        self.assertIn("ROUTE_DECISION incident_id=$IncidentId", launcher)
        self.assertIn("Final report is not bound to the current incident_id", launcher)
        self.assertIn('([string]$_.summary).Contains($IncidentId)', launcher)


if __name__ == "__main__":
    unittest.main()
