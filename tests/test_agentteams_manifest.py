import unittest
from pathlib import Path

import yaml


class AgentTeamsManifestTests(unittest.TestCase):
    def test_team_has_one_leader_four_workers_and_controlled_mcp(self) -> None:
        path = Path(__file__).parents[1] / "agentteams" / "ojguard-team.yaml"
        documents = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        workers = [item for item in documents if item["kind"] == "Worker"]
        teams = [item for item in documents if item["kind"] == "Team"]
        self.assertEqual(len(workers), 5)
        self.assertEqual(len(teams), 1)
        members = teams[0]["spec"]["workerMembers"]
        self.assertEqual(sum(item["role"] == "team_leader" for item in members), 1)
        self.assertEqual(sum(item["role"] == "worker" for item in members), 4)
        for worker in workers:
            self.assertEqual(worker["apiVersion"], "agentteams.io/v1beta1")
            self.assertEqual(worker["spec"]["model"], "deepseek-chat")
            self.assertEqual(
                worker["spec"]["mcpServers"][0]["url"],
                "http://host.docker.internal:8020/mcp",
            )
            self.assertNotIn("apiKey", worker["spec"])
        leader = next(item for item in workers if item["metadata"]["name"].endswith("manager"))
        self.assertIn("Never approve", leader["spec"]["soul"])


if __name__ == "__main__":
    unittest.main()
