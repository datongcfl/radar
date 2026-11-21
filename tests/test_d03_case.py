import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

from radar.discover import run_discovery


class TestD03MaterialProcurementCase(unittest.TestCase):
    def setUp(self):
        self.requirement = json.loads(
            (ROOT / "examples" / "requirements" / "d03-material-procurement.json").read_text(
                encoding="utf-8"
            )
        )
        self.case = (ROOT / "docs" / "cases" / "D03-MATERIAL-PROCUREMENT.md").read_text(
            encoding="utf-8"
        )

    def test_requirement_has_unique_critical_acceptance_criteria(self):
        self.assertEqual(self.requirement["schema_version"], 1)
        requirements = self.requirement["requirements"]
        self.assertEqual(len(requirements), 1)
        requirement = requirements[0]
        self.assertEqual(requirement["key"], "D03")
        self.assertEqual(requirement["version"], 1)
        criteria = requirement["acceptance_criteria"]
        self.assertGreaterEqual(len(criteria), 10)
        ids = [criterion["id"] for criterion in criteria]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(criterion.get("required") for criterion in criteria))
        self.assertTrue(all(criterion.get("description") for criterion in criteria))

    def test_case_maps_every_criterion_and_preserves_evidence_limits(self):
        criteria = self.requirement["requirements"][0]["acceptance_criteria"]
        for criterion in criteria:
            self.assertIn(criterion["id"], self.case)
        self.assertIn("no_evidence", self.case)
        self.assertIn("not_assessed", self.case)
        self.assertIn("GITHUB_TOKEN", self.case)
        self.assertIn("GPL-3.0", self.case)
        self.assertIn("a8ea38cb75dd00f51212d4072de24ec580ad6c84", self.case)


    def test_d03_requirement_runs_through_real_offline_discover_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_discovery(
                "ws_d03_offline_test",
                str(ROOT / "examples" / "requirements" / "d03-material-procurement.json"),
                str(ROOT / "packs" / "weak-current" / "pack.json"),
                str(ROOT / "seeds" / "weak-current.json"),
                workspace_root=tmp,
                github=False,
            )
        self.assertEqual(result["run_status"], "partial")
        self.assertEqual(len(result["assessments"]), 1)
        self.assertEqual(result["assessments"][0]["requirement_key"], "D03")
        self.assertEqual(result["assessments"][0]["status"], "no_evidence")
        self.assertGreater(result["assessments"][0]["candidate_assets"], 0)


if __name__ == "__main__":
    unittest.main()
