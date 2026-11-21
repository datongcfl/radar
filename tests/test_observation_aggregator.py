import unittest

from radar.observation_aggregator import (
    ObservationAggregationError, aggregate_observations,
)


RULE = {
    "id": "purchase_order_receipts_total",
    "source_invariant_id": "receipt_quantity_balance",
    "source_field": "received_qty",
    "group_by": ["purchase_order_id", "purchase_order_item_id"],
    "operation": "sum",
    "output_field": "cumulative_received_qty",
}


def row(identifier, po, line, qty, evidence=None, asset=None):
    evidence = evidence or "ev_" + identifier
    return {
        "id": identifier, "asset_id": asset or "asset_" + identifier,
        "invariant_id": "receipt_quantity_balance",
        "business_scope": {"purchase_order_id": po, "purchase_order_item_id": line},
        "values": {"received_qty": str(qty)},
        "field_provenance": {"received_qty": {
            "evidence_id": evidence,
            "locator": {"path": identifier + ".csv", "row": 2, "column": 3},
        }},
    }


class TestObservationAggregator(unittest.TestCase):
    def test_aggregates_receipts_across_assets_by_exact_order_line(self):
        result = aggregate_observations(RULE, [
            row("obs1", "PO-1", "LINE-1", 40),
            row("obs2", "PO-1", "LINE-1", 35),
            row("obs3", "PO-1", "LINE-1", 30),
            row("obs4", "PO-1", "LINE-2", 12),
        ])
        self.assertEqual(len(result["results"]), 2)
        first = next(item for item in result["results"]
                     if item["business_scope"]["purchase_order_item_id"] == "LINE-1")
        self.assertEqual(first["values"]["cumulative_received_qty"], "105")
        self.assertEqual(first["contribution_count"], 3)
        self.assertEqual(len(first["evidence_ids"]), 3)
        self.assertEqual(len({item["asset_id"] for item in first["contributions"]}), 3)

    def test_duplicate_evidence_is_counted_once_and_reported(self):
        result = aggregate_observations(RULE, [
            row("obs1", "PO-1", "LINE-1", 40, evidence="ev_shared"),
            row("obs2", "PO-1", "LINE-1", 40, evidence="ev_shared"),
        ])
        self.assertEqual(result["results"][0]["values"]["cumulative_received_qty"], "40")
        self.assertEqual(result["summary"]["duplicate_evidence"], 1)

    def test_missing_scope_is_reported_not_silently_grouped(self):
        item = row("obs1", "PO-1", "LINE-1", 40)
        item["business_scope"].pop("purchase_order_item_id")
        result = aggregate_observations(RULE, [item])
        self.assertEqual(result["results"], [])
        self.assertEqual(result["skipped"][0]["reason"], "missing_group_key")

    def test_other_invariants_are_ignored(self):
        item = row("obs1", "PO-1", "LINE-1", 40)
        item["invariant_id"] = "unrelated"
        self.assertEqual(aggregate_observations(RULE, [item])["results"], [])

    def test_duplicate_observation_ids_and_unsupported_operations_rejected(self):
        item = row("obs1", "PO-1", "LINE-1", 40)
        with self.assertRaises(ObservationAggregationError):
            aggregate_observations(RULE, [item, item])
        invalid = dict(RULE, operation="average")
        with self.assertRaises(ObservationAggregationError):
            aggregate_observations(invalid, [item])

    def test_non_finite_values_rejected(self):
        item = row("obs1", "PO-1", "LINE-1", "NaN")
        with self.assertRaises(ObservationAggregationError):
            aggregate_observations(RULE, [item])


if __name__ == "__main__":
    unittest.main()
