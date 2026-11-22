import unittest

from radar.ledger_vouchers import LedgerVoucherError, validate_gl_vouchers


class TestLedgerVouchers(unittest.TestCase):
    def _evidence(self):
        return {"id": "EV-MANIFEST", "asset_id": "asset-manifest",
                "locator": {"path": "extract-manifest.json", "line": 4}}

    def _row(self, identifier, debit, credit, **updates):
        row = {
            "ledger_kind": "general_ledger", "ledger_entry_id": identifier,
            "source_system": "erp-a", "company_id": "CO-1", "currency": "USD",
            "voucher_type": "Journal Entry", "voucher_id": "JV-1",
            "accounting_period": "FY2026-P03",
            "debit_amount": debit, "credit_amount": credit,
            "evidence_id": "EV-" + identifier,
        }
        row.update(updates)
        return row

    def _manifest(self, expected, **updates):
        manifest = {
            "id": "MAN-1", "source_system": "erp-a", "company_id": "CO-1",
            "currency": "USD", "voucher_type": "Journal Entry", "voucher_id": "JV-1",
            "accounting_period": "FY2026-P03",
            "expected_ledger_entry_ids": expected,
            "evidence_id": "EV-MANIFEST", "asset_id": "asset-manifest",
            "locator": {"path": "extract-manifest.json", "line": 4},
        }
        manifest.update(updates)
        return manifest

    def test_complete_balanced_voucher(self):
        result = validate_gl_vouchers(
            [self._row("L1", "100", "0"), self._row("L2", "0", "100")],
            [self._manifest(["L1", "L2"])], [self._evidence()])
        self.assertEqual(result["summary"]["balanced"], 1)
        self.assertEqual(result["results"][0]["status"], "balanced")

    def test_complete_unbalanced_voucher(self):
        result = validate_gl_vouchers(
            [self._row("L1", "100", "0"), self._row("L2", "0", "90")],
            [self._manifest(["L1", "L2"])], [self._evidence()])
        self.assertEqual(result["summary"]["unbalanced"], 1)
        self.assertEqual(result["results"][0]["difference"], "10")

    def test_missing_line_is_incomplete_not_unbalanced(self):
        result = validate_gl_vouchers(
            [self._row("L1", "100", "0")],
            [self._manifest(["L1", "L2"])], [self._evidence()])
        self.assertEqual(result["results"], [])
        self.assertEqual(result["unresolved"][0]["reason"], "incomplete_voucher_extract")
        self.assertEqual(result["summary"]["unbalanced"], 0)

    def test_unexpected_line_is_incomplete(self):
        result = validate_gl_vouchers(
            [self._row("L1", "100", "0"), self._row("L3", "0", "100")],
            [self._manifest(["L1", "L2"])], [self._evidence()])
        self.assertEqual(result["unresolved"][0]["unexpected_ledger_entry_ids"], ["L3"])

    def test_missing_manifest_is_unresolved(self):
        result = validate_gl_vouchers(
            [self._row("L1", "100", "100")], [], [self._evidence()])
        self.assertEqual(result["unresolved"][0]["reason"],
                         "missing_voucher_extraction_manifest")

    def test_missing_accounting_period_is_unresolved(self):
        row = self._row("L1", "100", "0")
        row.pop("accounting_period")
        result = validate_gl_vouchers([row], [self._manifest(["L1"])], [self._evidence()])
        self.assertEqual(result["unresolved"][0]["reason"], "missing_accounting_period")

    def test_conflicting_manifests_are_unresolved(self):
        result = validate_gl_vouchers(
            [self._row("L1", "100", "0")],
            [self._manifest(["L1"]), self._manifest(["L1"], id="MAN-2")],
            [self._evidence()])
        self.assertEqual(result["unresolved"][0]["reason"],
                         "conflicting_voucher_extraction_manifests")

    def test_manifest_requires_matching_evidence_and_locator(self):
        manifest = self._manifest(["L1"], locator={"path": "wrong.csv", "line": 2})
        with self.assertRaises(LedgerVoucherError):
            validate_gl_vouchers([self._row("L1", "100", "0")],
                                 [manifest], [self._evidence()])

    def test_explicit_tolerance(self):
        result = validate_gl_vouchers(
            [self._row("L1", "100", "0"), self._row("L2", "0", "100.01")],
            [self._manifest(["L1", "L2"])], [self._evidence()], tolerance="0.01")
        self.assertEqual(result["results"][0]["status"], "balanced")

    def test_negative_tolerance_is_rejected(self):
        with self.assertRaises(LedgerVoucherError):
            validate_gl_vouchers([], [], [], tolerance="-0.01")


if __name__ == "__main__":
    unittest.main()
