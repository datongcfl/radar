import unittest

from radar.observation_aggregator import ObservationAggregationError, aggregate_observations

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
    asset = asset or "asset_" + identifier
    value_locator = {"path": identifier + ".csv", "row": 2, "column": 3}
    scope = {"purchase_order_id": po, "purchase_order_item_id": line}
    scope_provenance, records = {}, [
        {"id": evidence, "asset_id": asset, "locator": value_locator}
    ]
    for index, field in enumerate(("purchase_order_id", "purchase_order_item_id"), 1):
        scope_id = evidence + "_scope_" + str(index)
        locator = {"path": identifier + ".csv", "row": 2, "column": index}
        scope_provenance[field] = {"evidence_id": scope_id, "locator": locator}
        records.append({"id": scope_id, "asset_id": asset, "locator": locator})
    observation = {
        "id": identifier, "asset_id": asset,
        "invariant_id": "receipt_quantity_balance",
        "business_scope": scope, "scope_provenance": scope_provenance,
        "values": {"received_qty": str(qty)},
        "field_provenance": {"received_qty": {
            "evidence_id": evidence, "locator": value_locator}},
    }
    return observation, records


class TestObservationAggregator(unittest.TestCase):
    def _aggregate(self, rows):
        observations = [item[0] for item in rows]
        evidence = [record for item in rows for record in item[1]]
        return aggregate_observations(RULE, observations, evidence_records=evidence)

    def test_aggregates_receipts_across_assets_by_exact_order_line(self):
        result = self._aggregate([
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
        self.assertTrue(all(len(item["scope_provenance"]) == 2 for item in first["contributions"]))

    def test_duplicate_evidence_is_counted_once_and_reported(self):
        result = self._aggregate([
            row("obs1", "PO-1", "LINE-1", 40, evidence="ev_shared"),
            row("obs2", "PO-1", "LINE-1", 40, evidence="ev_shared"),
        ])
        self.assertEqual(result["results"][0]["values"]["cumulative_received_qty"], "40")
        self.assertEqual(result["summary"]["duplicate_evidence"], 1)

    def test_missing_scope_is_reported_not_silently_grouped(self):
        item, evidence = row("obs1", "PO-1", "LINE-1", 40)
        item["business_scope"].pop("purchase_order_item_id")
        result = aggregate_observations(RULE, [item], evidence_records=evidence)
        self.assertEqual(result["results"], [])
        self.assertEqual(result["skipped"][0]["reason"], "missing_group_key")

    def test_unverified_scope_provenance_is_not_aggregated(self):
        item, evidence = row("obs1", "PO-1", "LINE-1", 40)
        item["scope_provenance"].pop("purchase_order_item_id")
        result = aggregate_observations(RULE, [item], evidence_records=evidence)
        self.assertEqual(result["results"], [])
        self.assertEqual(result["skipped"][0]["reason"], "unverified_group_key_provenance")

    def test_scope_evidence_from_another_asset_is_rejected(self):
        item, evidence = row("obs1", "PO-1", "LINE-1", 40)
        evidence[-1]["asset_id"] = "another_asset"
        result = aggregate_observations(RULE, [item], evidence_records=evidence)
        self.assertEqual(result["results"], [])
        self.assertEqual(result["skipped"][0]["reason"], "unverified_group_key_provenance")

    def test_unverified_value_evidence_is_not_aggregated(self):
        item, evidence = row("obs1", "PO-1", "LINE-1", 40)
        evidence[0]["locator"]["column"] = 99
        result = aggregate_observations(RULE, [item], evidence_records=evidence)
        self.assertEqual(result["results"], [])
        self.assertEqual(result["skipped"][0]["reason"], "unverified_source_field_provenance")

    def test_other_invariants_are_ignored(self):
        item, evidence = row("obs1", "PO-1", "LINE-1", 40)
        item["invariant_id"] = "unrelated"
        self.assertEqual(aggregate_observations(
            RULE, [item], evidence_records=evidence)["results"], [])

    def test_duplicate_observation_ids_and_unsupported_operations_rejected(self):
        item, evidence = row("obs1", "PO-1", "LINE-1", 40)
        with self.assertRaises(ObservationAggregationError):
            aggregate_observations(RULE, [item, item], evidence_records=evidence)
        with self.assertRaises(ObservationAggregationError):
            aggregate_observations(dict(RULE, operation="average"),
                                   [item], evidence_records=evidence)

    def test_non_finite_values_rejected(self):
        item, evidence = row("obs1", "PO-1", "LINE-1", "NaN")
        with self.assertRaises(ObservationAggregationError):
            aggregate_observations(RULE, [item], evidence_records=evidence)


if __name__ == "__main__":
    unittest.main()
