import unittest

from radar.ledger_reconciliation import (
    LedgerReconciliationError, reconcile_inventory_gl,
)


def stock(scope=None, value="100", identifier="S-1"):
    return {"id": identifier, "business_scope": scope or {
        "company_id": "CO-1", "currency": "USD", "accounting_period": "2026-11"},
        "values": {"net_stock_value_delta": value}, "evidence_ids": ["EV-S"]}


def gl(scope=None, value="100", role="inventory_asset", mapped=True, identifier="G-1"):
    return {"id": identifier, "business_scope": scope or {
        "company_id": "CO-1", "currency": "USD", "accounting_period": "2026-11"},
        "values": {"net_signed_amount": value}, "evidence_ids": ["EV-G"],
        "account_role": role, "account_mapping_status": "mapped" if mapped else "unmapped"}


class TestLedgerReconciliation(unittest.TestCase):
    def test_matches_within_explicit_tolerance(self):
        result = reconcile_inventory_gl([stock()], [gl(value="100.01")], "0.01")
        self.assertEqual(result["results"][0]["status"], "matched")

    def test_reports_value_mismatch(self):
        result = reconcile_inventory_gl([stock()], [gl(value="99")])
        self.assertEqual(result["results"][0]["status"], "mismatch")
        self.assertEqual(result["results"][0]["difference"], "1")

    def test_rolls_up_multiple_stock_and_inventory_accounts(self):
        result = reconcile_inventory_gl(
            [stock(value="40"), stock(value="60", identifier="S-2")],
            [gl(value="70"), gl(value="30", identifier="G-2")])
        self.assertEqual(result["results"][0]["status"], "matched")
        self.assertEqual(result["results"][0]["stock_value"], "100")
        self.assertEqual(result["results"][0]["general_ledger_value"], "100")

    def test_unmapped_account_is_not_compared(self):
        result = reconcile_inventory_gl([stock()], [gl(mapped=False)])
        self.assertEqual(result["results"], [])
        self.assertEqual(result["summary"]["unresolved"], 1)

    def test_non_inventory_account_role_is_not_compared(self):
        result = reconcile_inventory_gl([stock()], [gl(role="expense")])
        self.assertEqual(result["results"], [])
        self.assertEqual(result["summary"]["unresolved"], 1)

    def test_missing_period_is_unresolved(self):
        result = reconcile_inventory_gl(
            [stock({"company_id": "CO-1", "currency": "USD"})], [gl()])
        self.assertEqual(result["results"], [])
        self.assertEqual(result["summary"]["unresolved"], 1)

    def test_missing_counterpart_is_not_zero(self):
        result = reconcile_inventory_gl([stock()], [])
        self.assertEqual(result["results"][0]["status"], "unresolved")

    def test_negative_tolerance_is_rejected(self):
        with self.assertRaises(LedgerReconciliationError):
            reconcile_inventory_gl([], [], "-0.01")


if __name__ == "__main__":
    unittest.main()
