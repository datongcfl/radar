import tempfile
import unittest
import subprocess
import sys
from pathlib import Path

from radar.discover import run_discovery
from radar.discovery_store import JsonWorkspaceStore


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
