import unittest
from pathlib import Path

import yaml


class AgentTeamsKubernetesDeploymentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).parents[1]

    def test_kind_profile_uses_kubernetes_backend_and_saves_preflight_cost(self) -> None:
        values = yaml.safe_load(
            (self.root / "agentteams" / "values-kind.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(values["controller"]["workerBackend"], "k8s")
        self.assertFalse(values["preflight"]["llm"]["enabled"])
        self.assertEqual(values["manager"]["runtime"], "openclaw")
        self.assertEqual(values["worker"]["defaultRuntime"], "openclaw")

        manager = yaml.safe_load(
            (self.root / "agentteams" / "manager-budget.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(manager["spec"]["config"]["heartbeatInterval"], "24h")

        documents = list(
            yaml.safe_load_all(
                (self.root / "agentteams" / "ojguard-team.yaml").read_text(encoding="utf-8")
            )
        )
        team = next(item for item in documents if item["kind"] == "Team")
        self.assertEqual(team["spec"]["heartbeatEvery"], "")

    def test_committed_agentteams_files_contain_no_runtime_socket_or_secret(self) -> None:
        paths = [
            self.root / "agentteams" / "kind-config.yaml",
            self.root / "agentteams" / "values-kind.yaml",
            self.root / "agentteams" / "manager-budget.yaml",
            self.root / "agentteams" / "ojguard-team.yaml",
        ]
        joined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        self.assertNotIn("docker.sock", joined)
        self.assertNotIn("DEEPSEEK_API_KEY=", joined)
        self.assertNotRegex(joined, r"sk-[A-Za-z0-9]")

    def test_setup_script_pins_chart_and_kind_node_digests(self) -> None:
        script = (self.root / "scripts" / "setup_agentteams_k8s.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("agentteams-1.2.0.tgz", script)
        self.assertIn("sha256:452d707d", script)
        self.assertIn("f530879c26cc4e3e", script)
        self.assertIn(".runtime", script)
        self.assertIn("manager-budget.yaml", script)

    def test_mcp_and_demo_scripts_preserve_the_safe_boundary(self) -> None:
        start_script = (self.root / "scripts" / "start_ojguard_mcp.ps1").read_text(
            encoding="utf-8"
        )
        demo_script = (self.root / "scripts" / "run_agentteams_demo.ps1").read_text(
            encoding="utf-8"
        )
        server = (self.root / "mcp_server" / "server.py").read_text(encoding="utf-8")

        self.assertIn('$env:MCP_HOST = "127.0.0.1"', start_script)
        self.assertNotIn('$env:MCP_HOST = "0.0.0.0"', start_script)
        self.assertIn("enable_dns_rebinding_protection=True", server)
        self.assertIn("host.docker.internal", server)
        self.assertIn("All six workers replied", demo_script)
        self.assertIn("ojguard-incident-team", demo_script)
        self.assertIn("OJGUARD_DEMO_COMPLETE", demo_script)


if __name__ == "__main__":
    unittest.main()
