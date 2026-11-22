"""Failing contract tests for the 2026-11-22 branch review.

These tests encode the desired behavior. They are expected to fail against
feat/requirement-driven-discovery@07c6ec7b and pass only after the review P0/P1
fixes are implemented. They are not part of the normal test suite.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from radar.business_invariants import (
    ObservationError,
    evaluate_business_invariants,
    validate_observation_bundle,
)
from radar.business_observation_extractor import extract_table_observations
from radar.business_table_evidence import select_required_table_chunks
from radar.discovery import new_record
from radar.discovery_store import JsonWorkspaceStore, StorageError
from radar.document_parser import extract_office_document
from radar.ledger_aggregator import aggregate_ledger_effects
from radar.ledger_workspace import import_ledger_bundle
from radar.legacy import convert_legacy_sources


def _invariant(**updates):
    item = {
        "id": "receipt_quantity_balance",
        "operator": "sum_equals",
        "fields": ["accepted_qty", "rejected_qty"],
        "target_field": "received_qty",
        "field_aliases": {
            "accepted_qty": ["accepted_qty"],
            "rejected_qty": ["rejected_qty"],
            "received_qty": ["received_qty"],
        },
    }
    item.update(updates)
    return item


def _chunks(accepted="8", rejected="2", received="10", duplicate_received=None):
    chunks = [
        {"text": "accepted_qty", "locator": {"path": "receipts.csv", "row": 1, "column": 1}},
        {"text": "rejected_qty", "locator": {"path": "receipts.csv", "row": 1, "column": 2}},
        {"text": "received_qty", "locator": {"path": "receipts.csv", "row": 1, "column": 3}},
        {"text": accepted, "locator": {"path": "receipts.csv", "row": 2, "column": 1}},
        {"text": rejected, "locator": {"path": "receipts.csv", "row": 2, "column": 2}},
        {"text": received, "locator": {"path": "receipts.csv", "row": 2, "column": 3}},
    ]
    if duplicate_received is not None:
        chunks.append({
            "text": "received_qty",
            "locator": {"path": "receipts.csv", "row": 1, "column": 4},
        })
        chunks.append({
            "text": duplicate_received,
            "locator": {"path": "receipts.csv", "row": 2, "column": 4},
        })
    return chunks


def _evidence(accepted="8", rejected="2", received="10"):
    rows = []
    for index, (column, text) in enumerate(
            ((1, accepted), (2, rejected), (3, received)), start=1):
        rows.append({
            "id": "evd_contract_%d" % index,
            "asset_id": "ast_contract",
            "locator": {"path": "receipts.csv", "row": 2, "column": column},
            "statement": text,
            "excerpt": text,
            "verification_status": "source_confirmed",
            "metadata": {"verification": {"level": "document_text"}},
        })
    return rows


def _stock_row(entry_id, source_system, quantity, evidence_id, row):
    return {
        "ledger_entry_id": entry_id,
        "source_system": source_system,
        "ledger_kind": "stock",
        "company_id": "CO",
        "voucher_type": "Purchase Receipt",
        "voucher_id": "PR-1",
        "voucher_item_id": "ROW-1",
        "source_document_ref": {
            "voucher_type": "Purchase Receipt", "voucher_id": "PR-1",
            "voucher_item_id": "ROW-1",
        },
        "event_kind": "receipt",
        "posting_status": "posted",
        "currency": "USD",
        "asset_id": "asset-1",
        "item_id": "ITEM",
        "warehouse_id": "WH",
        "quantity_delta": quantity,
        "quantity_uom": "EA",
        "stock_value_delta": "19.50",
        "evidence_id": evidence_id,
        "locator": {"path": "ledger.csv", "row": row, "column": 1},
    }


def _minimal_store(root):
    workspace = new_record("workspace", name="contract-test",
                           status="active", pack_refs=[]).to_dict()
    workspace["id"] = "ws_contract"
    store = JsonWorkspaceStore(root, "ws_contract")
    store.initialize(workspace)

    source = new_record("source", provider="enterprise",
                        uri="file:///erp/export", name="ERP export",
                        access_status="proprietary").to_dict()
    asset = new_record("asset", source_id=source["id"], asset_type="dataset",
                       uri="file:///erp/export/stock.csv", title="Stock ledger export",
                       status="active").to_dict()
    evidence = new_record(
        "evidence", workspace_id="ws_contract", asset_id=asset["id"],
        evidence_kind="data", statement="ERP stock ledger row",
        locator={"path": "stock.csv", "row": 2, "column": 1},
        captured_at="2026-11-22T00:00:00Z",
        verification_status="source_confirmed",
    ).to_dict()
    store.append(source)
    store.append(asset)
    store.append(evidence)
    return store, evidence


class TestTransactionTablePath(unittest.TestCase):
    """P0-2: transaction columns must survive selection and extraction."""

    def test_transaction_columns_are_selected(self):
        invariant = _invariant(
            transaction_fields={"docstatus": ["docstatus"], "is_return": ["is_return"]},
        )
        chunks = _chunks() + [
            {"text": "docstatus", "locator": {"path": "receipts.csv", "row": 1, "column": 4}},
            {"text": "is_return", "locator": {"path": "receipts.csv", "row": 1, "column": 5}},
            {"text": "posted", "locator": {"path": "receipts.csv", "row": 2, "column": 4}},
            {"text": "false", "locator": {"path": "receipts.csv", "row": 2, "column": 5}},
        ]
        selected = select_required_table_chunks([invariant], chunks)
        texts = {item["text"] for item in selected}
        self.assertTrue({"docstatus", "is_return", "posted", "false"}.issubset(texts),
                        "transaction columns were dropped by selector: %r" % texts)


class TestObservationEvidenceBinding(unittest.TestCase):
    """P0-3: values must come from the referenced Evidence content."""

    def test_changed_cell_value_cannot_use_old_evidence(self):
        out = extract_table_observations(
            [_invariant()], _chunks(accepted="99", received="101"),
            _evidence(accepted="8", received="10"), "ast_contract",
        )
        # A skipped row is acceptable; a produced observation must be explicitly
        # unknown, not silently treated as verified/pass.
        self.assertTrue(
            not out["observations"]
            or all(item.get("status") in ("unknown", "rejected")
                   for item in out["observations"]),
            "extractor accepted 99/101 from a file while Evidence says 8/10",
        )

    def test_tampered_provenance_locator_is_rejected(self):
        out = extract_table_observations(
            [_invariant()], _chunks(), _evidence(), "ast_contract",
        )
        self.assertEqual(len(out["observations"]), 1)
        out["observations"][0]["field_provenance"]["accepted_qty"]["locator"] = {
            "path": "totally-different.csv", "row": 99, "column": 7,
        }
        with self.assertRaises(ObservationError):
            validate_observation_bundle(out, [_invariant()], _evidence())


class TestEvidenceStatusPropagation(unittest.TestCase):
    """P0-4 / P1-4: rejected and incomplete provenance cannot pass."""

    def test_rejected_evidence_cannot_pass(self):
        invariant = {
            "id": "i",
            "operator": "less_than_or_equal",
            "fields": ["a", "b"],
            "scope_fields": [],
        }
        row = {
            "id": "obs_contract",
            "asset_id": "ast_contract",
            "invariant_id": "i",
            "scope_key": "x",
            "origin": "test",
            "values": {"a": "1", "b": "2"},
            "field_provenance": {
                "a": {"evidence_id": "evd_rejected",
                      "locator": {"path": "x.csv", "row": 2, "column": 1},
                      "verification_level": "test_fixture"},
                "b": {"evidence_id": "evd_rejected",
                      "locator": {"path": "x.csv", "row": 2, "column": 1},
                      "verification_level": "test_fixture"},
            },
            "business_scope": {},
            "scope_provenance": {},
        }
        evidence = [{
            "id": "evd_rejected", "asset_id": "ast_contract",
            "locator": {"path": "x.csv", "row": 2, "column": 1},
            "verification_status": "rejected",
            "metadata": {"verification": {"level": "test_fixture"}},
        }]
        try:
            result = evaluate_business_invariants(
                [invariant], {"schema_version": 1, "observations": [row]}, evidence)
        except ObservationError:
            return
        self.assertNotEqual(result["evaluations"][0]["outcome"], "pass",
                            "rejected Evidence produced a pass")

    def test_missing_scope_fields_are_rejected(self):
        invariant = _invariant(scope_fields=["purchase_order_id"])
        out = extract_table_observations(
            [invariant], _chunks(), _evidence(), "ast_contract",
        )
        # The selector/extractor must either skip an incomplete scope or the
        # validator must reject it; neither may silently pass with scope={}.
        try:
            validate_observation_bundle(out, [invariant], _evidence())
        except ObservationError:
            return
        self.assertTrue(
            not out["observations"]
            or all(item.get("status") in ("unknown", "rejected")
                   for item in out["observations"]),
            "observation without declared scope fields passed as verified",
        )


class TestLedgerImportPreflight(unittest.TestCase):
    """P0-5: a semantically invalid bundle must not append records."""

    def test_missing_ledger_kind_is_rejected_before_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, evidence = _minimal_store(tmp)
            effect = {
                "ledger_entry_id": "STK-1",
                "source_system": "ERP-A",
                # ledger_kind intentionally missing
                "company_id": "C1",
                "voucher_type": "Receipt",
                "voucher_id": "PR-1",
                "voucher_item_id": "1",
                "event_kind": "receipt",
                "posting_status": "posted",
                "currency": "USD",
                "evidence_id": evidence["id"],
                "asset_id": evidence["asset_id"],
                "locator": evidence["locator"],
                "quantity_delta": "2",
                "stock_value_delta": "20",
                "item_id": "ITEM-1",
                "warehouse_id": "WH-1",
                "quantity_uom": "EA",
            }
            bundle = {
                "ledger_effects": [effect],
                "evidence_records": [evidence],
                "extraction_manifests": [],
                "aggregation_rules": [],
            }
            with self.assertRaises(StorageError):
                import_ledger_bundle(store, bundle)
            self.assertEqual(store.list_records("ledger_effect"), [],
                             "invalid import left ledger_effect records behind")


class TestLedgerAggregationIdentity(unittest.TestCase):
    """P0-6: same entry id from two sources must not be silently replaced."""

    def test_two_sources_sum_and_keep_two_contributions(self):
        rows = [
            _stock_row("E1", "S1", "5", "evd_1", 2),
            _stock_row("E1", "S2", "7", "evd_2", 3),
        ]
        evidence = [
            {"id": "evd_1", "asset_id": "asset-1",
             "locator": {"path": "ledger.csv", "row": 2, "column": 1}},
            {"id": "evd_2", "asset_id": "asset-1",
             "locator": {"path": "ledger.csv", "row": 3, "column": 1}},
        ]
        rule = {
            "id": "stock_qty", "ledger_kind": "stock", "metric": "quantity_delta",
            "output_field": "qty", "group_by": [
                "company_id", "currency", "item_id", "warehouse_id", "quantity_uom"],
        }
        result = aggregate_ledger_effects(rows, evidence, [rule])[0]
        aggregate = result["results"][0]
        # Independent sources should sum to 12; if the implementation treats
        # them as mirror records, it must say so explicitly. It must not replace
        # one source with the other and report neither conflict nor duplicate.
        silently_merged = (
            aggregate["contribution_count"] == 1
            and not result["skipped"]
            and not result.get("duplicate_transactions", [])
        )
        self.assertFalse(silently_merged,
                         "S2/E1 silently replaced S1/E1 (qty=%s, count=%s)" %
                         (aggregate["values"]["qty"], aggregate["contribution_count"]))
        if aggregate["contribution_count"] == 2:
            self.assertEqual(aggregate["values"]["qty"], "12")


class TestLegacyLocatorAndIdentity(unittest.TestCase):
    """P0-7 / P1-5: free-text note is not a locator; covers order is stable."""

    def _legacy(self, covers=None, locator=None):
        return {
            "id": "s1",
            "url": "https://example.com/a",
            "title": "A",
            "platform": "web",
            "artifact_type": "article",
            "covers": covers or ["u2", "u1"],
            "quotes": [{"text": "quote", "locator": locator}] if locator else [],
        }

    def test_note_is_not_upgraded_to_evidence(self):
        converted = convert_legacy_sources(
            [self._legacy(locator={"note": "somewhere on page 3"})],
            "ws_contract", captured_at="2026-11-22T00:00:00Z",
        )
        self.assertEqual(converted["evidence"], [])
        self.assertEqual(len(converted["pending_quotes"]), 1)

    def test_legacy_covers_are_canonicalized(self):
        converted = convert_legacy_sources(
            [self._legacy()], "ws_contract", captured_at="2026-11-22T00:00:00Z",
        )
        self.assertEqual(converted["assets"][0]["metadata"]["legacy_covers"], ["u1", "u2"])


class TestTableInputHygiene(unittest.TestCase):
    """P1-1 / P1-2: ambiguous headers and locale-ambiguous numbers are skipped."""

    def test_duplicate_received_qty_header_is_not_silently_last_wins(self):
        evidence = _evidence(received="10") + [{
            "id": "evd_contract_4",
            "asset_id": "ast_contract",
            "locator": {"path": "receipts.csv", "row": 2, "column": 4},
            "statement": "999",
            "excerpt": "999",
            "verification_status": "source_confirmed",
            "metadata": {"verification": {"level": "document_text"}},
        }]
        out = extract_table_observations(
            [_invariant()],
            _chunks(received="10", duplicate_received="999"),
            evidence, "ast_contract",
        )
        self.assertEqual(out["observations"], [],
                         "duplicate received_qty header silently selected 999")

    def test_european_decimal_comma_is_not_stripped_to_integer(self):
        invariant = {
            "id": "i",
            "operator": "less_than_or_equal",
            "fields": ["accepted_qty", "received_qty"],
            "field_aliases": {
                "accepted_qty": ["accepted_qty"],
                "received_qty": ["received_qty"],
            },
        }
        out = extract_table_observations(
            [invariant],
            _chunks(accepted="1,23", rejected="0", received="2"),
            _evidence(accepted="1,23", received="2"), "ast_contract",
        )
        self.assertEqual(out["observations"], [],
                         "1,23 was silently normalized to 123")


class TestOfficeParserSafety(unittest.TestCase):
    """P0-8: untrusted Office XML with DTD/entity declarations must fail closed."""

    def test_docx_with_doctype_is_not_parsed(self):
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE document>\n'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>hello</w:t></w:r></w:p></w:body></w:document>'
        )
        buffer = __import__("io").BytesIO()
        with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
            archive.writestr("word/document.xml", xml)
        result = extract_office_document(buffer.getvalue(), "docx")
        self.assertNotEqual(result["status"], "parsed",
                            "DOCX with a DOCTYPE was parsed instead of rejected")


class TestMergePreservation(unittest.TestCase):
    """P0-1: replay must preserve main's parse capability and XML safety."""

    def test_merged_tree_still_exposes_parse_and_xml_safety(self):
        cli_source = Path(__import__("radar.cli").cli.__file__).read_text(encoding="utf-8")
        self.assertIn('add_parser("parse"', cli_source,
                      "replay dropped main's parse CLI")
        self.assertTrue(
            Path(__import__("radar").__file__).with_name("xml_safety.py").is_file(),
            "replay dropped main's xml_safety module",
        )


if __name__ == "__main__":
    unittest.main()
