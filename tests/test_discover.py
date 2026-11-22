import tempfile
import unittest
import subprocess
import sys
from pathlib import Path

from radar.discover import run_discovery
from radar.discovery_store import JsonWorkspaceStore
from radar.discovery import new_record


class TestDiscoverWorkflow(unittest.TestCase):
    def _paths(self):
        root = Path(__file__).resolve().parents[1]
        return (str(root / "examples" / "requirements" / "weak-current.json"),
                str(root / "packs" / "weak-current" / "pack.json"),
                str(root / "seeds" / "weak-current.json"))

    def test_offline_discover_persists_assets_and_assessments(self):
        requirements, pack, seeds = self._paths()
        with tempfile.TemporaryDirectory() as tmp:
            result = run_discovery("ws_discover_test", requirements, pack, seeds, tmp)
            self.assertEqual(result["run_status"], "partial")
            self.assertEqual(result["ledger_control"], {"status": "skipped", "reason": "pack_opt_in_absent"})
            self.assertEqual(result["counts"]["assets"], 35)
            self.assertEqual(result["counts"]["pending_quotes"], 23)
            self.assertEqual(len(result["assessments"]), 5)
            d03 = next(x for x in result["assessments"] if x["requirement_key"] == "D03")
            self.assertEqual(d03["status"], "no_evidence")
            self.assertGreater(d03["candidate_assets"], 0)
            self.assertEqual(d03["evidence"], 0)
            store = JsonWorkspaceStore(tmp, "ws_discover_test")
            self.assertEqual(len(store.list_records("asset")), 35)
            self.assertEqual(len(store.list_records("assessment")), 5)
            self.assertEqual(len(store.list_pending_quotes()), 23)
            self.assertIsNotNone(store.get("discovery_run", result["run_id"]))

    def test_github_discovery_creates_cell_evidence_and_observation_bundle(self):
        requirements, pack, seeds = self._paths()
        root = Path(__file__).resolve().parents[1]
        business_model = root / "packs" / "weak-current" / "business-model.json"
        with tempfile.TemporaryDirectory() as tmp:
            def fake_github(requirement_rows, pack_data, workspace_id, **kwargs):
                source = new_record("source", provider="github",
                    uri="https://github.com", name="github.com",
                    access_status="public").to_dict()
                asset = new_record("asset", source_id=source["id"],
                    asset_type="file",
                    uri="https://github.com/acme/erp/blob/abc/receipts.csv",
                    title="receipts.csv", version_ref="abc",
                    status="active", metadata={}).to_dict()
                chunks = [
                    {"text":"accepted_qty","locator":{"path":"receipts.csv","row":1,"column":1}},
                    {"text":"rejected_qty","locator":{"path":"receipts.csv","row":1,"column":2}},
                    {"text":"received_qty","locator":{"path":"receipts.csv","row":1,"column":3}},
                    {"text":"8","locator":{"path":"receipts.csv","row":2,"column":1}},
                    {"text":"2","locator":{"path":"receipts.csv","row":2,"column":2}},
                    {"text":"10","locator":{"path":"receipts.csv","row":2,"column":3}},
                ]
                evidence = []
                for index, chunk in enumerate(chunks[3:]):
                    evidence.append(new_record("evidence",
                        workspace_id=workspace_id, asset_id=asset["id"],
                        evidence_kind="documentation", statement=chunk["text"],
                        locator=chunk["locator"],
                        captured_at="2026-11-22T00:00:00Z",
                        verification_status="source_confirmed",
                        metadata={"verification":{"level":"document_text",
                                                  "runtime_observed":False}}).to_dict())
                return {"sources":[source],"assets":[asset],"evidence":evidence,
                    "relationships":[],"matches":{},"table_chunks":{asset["id"]:chunks},
                    "warnings":[],"counts":{"code":0,"issues":0,"pull_requests":0,
                    "pr_files":0,"documents":1,"unsupported_documents":0}}
            from unittest import mock
            with mock.patch("radar.discover.discover_github", side_effect=fake_github):
                result = run_discovery("ws_auto_observations", requirements, pack, seeds,
                    tmp, github=True, business_model_path=str(business_model))
            self.assertIsNotNone(result["business_observations_path"])
            import json
            bundle = json.loads(Path(result["business_observations_path"]).read_text(encoding="utf-8"))
            self.assertEqual(bundle["summary"]["observations"], 1)
            self.assertEqual(bundle["observations"][0]["values"], {
                "accepted_qty":"8","rejected_qty":"2","received_qty":"10"})
            self.assertEqual(bundle["invariant_evaluations"]["evaluations"][0]["outcome"], "pass")
            self.assertEqual(bundle["summary"]["invariant_passes"], 1)
            store = JsonWorkspaceStore(tmp, "ws_auto_observations")
            self.assertEqual(len(store.list_records("evidence")), 3)

    def test_repeated_discover_is_idempotent_for_imported_assets(self):
        requirements, pack, seeds = self._paths()
        with tempfile.TemporaryDirectory() as tmp:
            first = run_discovery("ws_discover_repeat", requirements, pack, seeds, tmp)
            second = run_discovery("ws_discover_repeat", requirements, pack, seeds, tmp)
            store = JsonWorkspaceStore(tmp, "ws_discover_repeat")
            self.assertEqual(len(store.list_records("asset")), 35)
            self.assertEqual(len(store.list_records("source")), 7)
            self.assertEqual(len(store.list_pending_quotes()), 23)
            self.assertEqual(len(store.list_records("discovery_run")), 2)
            self.assertNotEqual(first["run_id"], second["run_id"])

    def test_github_candidates_and_evidence_join_the_workspace_run(self):
        requirements, pack, seeds = self._paths()
        with tempfile.TemporaryDirectory() as tmp:
            def fake_github(requirement_rows, pack_data, workspace_id, **kwargs):
                requirement_id = requirement_rows[0]["id"]
                source = new_record("source", provider="github",
                    uri="https://github.com", name="github.com",
                    access_status="public").to_dict()
                asset = new_record("asset", source_id=source["id"],
                    asset_type="file", uri="https://github.com/acme/app/blob/abc/app.py",
                    title="app.py", version_ref="abc", status="active").to_dict()
                evidence = new_record("evidence", workspace_id=workspace_id,
                    asset_id=asset["id"], evidence_kind="code",
                    statement="create_purchase_order()", locator={
                        "path": "app.py", "line_start": 12, "line_end": 12, "ref": "abc"},
                    captured_at="2026-11-22T00:00:00Z",
                    verification_status="source_confirmed").to_dict()
                return {
                    "sources": [source], "assets": [asset], "evidence": [evidence],
                    "relationships": [], "matches": {requirement_id: [asset["id"]]},
                    "warnings": [], "counts": {
                        "code": 1, "issues": 0, "pull_requests": 0, "pr_files": 0},
                }

            from unittest import mock
            with mock.patch("radar.discover.discover_github", side_effect=fake_github):
                result = run_discovery("ws_discover_github", requirements, pack, seeds,
                                       tmp, github=True)
            store = JsonWorkspaceStore(tmp, "ws_discover_github")
            self.assertEqual(len(store.list_records("source")), 8)
            self.assertEqual(len(store.list_records("asset")), 36)
            self.assertEqual(len(store.list_records("evidence")), 1)
            d01 = next(x for x in result["assessments"] if x["requirement_key"] == "D01")
            self.assertEqual(d01["status"], "not_assessed")
            self.assertEqual(d01["evidence"], 1)

    def test_unknown_pack_unit_is_rejected(self):
        requirements, pack, seeds = self._paths()
        with tempfile.TemporaryDirectory() as tmp:
            import json
            data = json.loads(Path(requirements).read_text(encoding="utf-8"))
            data["requirements"][0]["pack_unit_ids"] = ["M99"]
            bad = Path(tmp) / "bad-requirements.json"
            bad.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                run_discovery("ws_discover_bad", str(bad), pack, seeds, tmp)


if __name__ == "__main__":
    unittest.main()


class TestDiscoverCLI(unittest.TestCase):
    def test_discover_command_is_available(self):
        root = Path(__file__).resolve().parents[1]
        requirements, pack, seeds = TestDiscoverWorkflow()._paths()
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run([
                sys.executable, "-m", "radar", "discover",
                "--workspace", "ws_cli_test", "--workspace-root", tmp,
                "--requirements", requirements, "--pack", pack, "--seeds", seeds,
            ], cwd=str(root), capture_output=True, text=True, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn('"run_status": "partial"', proc.stdout)
