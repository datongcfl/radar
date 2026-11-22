import unittest

from radar.ledger_effects import LedgerEffectError, validate_ledger_effects


class TestLedgerEffects(unittest.TestCase):
    def _evidence(self, identifier, asset="asset-1"):
        return {"id": identifier, "asset_id": asset,
                "locator": {"path": "ledger.csv", "row": 2, "column": 1}}

    def _stock(self, identifier="SLE-1", evidence="EV-1", **updates):
        row = {
            "ledger_entry_id": identifier, "source_system": "erp-a",
            "ledger_kind": "stock", "company_id": "CO-1",
            "voucher_type": "Purchase Receipt", "voucher_id": "PR-1",
            "voucher_item_id": "PR-ROW-1",
            "source_document_ref": {"voucher_type": "Purchase Receipt",
                                    "voucher_id": "PR-1",
                                    "voucher_item_id": "PR-ROW-1"},
            "event_kind": "receipt", "posting_status": "posted",
            "currency": "USD", "asset_id": "asset-1",
            "item_id": "ITEM-1", "warehouse_id": "WH-1",
            "quantity_delta": "10", "quantity_uom": "EA",
            "stock_value_delta": "99.64", "evidence_id": evidence,
            "locator": {"path": "ledger.csv", "row": 2, "column": 1},
        }
        row.update(updates)
        return row

    def _gl(self, identifier="GL-1", evidence="EV-1", **updates):
        row = {
            "ledger_entry_id": identifier, "source_system": "erp-a",
            "ledger_kind": "general_ledger", "company_id": "CO-1",
            "voucher_type": "Purchase Receipt", "voucher_id": "PR-1",
            "voucher_item_id": "PR-ROW-1",
            "source_document_ref": {"voucher_type": "Purchase Receipt",
                                    "voucher_id": "PR-1",
                                    "voucher_item_id": "PR-ROW-1"},
            "event_kind": "receipt_accrual", "posting_status": "posted",
            "currency": "USD", "asset_id": "asset-1",
            "account_id": "STOCK-IN-TRANSIT",
            "debit_amount": "99.64", "credit_amount": "0",
            "evidence_id": evidence,
            "locator": {"path": "ledger.csv", "row": 2, "column": 1},
        }
        row.update(updates)
        return row

    def test_stock_and_gl_are_validated_as_distinct_streams(self):
        rows = [self._stock(), self._gl()]
        result = validate_ledger_effects(rows, [self._evidence("EV-1")])
        self.assertEqual(result["summary"]["accepted"], 2)
        self.assertEqual(result["summary"]["stock_entries"], 1)
        self.assertEqual(result["summary"]["general_ledger_entries"], 1)
        self.assertEqual(result["ledger_effects"][0]["stock_value_delta"], "99.64")

    def test_reversal_requires_exact_original_ledger_entry(self):
        original = self._stock()
        reversal = self._stock("SLE-2", "EV-2", posting_status="reversal",
                               reversal_of="SLE-1", quantity_delta="-10",
                               stock_value_delta="-99.64")
        result = validate_ledger_effects(
            [original, reversal],
            [self._evidence("EV-1"), self._evidence("EV-2")])
        self.assertEqual(result["summary"]["reversal_entries"], 1)
        self.assertEqual(result["summary"]["accepted"], 2)

    def test_missing_reversal_target_is_unresolved(self):
        reversal = self._stock("SLE-2", "EV-2", posting_status="reversal",
                               reversal_of="SLE-MISSING")
        result = validate_ledger_effects(
            [reversal], [self._evidence("EV-2")])
        self.assertEqual(result["ledger_effects"], [])
        self.assertEqual(result["skipped"][0]["reason"], "unresolved_reversal_target")

    def test_conflicting_duplicate_identity_excludes_both_rows(self):
        first = self._stock()
        second = self._stock(stock_value_delta="100")
        result = validate_ledger_effects(
            [first, second], [self._evidence("EV-1")])
        self.assertEqual(result["ledger_effects"], [])
        self.assertEqual(result["skipped"][0]["reason"],
                         "conflicting_ledger_entry_identity")

    def test_identical_duplicate_identity_is_counted_once(self):
        row = self._stock()
        result = validate_ledger_effects(
            [row, dict(row)], [self._evidence("EV-1")])
        self.assertEqual(result["summary"]["accepted"], 1)
        self.assertEqual(result["skipped"][0]["reason"], "duplicate_ledger_entry")

    def test_debit_note_is_not_automatically_a_stock_effect(self):
        debit_note = self._gl(voucher_type="Debit Note", voucher_id="DN-1",
                              source_document_ref={"voucher_type": "Debit Note",
                                                   "voucher_id": "DN-1",
                                                   "voucher_item_id": "DN-ROW-1"})
        result = validate_ledger_effects(
            [debit_note], [self._evidence("EV-1")])
        self.assertEqual(result["summary"]["general_ledger_entries"], 1)
        self.assertEqual(result["summary"]["stock_entries"], 0)

    def test_missing_source_evidence_is_rejected(self):
        with self.assertRaises(LedgerEffectError):
            validate_ledger_effects([self._stock()], [])

    def test_general_ledger_line_cannot_have_both_debit_and_credit(self):
        row = self._gl(debit_amount="10", credit_amount="10")
        with self.assertRaises(LedgerEffectError):
            validate_ledger_effects([row], [self._evidence("EV-1")])


if __name__ == "__main__":
    unittest.main()
