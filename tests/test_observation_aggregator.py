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
        {"id": evidence, "asset_id": asset, "locator": dict(value_locator)}
    ]
    for index, field in enumerate(("purchase_order_id", "purchase_order_item_id"), 1):
        scope_id = evidence + "_scope_" + str(index)
        locator = {"path": identifier + ".csv", "row": 2, "column": index}
        scope_provenance[field] = {"evidence_id": scope_id, "locator": dict(locator)}
        records.append({"id": scope_id, "asset_id": asset, "locator": dict(locator)})
    observation = {
        "id": identifier, "asset_id": asset,
        "invariant_id": "receipt_quantity_balance",
        "business_scope": scope, "scope_provenance": scope_provenance,
        "values": {"received_qty": str(qty)},
        "field_provenance": {"received_qty": {
            "evidence_id": evidence, "locator": dict(value_locator)}},
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
        first = row("obs1", "PO-1", "LINE-1", 40, evidence="ev_shared", asset="asset_shared")
        second = row("obs2", "PO-1", "LINE-1", 40, evidence="ev_shared", asset="asset_shared")
        second[0]["field_provenance"]["received_qty"]["locator"] = first[0]["field_provenance"]["received_qty"]["locator"]
        for field in ("purchase_order_id", "purchase_order_item_id"):
            second[0]["scope_provenance"][field]["locator"] = first[0]["scope_provenance"][field]["locator"]
        for record in second[1]:
            match = next(item for item in first[1] if item["id"] == record["id"])
            record["locator"] = match["locator"]
        result = self._aggregate([first, second])
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

    def _transactional_row(self, identifier, po, line, qty, status="1",
                           is_return="0", return_against="", receipt="PR-1",
                           receipt_item="PR-1-ROW-1", asset=None):
        item, records = row(identifier, po, line, qty, asset=asset)
        item["business_scope"].update({"receipt_id": receipt, "receipt_item_id": receipt_item})
        scope_fields = ("receipt_id", "receipt_item_id")
        for index, field in enumerate(scope_fields, 10):
            evidence_id = "ev_" + identifier + "_" + field
            locator = {"path": identifier + ".csv", "row": 2, "column": index}
            item["scope_provenance"][field] = {"evidence_id": evidence_id, "locator": locator}
            records.append({"id": evidence_id, "asset_id": item["asset_id"], "locator": locator})
        tx = {"document_status": status, "is_return": is_return, "return_against": return_against}
        txp = {}
        for index, field in enumerate(("document_status", "is_return", "return_against"), 20):
            if field == "return_against" and not return_against:
                continue
            evidence_id = "ev_" + identifier + "_" + field
            locator = {"path": identifier + ".csv", "row": 2, "column": index}
            txp[field] = {"evidence_id": evidence_id, "locator": locator}
            records.append({"id": evidence_id, "asset_id": item["asset_id"], "locator": locator})
        item["transaction"] = tx
        item["transaction_provenance"] = txp
        return item, records

    def _aggregate_transactional(self, rows):
        rule = dict(RULE)
        rule["transaction_semantics"] = {
            "status_field": "document_status",
            "posted_values": ["1", "submitted"],
            "non_posted_values": ["0", "2", "draft", "cancelled"],
            "return_flag_field": "is_return",
            "return_values": ["1", "true", "yes"],
            "normal_values": ["0", "false", "no", ""],
            "return_reference_field": "return_against",
            "deduplicate_by": ["receipt_id", "receipt_item_id"],
        }
        observations = [item[0] for item in rows]
        evidence = [record for item in rows for record in item[1]]
        return aggregate_observations(rule, observations, evidence_records=evidence)

    def test_cancelled_and_draft_documents_do_not_enter_posted_total(self):
        result = self._aggregate_transactional([
            self._transactional_row("obs1", "PO-1", "LINE-1", 40, status="1"),
            self._transactional_row("obs2", "PO-1", "LINE-1", 20, status="2"),
            self._transactional_row("obs3", "PO-1", "LINE-1", 10, status="0"),
        ])
        self.assertEqual(result["results"][0]["values"]["cumulative_received_qty"], "40")
        self.assertEqual(result["summary"]["skipped"], 2)

    def test_return_is_negative_and_requires_reference_to_original_receipt(self):
        result = self._aggregate_transactional([
            self._transactional_row("obs1", "PO-1", "LINE-1", 40, receipt="PR-1", receipt_item="PR-1-1"),
            self._transactional_row("obs2", "PO-1", "LINE-1", 5, is_return="1",
                                    return_against="PR-1", receipt="RET-1", receipt_item="RET-1-1"),
        ])
        self.assertEqual(result["results"][0]["values"]["cumulative_received_qty"], "35")
        contribution = result["results"][0]["contributions"][0]
        self.assertEqual(set(contribution["scope_provenance"]), {
            "purchase_order_id", "purchase_order_item_id", "receipt_id", "receipt_item_id"})
        self.assertEqual(set(contribution["transaction_provenance"]), {
            "document_status", "is_return", "return_against"})

    def test_return_without_original_reference_is_unresolved(self):
        item, records = self._transactional_row("obs1", "PO-1", "LINE-1", 5,
                                                is_return="1", return_against="")
        result = self._aggregate_transactional([(item, records)])
        self.assertEqual(result["results"], [])
        self.assertEqual(result["skipped"][0]["reason"], "unresolved_return_reference")

    def test_duplicate_imported_transaction_is_counted_once(self):
        first = self._transactional_row("obs1", "PO-1", "LINE-1", 40,
                                        receipt="PR-1", receipt_item="PR-1-1")
        second = self._transactional_row("obs2", "PO-1", "LINE-1", 40,
                                         receipt="PR-1", receipt_item="PR-1-1", asset="asset_obs1")
        # Duplicate imports point to the same source cells and business row identity.
        for field in ("received_qty",):
            second[0]["field_provenance"][field] = first[0]["field_provenance"][field]
        for field in ("purchase_order_id", "purchase_order_item_id", "receipt_id", "receipt_item_id"):
            second[0]["scope_provenance"][field] = first[0]["scope_provenance"][field]
        for field in ("document_status", "is_return"):
            second[0]["transaction_provenance"][field] = first[0]["transaction_provenance"][field]
        records_by_id = {item["id"]: item for item in first[1]}
        second = (second[0], [records_by_id.get(item["id"], item) for item in second[1]])
        result = self._aggregate_transactional([first, second])
        self.assertEqual(result["results"][0]["values"]["cumulative_received_qty"], "40")
        self.assertEqual(result["summary"]["duplicate_transactions"], 1)

    def test_conflicting_duplicate_transaction_identity_excludes_both(self):
        first = self._transactional_row("obs1", "PO-1", "LINE-1", 40,
                                        receipt="PR-1", receipt_item="PR-1-1")
        second = self._transactional_row("obs2", "PO-1", "LINE-1", 41,
                                         receipt="PR-1", receipt_item="PR-1-1", asset="asset_obs1")
        for field in ("purchase_order_id", "purchase_order_item_id", "receipt_id", "receipt_item_id"):
            second[0]["scope_provenance"][field] = first[0]["scope_provenance"][field]
        # Same transaction identity but conflicting value: neither version is trusted.
        result = self._aggregate_transactional([first, second])
        self.assertEqual(result["results"], [])
        self.assertEqual(result["summary"]["skipped"], 2)

    def test_non_finite_values_rejected(self):
        item, evidence = row("obs1", "PO-1", "LINE-1", "NaN")
        with self.assertRaises(ObservationAggregationError):
            aggregate_observations(RULE, [item], evidence_records=evidence)


if __name__ == "__main__":
    unittest.main()
