import tempfile
import unittest

from radar.discovery import new_record
from radar.discovery_store import JsonWorkspaceStore, StorageError
from radar.ledger_workspace import import_ledger_bundle, load_ledger_bundle


class TestLedgerWorkspace(unittest.TestCase):
    def _store(self, root):
        workspace = new_record("workspace", name="ledger-test",
                               status="active", pack_refs=[]).to_dict()
        store = JsonWorkspaceStore(root, workspace["id"])
        store.initialize(workspace)
        source = new_record("source", provider="enterprise",
            uri="file:///erp/export", name="ERP export",
            access_status="proprietary").to_dict()
        asset = new_record("asset", source_id=source["id"],
            asset_type="dataset", uri="file:///erp/export/stock.csv",
            title="Stock ledger export", status="active").to_dict()
        evidence = new_record("evidence", workspace_id=workspace["id"],
            asset_id=asset["id"], evidence_kind="data",
            statement="ERP stock ledger row", locator={
                "path":"stock.csv", "row":2, "column":1},
            captured_at="2026-11-22T00:00:00Z",
            verification_status="source_confirmed").to_dict()
        store.append(source); store.append(asset); store.append(evidence)
        return store, evidence

    def _bundle(self, evidence):
        locator = evidence["locator"]
        effect = {
            "ledger_entry_id":"STK-1", "source_system":"ERP-A",
            "ledger_kind":"stock", "company_id":"C1", "voucher_type":"Receipt",
            "voucher_id":"PR-1", "voucher_item_id":"1", "event_kind":"receipt",
            "posting_status":"posted", "currency":"USD", "evidence_id":evidence["id"],
            "asset_id":evidence["asset_id"], "locator":locator,
            "source_document_ref":{"voucher_type":"Receipt","voucher_id":"PR-1",
                                   "voucher_item_id":"1"},
            "item_id":"ITEM-1", "warehouse_id":"WH-1", "quantity_uom":"EA",
            "quantity_delta":"2", "stock_value_delta":"20"
        }
        rule = {"rule_id":"stock-by-period", "ledger_kind":"stock",
                "dimensions":["company_id","currency","accounting_period"]}
        return {"ledger_effects":[effect], "evidence_records":[evidence],
                "extraction_manifests":[], "aggregation_rules":[rule]}

    def test_import_and_rehydrate_workspace_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, evidence = self._store(tmp)
            bundle = self._bundle(evidence)
            counts = import_ledger_bundle(store, bundle)
            self.assertEqual(counts, {"ledger_effects":1,
                "extraction_manifests":0, "aggregation_rules":1})
            loaded = load_ledger_bundle(store)
            self.assertEqual(loaded["ledger_effects"], bundle["ledger_effects"])
            self.assertEqual(loaded["evidence_records"], [evidence])
            self.assertEqual(loaded["aggregation_rules"], bundle["aggregation_rules"])

    def test_import_rejects_evidence_not_identical_to_workspace_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, evidence = self._store(tmp)
            altered = dict(evidence)
            altered["statement"] = "fabricated statement"
            bundle = self._bundle(altered)
            with self.assertRaises(StorageError):
                import_ledger_bundle(store, bundle)
            self.assertEqual(store.list_records("ledger_effect"), [])

    def test_store_rejects_ledger_effect_with_mismatched_locator(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, evidence = self._store(tmp)
            effect = self._bundle(evidence)["ledger_effects"][0]
            effect["locator"] = {"path":"other.csv","row":99,"column":1}
            bundle = self._bundle(evidence)
            bundle["ledger_effects"] = [effect]
            with self.assertRaises(StorageError):
                import_ledger_bundle(store, bundle)
            self.assertEqual(store.list_records("ledger_effect"), [])


if __name__ == "__main__":
    unittest.main()
