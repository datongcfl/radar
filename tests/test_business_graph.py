import json
import unittest
from pathlib import Path
from radar.business_graph import BusinessModelError, build_business_graph, validate_business_model
from radar.model import load_pack

class TestBusinessGraph(unittest.TestCase):
    def _data(self):
        root = Path(__file__).resolve().parents[1]
        pack = load_pack(root / "packs/weak-current/pack.json")
        model = json.loads((root / "packs/weak-current/business-model.json").read_text(encoding="utf-8"))
        return root, pack, model

    def test_weak_current_business_model_is_valid(self):
        _, pack, model = self._data()
        self.assertEqual(validate_business_model(model, pack)["pack"], "weak-current")
        self.assertEqual(len(model["entities"]), 7)
        self.assertEqual(len(model["exceptions"]), 6)

    def test_unknown_transition_endpoint_is_rejected(self):
        _, pack, model = self._data()
        model["processes"][0]["transitions"][0]["to"] = "missing_entity"
        with self.assertRaises(BusinessModelError):
            validate_business_model(model, pack)

    def test_term_match_is_candidate_only_and_provenance_is_retained(self):
        _, pack, model = self._data()
        assets = [{"id":"ast_file_1","title":"purchase_receipt.py","asset_type":"file",
                   "uri":"https://example.test/purchase_receipt.py","version_ref":"abc"}]
        evidence = [{"id":"evd_receipt_1","asset_id":"ast_file_1","evidence_kind":"code",
                     "statement":"purchase receipt validates rejected_qty and accepted_qty",
                     "excerpt":"quality inspection","locator":{"path":"purchase_receipt.py","line_start":20},
                     "verification_status":"source_confirmed"}]
        graph = build_business_graph(model, pack, assets=assets, evidence=evidence)
        matches = [e for e in graph["edges"] if e["relation"] == "candidate_mention"]
        self.assertTrue(matches)
        self.assertTrue(all(e["status"] == "candidate_only" for e in matches))
        self.assertTrue(all(e["evidence_ids"] == ["evd_receipt_1"] for e in matches))
        self.assertTrue(all(e["provenance"]["locator"]["path"] == "purchase_receipt.py" for e in matches))
        self.assertFalse(any(e["relation"] in ("implements", "supports") for e in graph["edges"]))

    def test_declared_transitions_are_not_claimed_as_verified(self):
        _, pack, model = self._data()
        graph = build_business_graph(model, pack)
        declared = [e for e in graph["edges"] if e["relation"] == "declared_transition"]
        self.assertTrue(declared)
        self.assertTrue(all(e["status"] == "declared_not_verified" for e in declared))
        self.assertTrue(all(not e["evidence_ids"] for e in declared))

    def test_projection_is_deterministic(self):
        _, pack, model = self._data()
        assets = [{"id":"ast_file_1","title":"x","asset_type":"file","uri":"https://x"}]
        evidence = [{"id":"evd_1","asset_id":"ast_file_1","statement":"Purchase Order",
                     "locator":{"path":"x","line_start":1},"verification_status":"unverified"}]
        self.assertEqual(build_business_graph(model, pack, assets=assets, evidence=evidence),
                         build_business_graph(model, pack, assets=assets, evidence=evidence))

if __name__ == "__main__":
    unittest.main()
