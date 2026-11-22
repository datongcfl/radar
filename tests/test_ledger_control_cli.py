import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from radar.cli import main
from radar.discovery import new_record
from radar.discovery_store import JsonWorkspaceStore


class TestLedgerControlCLI(unittest.TestCase):
    def test_ledger_control_command_writes_pipeline_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.json"
            output = root / "result.json"
            source.write_text(json.dumps({
                "ledger_effects": [],
                "evidence_records": [],
                "extraction_manifests": [],
                "aggregation_rules": [],
            }), encoding="utf-8")
            with redirect_stdout(StringIO()):
                code = main(["ledger-control", "--input", str(source),
                             "--out", str(output)])
            self.assertEqual(code, 0)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["schema_version"], 1)
            self.assertEqual(result["summary"]["ledger_effects_accepted"], 0)
            self.assertEqual(result["summary"]["vouchers_unresolved"], 0)

    def test_workspace_import_and_control_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = new_record("workspace", name="cli-ledger",
                                   status="active", pack_refs=[]).to_dict()
            store = JsonWorkspaceStore(root, workspace["id"])
            store.initialize(workspace)
            source = root / "bundle.json"
            output = root / "result.json"
            source.write_text(json.dumps({
                "ledger_effects": [], "evidence_records": [],
                "extraction_manifests": [], "aggregation_rules": [],
            }), encoding="utf-8")
            with redirect_stdout(StringIO()):
                imported = main(["ledger-import", "--workspace", workspace["id"],
                                 "--workspace-root", str(root), "--input", str(source)])
            self.assertEqual(imported, 0)
            with redirect_stdout(StringIO()):
                controlled = main(["ledger-control", "--workspace", workspace["id"],
                                   "--workspace-root", str(root), "--out", str(output)])
            self.assertEqual(controlled, 0)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["summary"]["ledger_effects_accepted"], 0)

    def test_ledger_control_rejects_missing_bundle_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.json"
            output = root / "result.json"
            source.write_text(json.dumps({"ledger_effects": []}), encoding="utf-8")
            with redirect_stdout(StringIO()):
                code = main(["ledger-control", "--input", str(source),
                             "--out", str(output)])
            self.assertEqual(code, 1)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
