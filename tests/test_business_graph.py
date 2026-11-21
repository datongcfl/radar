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
            observations_path = Path(tmp) / "observations.json"
            observations_path.write_text(json.dumps({"schema_version":1,"observations":[]}),
                                         encoding="utf-8")
            proc = subprocess.run([sys.executable, "-m", "radar", "business-graph",
                "--workspace", "ws_business_graph_cli", "--workspace-root", str(workspace_root),
                "--pack", str(pack_path), "--business-model", str(root / "packs/weak-current/business-model.json"),
                "--observations", str(observations_path), "--out", str(output)],
                cwd=str(root), capture_output=True, text=True, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            graph = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(graph["counts"]["entities"], 7)
            self.assertEqual(graph["counts"]["evidence"], 0)
            self.assertEqual(graph["counts"]["candidate_entity_mentions"], 0)
            self.assertEqual(graph["counts"]["criteria_no_evidence"], 11)
            self.assertEqual(graph["counts"]["criterion_candidate_evidence_links"], 0)
            self.assertEqual(graph["counts"]["invariant_evaluations"], 0)
            self.assertEqual(graph["counts"]["invariants_without_observations"], 6)
            self.assertEqual(graph["counts"]["criteria_with_invariant_mappings"], 6)
            self.assertEqual(graph["workspace_id"], "ws_business_graph_cli")
            self.assertTrue(all(item["invariant_status"] == "no_observation"
                                for item in graph["criterion_evidence_matrix"] if item["invariant_ids"]))
            self.assertEqual(len(graph["discovery_run_ids"]), 1)
            self.assertEqual(len([n for n in graph["nodes"] if n["kind"] == "acceptance_criterion"]), 11)

    def test_criterion_evidence_matrix_and_cross_file_transition_are_candidates(self):
        _, pack, model = self._data()
        requirement = {"id":"req_d03","key":"D03","version":1,"title":"材料采购",
            "acceptance_criteria":[{"id":"D03-C5","description":"采购收货关联采购订单，支持分批收货。","required":True}]}
        assets = [{"id":"ast_order","title":"order.py","asset_type":"file","uri":"https://x/order.py"},
                  {"id":"ast_receipt","title":"receipt.py","asset_type":"file","uri":"https://x/receipt.py"}]
        evidence = [
            {"id":"evd_order","asset_id":"ast_order","statement":"purchase order item qty",
             "excerpt":"Purchase Order","locator":{"path":"order.py","line_start":20},"verification_status":"unverified"},
            {"id":"evd_receipt","asset_id":"ast_receipt","statement":"purchase receipt received_qty accepted_qty",
             "excerpt":"Purchase Receipt","locator":{"path":"receipt.py","line_start":10},"verification_status":"source_confirmed"}]
        relationships = [{"id":"rel_cross","from":{"object_type":"asset","id":"ast_order"},
            "to":{"object_type":"asset","id":"ast_receipt"},"relation_type":"depends_on","status":"active",
            "evidence_ids":["evd_order","evd_receipt"]}]
        graph = build_business_graph(model, pack, requirements=[requirement],
            assets=assets, evidence=evidence, relationships=relationships)
        matrix = graph["criterion_evidence_matrix"][0]
        self.assertEqual(matrix["status"], "candidate_evidence")
        self.assertEqual(set(matrix["candidate_evidence_ids"]), {"evd_order", "evd_receipt"})
        candidate_edges = [e for e in graph["edges"] if e["relation"] == "candidate_evidence_for"]
        self.assertEqual(len(candidate_edges), 2)
        self.assertTrue(all(e["status"] == "candidate_only" for e in candidate_edges))
        transition_edges = [e for e in graph["edges"] if e["relation"] == "candidate_transition"]
        self.assertTrue(transition_edges)
        self.assertEqual(set(transition_edges[0]["evidence_ids"]), {"evd_order", "evd_receipt"})
        self.assertFalse(any(e["relation"] in ("implements", "supports") for e in graph["edges"]))

    def test_criterion_without_matching_evidence_is_explicit_no_evidence(self):
        _, pack, model = self._data()
        requirement = {"id":"req_d03","key":"D03","version":1,"title":"材料采购",
            "acceptance_criteria":[{"id":"D03-C10","description":"库存价值与总账一致。","required":True}]}
        graph = build_business_graph(model, pack, requirements=[requirement])
        matrix = graph["criterion_evidence_matrix"][0]
        self.assertEqual(matrix["status"], "no_evidence")
        self.assertEqual(matrix["candidate_evidence_ids"], [])

    def test_code_state_transition_is_exposed_as_unverified_candidate(self):
        _, pack, model = self._data()
        evidence = [{"id":"evd_state","asset_id":"ast_code","statement":"Draft -> Submitted",
            "locator":{"path":"receipt.py","line_start":4,"line_end":5},
            "metadata":{"code_analysis":{"kind":"state_transition_candidate",
                "from_state":"Draft","to_state":"Submitted","scope":["function:submit"],
                "inference_status":"candidate_only"}}}]
        graph = build_business_graph(model, pack,
            assets=[{"id":"ast_code","title":"receipt.py","asset_type":"file","uri":"https://x/receipt.py"}],
            evidence=evidence)
        state_nodes = [n for n in graph["nodes"] if n["kind"] == "code_state_transition"]
        self.assertEqual(len(state_nodes), 1)
        self.assertEqual(state_nodes[0]["from_state"], "Draft")
        self.assertEqual(state_nodes[0]["to_state"], "Submitted")
        self.assertEqual(state_nodes[0]["inference_status"], "candidate_only")
        self.assertEqual(graph["counts"]["candidate_code_state_transitions"], 1)

    def test_pack_invariants_are_declared_not_evaluated(self):
        _, pack, model = self._data()
        model["invariants"] = [{
            "id":"qty_balance","name":"Quantity balance","description":"Accepted plus rejected equals received.",
            "operator":"sum_equals","scope":"receipt_item","fields":["accepted","rejected"],
            "target_field":"received","related_entities":["purchase_receipt"],
            "required_evidence":["receipt lines","quality record"],"risk":"quantity mismatch"}]
        graph = build_business_graph(model, pack)
        invariant_nodes = [n for n in graph["nodes"] if n["kind"] == "business_invariant"]
        self.assertEqual(len(invariant_nodes), 1)
        self.assertEqual(invariant_nodes[0]["verification_status"], "declared_not_verified")
        self.assertTrue(any(e["relation"] == "constrains_entity" for e in graph["edges"]))
        model["invariants"][0]["operator"] = "execute_python"
        with self.assertRaises(BusinessModelError):
            build_business_graph(model, pack)

    def test_structured_observation_evaluates_invariant_with_evidence_links(self):
        _, pack, model = self._data()
        invariant = next(item for item in model["invariants"]
                         if item["id"] == "receipt_quantity_balance")
        evidence = [{"id":"evd_qty","asset_id":"ast_receipt","statement":"receipt quantity fixture",
                     "locator":{"path":"receipt.json","line_start":1},
                     "metadata":{"verification":{"level":"ci_check_success","runtime_observed":False}}}]
        values = {"accepted_qty":8,"rejected_qty":2,"received_qty":10}
        provenance = {field:{"evidence_id":"evd_qty",
                     "locator":{"path":"receipt.json","field":field},
                     "verification_level":"ci_check_success","runtime_observed":False}
                     for field in values}
        observations = {"schema_version":1,"observations":[{
            "id":"obs_receipt_1","invariant_id":invariant["id"],"scope_key":"receipt-item-1",
            "origin":"test","values":values,"field_provenance":provenance}]}
        requirement = {"id":"req_d03","key":"D03","version":1,"title":"材料采购",
            "acceptance_criteria":[{"id":"D03-C6","description":"区分实收、合格和拒收数量。",
                                    "required":True,"invariant_ids":[invariant["id"]]}]}
        graph = build_business_graph(model, pack, requirements=[requirement],
            assets=[{"id":"ast_receipt","title":"receipt.json","asset_type":"file","uri":"https://x/receipt.json"}],
            evidence=evidence, observations=observations)
        result = graph["invariant_evaluations"]["evaluations"][0]
        self.assertEqual(result["outcome"], "pass")
        self.assertEqual(result["verification_level"], "test_fixture")
        self.assertEqual(graph["counts"]["invariant_evaluations"], 1)
        self.assertTrue(any(edge["relation"] == "derived_from_observation"
                            and edge["evidence_ids"] == ["evd_qty"] for edge in graph["edges"]))
        self.assertEqual(graph["counts"]["invariants_passed"], 1)
        criterion = graph["criterion_evidence_matrix"][0]
        self.assertEqual(criterion["invariant_ids"], [invariant["id"]])
        self.assertEqual(criterion["invariant_status"], "computed_pass")
        self.assertEqual(criterion["invariant_evaluation_ids"], ["obs_receipt_1"])
        self.assertTrue(any(edge["relation"] == "has_invariant_evaluation"
                            and edge["status"] == "computed_not_assessed" for edge in graph["edges"]))

    def test_unknown_criterion_invariant_reference_is_rejected(self):
        _, pack, model = self._data()
        requirement = {"id":"req_d03","key":"D03","version":1,"title":"材料采购",
            "acceptance_criteria":[{"id":"D03-CX","description":"测试规则映射。",
                                    "required":True,"invariant_ids":["not_a_pack_rule"]}]}
        with self.assertRaises(BusinessModelError):
            build_business_graph(model, pack, requirements=[requirement])

    def test_invariant_rejects_non_finite_tolerance_and_duplicate_fields(self):
        _, pack, model = self._data()
        model["invariants"][0]["tolerance"] = float("nan")
        with self.assertRaises(BusinessModelError):
            validate_business_model(model, pack)
        _, pack, model = self._data()
        model["invariants"][0]["fields"] = ["accepted_qty", "accepted_qty"]
        with self.assertRaises(BusinessModelError):
            validate_business_model(model, pack)

    def test_field_aliases_must_be_unambiguous(self):
        _, pack, model = self._data()
        model["invariants"][0]["field_aliases"] = {
            "accepted_qty":["quantity"],
            "rejected_qty":[" quantity "],
            "received_qty":["received"],
        }
        with self.assertRaises(BusinessModelError):
            validate_business_model(model, pack)

    def test_scope_aliases_must_be_declared_and_unambiguous(self):
        _, pack, model = self._data()
        model["invariants"][0]["scope_fields"] = ["purchase_order_id"]
        model["invariants"][0]["scope_aliases"] = {
            "purchase_order_id":["合格数量"],
        }
        with self.assertRaises(BusinessModelError):
            validate_business_model(model, pack)

    def test_projection_is_deterministic(self):
        _, pack, model = self._data()
        assets = [{"id":"ast_file_1","title":"x","asset_type":"file","uri":"https://x"}]
        evidence = [{"id":"evd_1","asset_id":"ast_file_1","statement":"Purchase Order",
                     "locator":{"path":"x","line_start":1},"verification_status":"unverified"}]
        self.assertEqual(build_business_graph(model, pack, assets=assets, evidence=evidence),
                         build_business_graph(model, pack, assets=assets, evidence=evidence))

if __name__ == "__main__":
    unittest.main()
