import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from radar.cli import main
from radar.discovery import new_record
from radar.discovery_store import JsonWorkspaceStore
from radar.model import load_pack, sha256_file


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
            self.assertEqual(code, 0, captured.getvalue())
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

    def test_ledger_adapt_command_uses_pack_mapping_and_workspace_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = Path(__file__).resolve().parents[1]
            pack_path = repo / "packs/weak-current/pack.json"
            business_model = json.loads(
                (repo / "packs/weak-current/business-model.json").read_text(encoding="utf-8")
            )
            pack = load_pack(pack_path)
            adapter = {
                "id": "erp-stock-csv-v1", "source_system": "erp-a",
                "format": "csv", "ledger_kind": "stock", "header_row": 1,
                "delimiter": ",",
                "field_map": {
                    "ledger_entry_id": "Ledger Entry ID",
                    "company_id": "Company ID",
                    "voucher_type": "Voucher Type",
                    "voucher_id": "Voucher ID",
                    "voucher_item_id": "Voucher Item ID",
                    "event_kind": "Event Kind",
                    "posting_status": "Posting Status",
                    "currency": "Currency",
                    "accounting_period": "Accounting Period",
                    "item_id": "Item ID", "warehouse_id": "Warehouse ID",
                    "quantity_delta": "Quantity Delta", "quantity_uom": "Quantity UOM",
                    "stock_value_delta": "Stock Value Delta",
                },
                "number_format": {"decimal_separator": ".", "thousands_separator": ","},
                "value_maps": {"posting_status": {"Posted": "posted"}},
            }
            business_model["ledger_source_adapters"] = [adapter]
            model_path = root / "business-model.json"
            model_path.write_text(json.dumps(business_model), encoding="utf-8")

            pack_refs = [{"pack": pack["pack"], "version": str(pack.get("version", "unknown")),
                          "digest": sha256_file(pack_path)}]
            workspace = new_record("workspace", name="ledger-adapt-cli",
                                   status="active", pack_refs=pack_refs).to_dict()
            store = JsonWorkspaceStore(root, workspace["id"])
            store.initialize(workspace)

            source = root / "stock.csv"
            source.write_text(
                "Ledger Entry ID,Company ID,Voucher Type,Voucher ID,Voucher Item ID,Event Kind,Posting Status,Currency,Accounting Period,Item ID,Warehouse ID,Quantity Delta,Quantity UOM,Stock Value Delta\\n"
                "SLE-CLI-1,C1,Receipt,GR-CLI-1,ROW-1,receipt,Posted,USD,2026-11,CABLE-1,WH-1,5,EA,50\\n",
                encoding="utf-8",
            )
            output = root / "adapt-result.json"
            captured = StringIO()
            with redirect_stdout(captured):
                code = main([
                    "ledger-adapt", "--workspace", workspace["id"],
                    "--workspace-root", str(root), "--pack", str(pack_path),
                    "--business-model", str(model_path), "--adapter-id", "erp-stock-csv-v1",
                    "--input", str(source), "--out", str(output),
                ])
            self.assertEqual(code, 0)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["ledger_effects_imported"], 1)
            self.assertEqual(result["pack"], "weak-current")
            self.assertEqual(len(store.list_records("ledger_effect")), 1)

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
