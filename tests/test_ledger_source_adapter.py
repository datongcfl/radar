import json
import tempfile
import unittest
from io import BytesIO
from zipfile import ZipFile
from pathlib import Path

from radar.discovery import new_record
from radar.discovery_store import JsonWorkspaceStore
from radar.ledger_source_adapter import (
    LedgerSourceAdapterError,
    adapt_ledger_source,
    validate_ledger_source_adapter,
)
from radar.ledger_vouchers import validate_gl_vouchers
from radar.ledger_workspace import load_ledger_bundle


def make_workspace(root):
    workspace_id = "ws_ledger-adapter"
    store = JsonWorkspaceStore(root, workspace_id)
    workspace = new_record(
        "workspace", name="Ledger adapter test", description="",
        status="active", pack_refs=[],
    ).to_dict()
    workspace["id"] = workspace_id
    store.initialize(workspace)
    return store


def stock_mapping():
    return {
        "id": "demo-stock-csv-v1",
        "source_system": "erp-demo",
        "format": "csv",
        "ledger_kind": "stock",
        "header_row": 1,
        "delimiter": ",",
        "field_map": {
            "ledger_entry_id": "Ledger Entry ID",
            "company_id": "Company ID",
            "voucher_type": "Voucher Type",
            "voucher_id": "Voucher ID",
            "voucher_item_id": "Voucher Item ID",
            "event_kind": "Event Kind",
            "posting_status": "Posting Status",
            "currency": "Currency",
            "accounting_period": "Accounting Period",
            "posting_date": "Posting Date",
            "item_id": "Item ID",
            "warehouse_id": "Warehouse ID",
            "quantity_delta": "Quantity Delta",
            "quantity_uom": "Quantity UOM",
            "stock_value_delta": "Stock Value Delta",
        },
        "optional_fields": ["posting_date"],
        "value_maps": {"posting_status": {"Posted": "posted", "Reversal": "reversal"}},
        "number_format": {"decimal_separator": ".", "thousands_separator": ","},
        "date_format": "%Y-%m-%d",
    }


def gl_mapping():
    mapping = stock_mapping()
    mapping.update({
        "id": "demo-gl-csv-v1",
        "ledger_kind": "general_ledger",
        "field_map": {
            "ledger_entry_id": "Ledger Entry ID",
            "company_id": "Company ID",
            "voucher_type": "Voucher Type",
            "voucher_id": "Voucher ID",
            "voucher_item_id": "Voucher Item ID",
            "event_kind": "Event Kind",
            "posting_status": "Posting Status",
            "currency": "Currency",
            "accounting_period": "Accounting Period",
            "posting_date": "Posting Date",
            "account_id": "Account ID",
            "debit_amount": "Debit Amount",
            "credit_amount": "Credit Amount",
        },
        "optional_fields": ["posting_date"],
    })
    return mapping


def make_xlsx(headers, rows):
    stream = BytesIO()
    workbook = (
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Stock" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    relationships = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Target="worksheets/sheet1.xml" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>'
        '</Relationships>'
    )
    all_rows = [headers] + rows
    sheet_rows = []
    for row_number, values in enumerate(all_rows, 1):
        cells = []
        for column_number, value in enumerate(values, 1):
            column = ""
            n = column_number
            while n:
                n, remainder = divmod(n - 1, 26)
                column = chr(65 + remainder) + column
            cell_ref = "%s%d" % (column, row_number)
            text = str(value)
            escaped = (text.replace("&", "&amp;").replace("<", "&lt;")
                       .replace(">", "&gt;"))
            cells.append('<c r="%s" t="inlineStr"><is><t>%s</t></is></c>' %
                         (cell_ref, escaped))
        sheet_rows.append('<row r="%d">%s</row>' % (row_number, "".join(cells)))
    worksheet = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData>%s</sheetData></worksheet>' % "".join(sheet_rows)
    )
    with ZipFile(stream, "w") as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)
    return stream.getvalue()


