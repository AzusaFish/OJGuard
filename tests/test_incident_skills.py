from __future__ import annotations

import unittest
from pathlib import Path

import yaml


class IncidentSkillTests(unittest.TestCase):
    def test_nine_skills_have_complete_operational_contracts(self) -> None:
        root = Path(__file__).parents[1] / "skills"
        skill_files = sorted(root.glob("*/SKILL.md"))
        self.assertEqual(len(skill_files), 9)
        required_terms = (
            "Version:",
            "Inputs:",
            "Outputs:",
            "Invocation condition:",
            "Error",
            "Safety",
            "Idempotency key:",
            "Acceptance:",
            "Dependent tools:",
            "Agent collaboration:",
            "Reuse value:",
        )
        for path in skill_files:
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), path)
            frontmatter = yaml.safe_load(text.split("---", 2)[1])
            self.assertEqual(frontmatter["name"], path.parent.name)
            self.assertTrue(frontmatter["description"])
            for term in required_terms:
                self.assertIn(term, text, f"{path}: missing {term}")
            agent = yaml.safe_load(
                (path.parent / "agents" / "openai.yaml").read_text(encoding="utf-8")
            )
            self.assertTrue(agent["interface"]["display_name"])
            self.assertEqual(agent["dependencies"]["tools"][0]["value"], "ojguard")


if __name__ == "__main__":
    unittest.main()
