import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from radar.business_graph import BusinessModelError, build_business_graph, validate_business_model
from radar.model import load_pack
from radar.discover import run_discovery

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

    def test_process_steps_and_criterion_entity_links_are_explicit_candidates(self):
        _, pack, model = self._data()
        requirement = {"id":"req_d03","key":"D03","version":1,"title":"材料采购",
            "acceptance_criteria":[{"id":"D03-C5","description":"采购收货逐行关联采购订单，支持分批收货。","required":True}]}
        graph = build_business_graph(model, pack, requirements=[requirement])
        self.assertTrue(any(e["relation"] == "has_step" for e in graph["edges"]))
        candidates = [e for e in graph["edges"] if e["relation"] == "candidate_requires"]
        self.assertTrue(candidates)
        self.assertTrue(all(e["status"] == "candidate_only" for e in candidates))

    def test_business_graph_cli_reads_workspace_and_writes_projection(self):
        root, pack, model = self._data()
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp) / "store"
            pack_path = root / "packs/weak-current/pack.json"
            run_discovery("ws_business_graph_cli", str(root / "examples/requirements/d03-material-procurement.json"),
                str(pack_path), str(root / "seeds/weak-current.json"), str(workspace_root))
            output = Path(tmp) / "business-graph.json"
            proc = subprocess.run([sys.executable, "-m", "radar", "business-graph",
                "--workspace", "ws_business_graph_cli", "--workspace-root", str(workspace_root),
                "--pack", str(pack_path), "--business-model", str(root / "packs/weak-current/business-model.json"),
                "--out", str(output)], cwd=str(root), capture_output=True, text=True, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            graph = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(graph["counts"]["entities"], 7)
            self.assertEqual(graph["counts"]["evidence"], 0)
            self.assertEqual(graph["counts"]["candidate_entity_mentions"], 0)
            self.assertEqual(graph["counts"]["criteria_no_evidence"], 11)
            self.assertEqual(graph["counts"]["criterion_candidate_evidence_links"], 0)
            self.assertEqual(graph["workspace_id"], "ws_business_graph_cli")
            self.assertEqual(len(graph["discovery_run_ids"]), 1)
            self.assertEqual(len([n for n in graph["nodes"] if n["kind"] == "acceptance_criterion"]), 11)

    def test_projection_is_deterministic(self):
        _, pack, model = self._data()
        assets = [{"id":"ast_file_1","title":"x","asset_type":"file","uri":"https://x"}]
        evidence = [{"id":"evd_1","asset_id":"ast_file_1","statement":"Purchase Order",
                     "locator":{"path":"x","line_start":1},"verification_status":"unverified"}]
        self.assertEqual(build_business_graph(model, pack, assets=assets, evidence=evidence),
                         build_business_graph(model, pack, assets=assets, evidence=evidence))

if __name__ == "__main__":
    unittest.main()