class TestLedgerSourceAdapter(unittest.TestCase):
    def test_stock_csv_creates_row_evidence_and_ledger_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_workspace(tmp)
            source = Path(tmp) / "stock.csv"
            source.write_text(
                "Ledger Entry ID,Company ID,Voucher Type,Voucher ID,Voucher Item ID,Event Kind,Posting Status,Currency,Accounting Period,Posting Date,Item ID,Warehouse ID,Quantity Delta,Quantity UOM,Stock Value Delta\n"
                "SLE-1,C1,Receipt,GR-1,ROW-1,receipt,Posted,USD,2026-11,2026-11-20,CABLE-1,WH-1,10,EA,125.50\n",
                encoding="utf-8",
            )
            result = adapt_ledger_source(store, str(source), stock_mapping())
            self.assertEqual(result["ledger_effects_imported"], 1)
            self.assertEqual(result["rows_with_evidence"], 1)
            effects = store.list_records("ledger_effect")
            self.assertEqual(len(effects), 1)
            effect = effects[0]["effect"]
            self.assertEqual(effect["quantity_delta"], "10")
            self.assertEqual(effect["stock_value_delta"], "125.50")
            self.assertEqual(effect["locator"], {
                "path": "stock.csv", "row": 2, "block": "row"
            })
            evidence = store.list_records("evidence")[0]
            self.assertEqual(evidence["verification_status"], "source_confirmed")

    def test_xlsx_source_uses_sheet_row_locator(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_workspace(tmp)
            mapping = stock_mapping()
            mapping.update({"format": "xlsx", "sheet_name": "Stock"})
            mapping.pop("delimiter")
            headers = [
                "Ledger Entry ID", "Company ID", "Voucher Type", "Voucher ID",
                "Voucher Item ID", "Event Kind", "Posting Status", "Currency",
                "Accounting Period", "Posting Date", "Item ID", "Warehouse ID",
                "Quantity Delta", "Quantity UOM", "Stock Value Delta",
            ]
            values = [
                "SLE-X1", "C1", "Receipt", "GR-X1", "ROW-1", "receipt",
                "Posted", "USD", "2026-11", "2026-11-20", "CABLE-1", "WH-1",
                "3", "EA", "30",
            ]
            source = Path(tmp) / "stock.xlsx"
            source.write_bytes(make_xlsx(headers, [values]))
            result = adapt_ledger_source(store, str(source), mapping)
            self.assertEqual(result["ledger_effects_imported"], 1)
            effect = store.list_records("ledger_effect")[0]["effect"]
            self.assertEqual(effect["locator"], {
                "path": "stock.xlsx", "sheet": "Stock", "row": 2, "block": "row"
            })

    def test_reimport_is_idempotent_for_same_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_workspace(tmp)
            source = Path(tmp) / "stock.csv"
            source.write_text(
                "Ledger Entry ID,Company ID,Voucher Type,Voucher ID,Voucher Item ID,Event Kind,Posting Status,Currency,Accounting Period,Posting Date,Item ID,Warehouse ID,Quantity Delta,Quantity UOM,Stock Value Delta\n"
                "SLE-1,C1,Receipt,GR-1,ROW-1,receipt,Posted,USD,2026-11,2026-11-20,CABLE-1,WH-1,10,EA,125.50\n",
                encoding="utf-8",
            )
            first = adapt_ledger_source(store, str(source), stock_mapping())
            second = adapt_ledger_source(store, str(source), stock_mapping())
            self.assertEqual(first["ledger_effects_imported"], 1)
            self.assertEqual(second["ledger_effects_imported"], 0)
            self.assertEqual(len(store.list_records("ledger_effect")), 1)
            self.assertEqual(len(store.list_records("evidence")), 1)

    def test_ambiguous_headers_fail_before_creating_source_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_workspace(tmp)
            source = Path(tmp) / "ambiguous.csv"
            source.write_text(
                "Ledger Entry ID,ledger_entry_id,Company ID\nX1,X1,C1\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(LedgerSourceAdapterError, "ambiguous"):
                adapt_ledger_source(store, str(source), stock_mapping())
            self.assertEqual(store.list_records("asset"), [])

    def test_invalid_decimal_is_unresolved_but_source_evidence_is_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_workspace(tmp)
            source = Path(tmp) / "stock.csv"
            source.write_text(
                "Ledger Entry ID,Company ID,Voucher Type,Voucher ID,Voucher Item ID,Event Kind,Posting Status,Currency,Accounting Period,Posting Date,Item ID,Warehouse ID,Quantity Delta,Quantity UOM,Stock Value Delta\n"
                "SLE-1,C1,Receipt,GR-1,ROW-1,receipt,Posted,USD,2026-11,2026-11-20,CABLE-1,WH-1,10,EA,not-money\n",
                encoding="utf-8",
            )
            result = adapt_ledger_source(store, str(source), stock_mapping())
            self.assertEqual(result["ledger_effects_imported"], 0)
            self.assertEqual(result["rows_with_evidence"], 1)
            self.assertEqual(result["unresolved"][0]["reason"],
                             "row_mapping_or_validation_failed")
            self.assertEqual(store.list_records("ledger_effect"), [])

    def test_conflicting_duplicate_source_ids_are_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_workspace(tmp)
            source = Path(tmp) / "stock.csv"
            header = "Ledger Entry ID,Company ID,Voucher Type,Voucher ID,Voucher Item ID,Event Kind,Posting Status,Currency,Accounting Period,Posting Date,Item ID,Warehouse ID,Quantity Delta,Quantity UOM,Stock Value Delta\n"
            row1 = "SLE-1,C1,Receipt,GR-1,ROW-1,receipt,Posted,USD,2026-11,2026-11-20,CABLE-1,WH-1,10,EA,100\n"
            row2 = "SLE-1,C1,Receipt,GR-1,ROW-1,receipt,Posted,USD,2026-11,2026-11-20,CABLE-1,WH-1,12,EA,120\n"
            source.write_text(header + row1 + row2, encoding="utf-8")
            result = adapt_ledger_source(store, str(source), stock_mapping())
            self.assertEqual(result["ledger_effects_imported"], 0)
            self.assertTrue(any(x["reason"] == "conflicting_duplicate_source_identity"
                                for x in result["unresolved"]))
            self.assertEqual(store.list_records("ledger_effect"), [])

    def test_gl_manifest_is_external_and_voucher_completeness_is_checkable(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_workspace(tmp)
            source = Path(tmp) / "gl.csv"
            source.write_text(
                "Ledger Entry ID,Company ID,Voucher Type,Voucher ID,Voucher Item ID,Event Kind,Posting Status,Currency,Accounting Period,Posting Date,Account ID,Debit Amount,Credit Amount\n"
                "GL-1,C1,Journal Entry,JV-1,ROW-1,receipt_accrual,Posted,USD,2026-11,2026-11-20,INV,100,0\n"
                "GL-2,C1,Journal Entry,JV-1,ROW-2,receipt_accrual,Posted,USD,2026-11,2026-11-20,INV,0,100\n",
                encoding="utf-8",
            )
            manifest = Path(tmp) / "gl-export-manifest.jsonl"
            manifest.write_text(json.dumps({
                "id": "MAN-1", "source_system": "erp-demo", "company_id": "C1",
                "currency": "USD", "voucher_type": "Journal Entry", "voucher_id": "JV-1",
                "accounting_period": "2026-11",
                "expected_ledger_entry_ids": ["GL-1", "GL-2"],
                "export_id": "ERP-EXPORT-2026-11-20",
            }) + "\n", encoding="utf-8")
            result = adapt_ledger_source(store, str(source), gl_mapping(),
                                         manifest_path=str(manifest))
            self.assertEqual(result["ledger_effects_imported"], 2)
            self.assertEqual(result["extraction_manifests_imported"], 1)
            bundle = load_ledger_bundle(store)
            vouchers = validate_gl_vouchers(
                bundle["ledger_effects"], bundle["extraction_manifests"],
                bundle["evidence_records"],
            )
            self.assertEqual(vouchers["summary"]["balanced"], 1)
            self.assertEqual(vouchers["results"][0]["status"], "balanced")
            manifest_evidence = next(
                item for item in bundle["evidence_records"]
                if item["id"] == bundle["extraction_manifests"][0]["evidence_id"]
            )
            self.assertEqual(manifest_evidence["verification_status"], "unverified")

    def test_mapping_requires_explicit_period_and_numeric_locale(self):
        mapping = stock_mapping()
        mapping["field_map"].pop("accounting_period")
        mapping["number_format"].pop("decimal_separator")
        with self.assertRaises(LedgerSourceAdapterError):
            validate_ledger_source_adapter(mapping)


if __name__ == "__main__":
    unittest.main()
