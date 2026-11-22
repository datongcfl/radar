import unittest

from radar.observation_aggregator import aggregate_observations


RULE = {
    "id": "receipt_total",
    "source_invariant_id": "receipt_quantity_balance",
    "source_field": "received_qty",
    "group_by": ["purchase_order_id", "purchase_order_item_id"],
    "operation": "sum",
    "transaction_semantics": {
        "status_field": "document_status",
        "posted_values": ["1"],
        "non_posted_values": ["0", "2"],
        "return_flag_field": "is_return",
        "return_values": ["1"],
        "normal_values": ["0"],
        "return_reference_field": "return_against",
        "return_reference_item_field": "return_against_item_id",
        "return_reference_target_field": "receipt_id",
        "return_reference_item_target_field": "receipt_item_id",
        "deduplicate_by": ["receipt_id", "receipt_item_id", "purchase_order_item_id"],
        "document_type_field": "document_type",
        "allowed_document_types": ["Purchase Receipt"],
        "return_reference_match_fields": ["purchase_order_item_id"],
    },
}


def transaction_row(identifier, qty, receipt, receipt_item, is_return="0",
                    return_against="", return_against_item_id=""):
    asset = "asset_" + identifier
    observation = {
        "id": identifier, "asset_id": asset,
        "invariant_id": "receipt_quantity_balance",
        "business_scope": {
            "purchase_order_id": "PO-1",
            "purchase_order_item_id": "PO-ITEM-1",
            "receipt_id": receipt,
            "receipt_item_id": receipt_item,
        },
        "scope_provenance": {},
        "values": {"received_qty": str(qty)},
        "field_provenance": {},
        "transaction": {
            "document_status": "1", "is_return": is_return,
            "document_type": "Purchase Receipt",
            "return_against": return_against,
            "return_against_item_id": return_against_item_id,
        },
        "transaction_provenance": {},
    }
    evidence = []
    for index, field in enumerate(
            ("received_qty", "purchase_order_id", "purchase_order_item_id",
             "receipt_id", "receipt_item_id", "document_status", "is_return",
             "document_type", "return_against", "return_against_item_id"), 1):
        locator = {"path": identifier + ".csv", "row": 2, "column": index}
        evidence_id = "ev_" + identifier + "_" + field
        evidence.append({"id": evidence_id, "asset_id": asset, "locator": locator})
        provenance = {"evidence_id": evidence_id, "locator": locator}
        if field == "received_qty":
            observation["field_provenance"][field] = provenance
        elif field in ("purchase_order_id", "purchase_order_item_id",
                       "receipt_id", "receipt_item_id"):
            observation["scope_provenance"][field] = provenance
        else:
            observation["transaction_provenance"][field] = provenance
    return observation, evidence


def aggregate(rows):
    observations = [item[0] for item in rows]
    evidence = [record for item in rows for record in item[1]]
    return aggregate_observations(RULE, observations, evidence_records=evidence)


class TestReturnQuantityCap(unittest.TestCase):
    def test_all_returns_are_unresolved_when_cumulative_return_exceeds_original_line(self):
        result = aggregate([
            transaction_row("original", 10, "PR-1", "PR-1-ROW-1"),
            transaction_row("return-a", 6, "RET-1", "RET-1-ROW-1", "1",
                            "PR-1", "PR-1-ROW-1"),
            transaction_row("return-b", 5, "RET-2", "RET-2-ROW-1", "1",
                            "PR-1", "PR-1-ROW-1"),
        ])
        self.assertEqual(result["results"][0]["values"]["aggregated_value"], "10")
        exceeded = [item for item in result["skipped"]
                    if item["reason"] == "return_quantity_exceeds_original_receipt"]
        self.assertEqual({item["observation_id"] for item in exceeded},
                         {"return-a", "return-b"})
        self.assertTrue(all(item["original_received_qty"] == "10"
                            and item["cumulative_return_qty"] == "11"
                            for item in exceeded))

    def test_cumulative_return_equal_to_original_quantity_is_allowed(self):
        result = aggregate([
            transaction_row("original", 10, "PR-1", "PR-1-ROW-1"),
            transaction_row("return-a", 6, "RET-1", "RET-1-ROW-1", "1",
                            "PR-1", "PR-1-ROW-1"),
            transaction_row("return-b", 4, "RET-2", "RET-2-ROW-1", "1",
                            "PR-1", "PR-1-ROW-1"),
        ])
        self.assertEqual(result["results"][0]["values"]["aggregated_value"], "0")
        self.assertEqual(result["summary"]["skipped"], 0)


if __name__ == "__main__":
    unittest.main()
