import unittest

from update_pocock_sync import MAPPED_CORE_SKILLS, build_sync_payload, parse_skill_tree


class PocockSyncTests(unittest.TestCase):
    def _tree_for(self, eng, prod, wip=(), misc=()):
        items = []
        for cat, names in (
            ("engineering", eng),
            ("productivity", prod),
            ("in-progress", wip),
            ("misc", misc),
        ):
            for n in names:
                items.append({"path": f"skills/{cat}/{n}/SKILL.md"})
        # Noise files should be ignored
        items.append({"path": "README.md"})
        items.append({"path": "skills/scripts/list-skills.sh"})
        return items

    def test_parse_skill_tree_groups_categories(self):
        tree = self._tree_for(
            eng=["implement", "pr"],
            prod=["handoff"],
            wip=["chief-of-staff"],
            misc=["setup-pre-commit"],
        )
        grouped = parse_skill_tree(tree)
        self.assertEqual(grouped["engineering"], ["implement", "pr"])
        self.assertEqual(grouped["productivity"], ["handoff"])
        self.assertEqual(grouped["in-progress"], ["chief-of-staff"])
        self.assertEqual(grouped["misc"], ["setup-pre-commit"])

    def test_in_sync_when_core_skills_match(self):
        eng = [s for s in MAPPED_CORE_SKILLS if s not in {
            "grill-me", "grilling", "handoff", "teach",
            "to-questionnaire", "wait-what", "writing-for-agents",
        }]
        prod = [
            "grill-me", "grilling", "handoff", "teach",
            "to-questionnaire", "wait-what", "writing-for-agents",
        ]
        payload = build_sync_payload(
            {"tag_name": "v1.3.2", "published_at": "2026-10-29T10:27:41Z"},
            self._tree_for(eng=eng, prod=prod, wip=["chief-of-staff"]),
            checked_at="2026-11-23T22:40:00Z",
        )
        self.assertTrue(payload["in_sync"])
        self.assertEqual(payload["mapped_count"], 27)
        self.assertEqual(payload["upstream_core_count"], 27)
        self.assertEqual(payload["added_upstream"], [])
        self.assertEqual(payload["removed_upstream"], [])

    def test_detects_added_and_removed_upstream_skills(self):
        tree = self._tree_for(
            eng=["ask-matt", "new-v14-skill"],
            prod=["handoff"],
        )
        payload = build_sync_payload(
            {"tag_name": "v1.4.0", "published_at": "2026-12-01T00:00:00Z"},
            tree,
            checked_at="2026-12-02T00:00:00Z",
            mapped_core=["ask-matt", "handoff", "retired-skill"],
        )
        self.assertFalse(payload["in_sync"])
        self.assertEqual(payload["added_upstream"], ["new-v14-skill"])
        self.assertEqual(payload["removed_upstream"], ["retired-skill"])


if __name__ == "__main__":
    unittest.main()
