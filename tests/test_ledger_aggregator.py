import unittest

from radar.ledger_aggregator import aggregate_ledger_effects


class TestLedgerAggregator(unittest.TestCase):
    def _evidence(self, identifier, row):
        return {"id": identifier, "asset_id": "asset-1",
                "locator": {"path": "ledger.csv", "row": row, "column": 1}}

    def _stock(self, identifier, evidence, row, **updates):
        item = {
            "ledger_entry_id": identifier, "source_system": "erp",
            "ledger_kind": "stock", "company_id": "CO", "voucher_type": "Purchase Receipt",
            "voucher_id": "PR-1", "voucher_item_id": "ROW-1",
            "source_document_ref": {"voucher_type": "Purchase Receipt", "voucher_id": "PR-1",
                                    "voucher_item_id": "ROW-1"},
            "event_kind": "receipt", "posting_status": "posted", "currency": "USD",
            "asset_id": "asset-1", "item_id": "ITEM", "warehouse_id": "WH",
            "quantity_delta": "2", "quantity_uom": "EA", "stock_value_delta": "19.50",
            "evidence_id": evidence,
            "locator": {"path": "ledger.csv", "row": row, "column": 1},
        }
        item.update(updates)
        return item

    def _gl(self, identifier, evidence, row, **updates):
        item = self._stock(identifier, evidence, row, ledger_kind="general_ledger",
                           account_id="STOCK", debit_amount="19.50", credit_amount="0")
        item.pop("item_id")
        item.pop("warehouse_id")
        item.pop("quantity_delta")
        item.pop("quantity_uom")
        item.pop("stock_value_delta")
        item.update(updates)
        return item

    def test_stock_value_uses_ledger_value_not_purchase_rate(self):
        rows = [self._stock("S1", "E1", 2), self._stock("S2", "E2", 3,
                stock_value_delta="20.14")]
        evidence = [self._evidence("E1", 2), self._evidence("E2", 3)]
        result = aggregate_ledger_effects(rows, evidence, [{
            "id": "stock_value", "ledger_kind": "stock", "metric": "stock_value_delta",
            "output_field": "stock_value", "group_by": [
                "company_id", "currency", "item_id", "warehouse_id", "quantity_uom"]}])[0]
        self.assertEqual(result["results"][0]["values"]["stock_value"], "39.64")
        self.assertEqual(result["summary"]["contributions"], 2)

    def test_gl_is_signed_and_unmapped_account_remains_unassessed(self):
        row = self._gl("G1", "E1", 2, debit_amount="0", credit_amount="19.50")
        result = aggregate_ledger_effects([row], [self._evidence("E1", 2)], [{
            "id": "gl_account", "ledger_kind": "general_ledger", "metric": "signed_amount",
            "output_field": "net_amount", "group_by": ["company_id", "currency", "account_id"]}])[0]
        self.assertEqual(result["results"][0]["values"]["net_amount"], "-19.50")
        self.assertEqual(result["results"][0]["account_mapping_status"], "unmapped")
        self.assertEqual(result["results"][0]["verification_status"], "computed_not_assessed")

    def test_explicit_account_mapping_is_retained(self):
        row = self._gl("G1", "E1", 2)
        result = aggregate_ledger_effects([row], [self._evidence("E1", 2)], [{
            "id": "gl_account", "ledger_kind": "general_ledger", "metric": "signed_amount",
            "output_field": "net_amount", "group_by": ["company_id", "currency", "account_id"],
            "account_mapping": {"STOCK": "inventory_control"} }])[0]
        self.assertEqual(result["results"][0]["account_role"], "inventory_control")
        self.assertEqual(result["results"][0]["account_mapping_status"], "mapped")

    def test_stock_and_gl_cannot_share_an_aggregation(self):
        with self.assertRaises(ValueError):
            aggregate_ledger_effects([], [], [{
                "id": "bad", "ledger_kind": "stock", "metric": "signed_amount",
                "output_field": "x", "group_by": ["company_id", "currency", "item_id",
                "warehouse_id", "quantity_uom"]}])

    def test_missing_dimensions_are_skipped_not_guessed(self):
        row = self._stock("S1", "E1", 2)
        result = aggregate_ledger_effects([row], [self._evidence("E1", 2)], [{
            "id": "stock_qty", "ledger_kind": "stock", "metric": "quantity_delta",
            "output_field": "qty", "group_by": [
                "company_id", "currency", "item_id", "warehouse_id",
                "quantity_uom", "posting_period"]}])[0]
        self.assertEqual(result["results"], [])
        self.assertEqual(result["skipped"][-1]["reason"], "missing_ledger_group_dimension")


if __name__ == "__main__":
    unittest.main()
