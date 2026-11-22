import unittest

from radar.ledger_control_pipeline import (
    LedgerControlPipelineError, run_ledger_control_pipeline,
)


class TestLedgerControlPipeline(unittest.TestCase):
    def _evidence(self, identifier, row):
        return {"id": identifier, "asset_id": "asset-1",
                "locator": {"path": "ledger.csv", "row": row, "column": 1}}

    def _row(self, identifier, evidence, row, kind, debit="0", credit="0",
             quantity="0", value="0", account="INV"):
        common = {
            "ledger_entry_id": identifier, "source_system": "erp",
            "ledger_kind": kind, "company_id": "CO-1",
            "voucher_type": "Journal Entry", "voucher_id": "JV-1",
            "voucher_item_id": identifier,
            "source_document_ref": {"voucher_type": "Journal Entry",
                                    "voucher_id": "JV-1", "voucher_item_id": identifier},
            "event_kind": "posting", "posting_status": "posted", "currency": "USD",
            "accounting_period": "FY2026-P03", "asset_id": "asset-1",
            "evidence_id": evidence,
            "locator": {"path": "ledger.csv", "row": row, "column": 1},
        }
        if kind == "stock":
            common.update({"item_id": "ITEM-1", "warehouse_id": "WH-1",
                           "quantity_uom": "EA", "quantity_delta": quantity,
                           "stock_value_delta": value})
        else:
            common.update({"account_id": account, "debit_amount": debit,
                           "credit_amount": credit})
        return common

    def _manifest(self, evidence):
        return {
            "id": "MAN-1", "source_system": "erp", "company_id": "CO-1",
            "currency": "USD", "voucher_type": "Journal Entry", "voucher_id": "JV-1",
            "accounting_period": "FY2026-P03",
            "expected_ledger_entry_ids": ["G1", "G2"],
            "evidence_id": evidence, "asset_id": "asset-1",
            "locator": {"path": "ledger.csv", "row": 5, "column": 1},
        }

    def _rules(self):
        return [
            {"id": "stock-value", "ledger_kind": "stock",
             "metric": "stock_value_delta", "output_field": "stock_value",
             "group_by": ["company_id", "currency", "accounting_period",
                          "item_id", "warehouse_id", "quantity_uom"]},
            {"id": "inventory-gl", "ledger_kind": "general_ledger",
             "metric": "signed_amount", "output_field": "net_amount",
             "group_by": ["company_id", "currency", "accounting_period", "account_id"],
             "account_mapping": {"INV": "inventory_asset"}},
        ]

    def test_runs_all_stages_and_returns_balanced_reconciliation(self):
        evidence = [self._evidence("ES", 2), self._evidence("EG1", 3),
                    self._evidence("EG2", 4), self._evidence("EM", 5)]
        rows = [
            self._row("S1", "ES", 2, "stock", quantity="2", value="100"),
            self._row("G1", "EG1", 3, "general_ledger", debit="100", account="INV"),
            self._row("G2", "EG2", 4, "general_ledger", credit="100", account="OFFSET"),
        ]
        result = run_ledger_control_pipeline(
            rows, evidence, [self._manifest("EM")], self._rules())
        self.assertEqual(result["summary"]["ledger_effects_accepted"], 3)
        self.assertEqual(result["summary"]["vouchers_balanced"], 1)
        self.assertEqual(result["summary"]["reconciliations_matched"], 1)
        self.assertEqual(result["reconciliation"]["results"][0]["status"], "matched")
        self.assertEqual(result["policy"]["computed_results_are_not_business_assessments"], True)

    def test_incomplete_voucher_does_not_block_other_pipeline_stages(self):
        evidence = [self._evidence("ES", 2), self._evidence("EG1", 3),
                    self._evidence("EM", 5)]
        rows = [
            self._row("S1", "ES", 2, "stock", quantity="2", value="100"),
            self._row("G1", "EG1", 3, "general_ledger", debit="100", account="INV"),
        ]
        result = run_ledger_control_pipeline(
            rows, evidence, [self._manifest("EM")], self._rules())
        self.assertEqual(result["summary"]["vouchers_unresolved"], 1)
        self.assertEqual(result["vouchers"]["unresolved"][0]["reason"],
                         "incomplete_voucher_extract")
        self.assertEqual(result["summary"]["reconciliations_unresolved"], 1)

    def test_invalid_evidence_stops_pipeline_before_computation(self):
        row = self._row("G1", "MISSING", 2, "general_ledger", debit="1")
        with self.assertRaises(LedgerControlPipelineError):
            run_ledger_control_pipeline([row], [], [], self._rules())

    def test_missing_manifest_is_reported_not_assumed_complete(self):
        evidence = [self._evidence("G1", 2)]
        row = self._row("G1", "G1", 2, "general_ledger", debit="1")
        result = run_ledger_control_pipeline([row], evidence, [], self._rules())
        self.assertEqual(result["vouchers"]["unresolved"][0]["reason"],
                         "missing_voucher_extraction_manifest")


if __name__ == "__main__":
    unittest.main()
