import builtins
import hashlib
import importlib.util
import io
import unittest
import warnings
import zipfile
import xml.etree.ElementTree as ET
from datetime import date
from unittest.mock import patch

from radar.capabilities import CapabilityContext
from radar.xlsx_parser import XlsxDocumentParserCapability


def make_minimal_xlsx(workbook_xml=None):
    if workbook_xml is None:
        workbook_xml = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            b'<sheets/></workbook>'
        )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        archive.writestr("xl/workbook.xml", workbook_xml)
    return output.getvalue()


def make_workbook():
    from openpyxl import Workbook
    from openpyxl.worksheet.table import Table
    from openpyxl.workbook.defined_name import DefinedName

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Data"
    workbook.create_sheet("Visible")
    sheet.append(["Item", "Amount"])
    sheet.append(["Steel", 10])
    sheet.append(["Copper", 20])
    sheet["C2"] = "=SUM(B2:B3)"
    sheet["D2"] = date(2026, 1, 2)
    sheet.merge_cells("E1:F1")
    sheet["E1"] = "Merged header"
    sheet.sheet_state = "veryHidden"
    sheet.add_table(Table(displayName="SalesTable", ref="A1:B3"))
    workbook.defined_names.add(DefinedName("SalesTotal", attr_text="'Data'!$B$2:$B$3"))
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def with_cached_formula(content, coordinate="C2", cached="30"):
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(content), "r") as original:
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as updated:
            for item in original.infolist():
                data = original.read(item.filename)
                if item.filename == "xl/worksheets/sheet1.xml":
                    root = ET.fromstring(data)
                    for cell in root.iter():
                        if cell.tag.rsplit("}", 1)[-1] == "c" and cell.attrib.get("r") == coordinate:
                            for child in cell:
                                if child.tag.rsplit("}", 1)[-1] == "v":
                                    child.text = cached
                    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
                updated.writestr(item, data)
    return output.getvalue()


class TestXlsxPreflightAndOptionalBoundary(unittest.TestCase):
    def parse(self, content, filename="sample.xlsx"):
        return XlsxDocumentParserCapability().execute(CapabilityContext(
            operation="parse",
            inputs={"content": content, "uri": "https://example.test/" + filename,
                    "filename": filename},
        ))

    def test_missing_optional_dependency_returns_unavailable(self):
        original_import = builtins.__import__

        def import_without_openpyxl(name, *args, **kwargs):
            if name == "openpyxl":
                raise ImportError("simulated missing optional dependency")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=import_without_openpyxl):
            result = self.parse(make_minimal_xlsx())
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.warnings[0]["dependency"], "openpyxl")

    def test_unsafe_xml_is_rejected_before_optional_import(self):
        xml = b'<!DOCTYPE x [<!ENTITY e "unsafe">]><workbook/>'
        result = self.parse(make_minimal_xlsx(xml))
        self.assertEqual(result.error["code"], "xlsx_unsafe_xml_declaration")

    def test_input_cell_and_sheet_limits(self):
        limited = XlsxDocumentParserCapability(max_bytes=20).execute(CapabilityContext(
            operation="parse",
            inputs={"content": make_minimal_xlsx(), "uri": "file:///x.xlsx",
                    "filename": "x.xlsx"},
        ))
        self.assertEqual(limited.error["code"], "xlsx_too_large")

        workbook_xml = (
            b'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            b'<sheets><sheet name="A" sheetId="1"/><sheet name="B" sheetId="2"/></sheets></workbook>'
        )
        sheet_limited = XlsxDocumentParserCapability(max_sheets=1).execute(CapabilityContext(
            operation="parse",
            inputs={"content": make_minimal_xlsx(workbook_xml), "uri": "file:///x.xlsx",
                    "filename": "x.xlsx"},
        ))
        self.assertEqual(sheet_limited.error["code"], "xlsx_sheet_limit_exceeded")

        if importlib.util.find_spec("openpyxl"):
            cell_limited = XlsxDocumentParserCapability(max_cells=1).execute(CapabilityContext(
                operation="parse",
                inputs={"content": make_workbook(), "uri": "file:///x.xlsx", "filename": "x.xlsx"},
            ))
            self.assertEqual(cell_limited.error["code"], "xlsx_cell_limit_exceeded")

    def test_unsafe_paths_and_duplicate_entries_are_rejected(self):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", b"<Types/>")
            archive.writestr("xl/workbook.xml", b"<workbook/>")
            archive.writestr("../escape.xml", b"<escape/>")
        unsafe = self.parse(output.getvalue())
        self.assertEqual(unsafe.error["code"], "xlsx_unsafe_archive_path")

        output = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("[Content_Types].xml", b"<Types/>")
                archive.writestr("xl/workbook.xml", b"<workbook/>")
                archive.writestr("xl/workbook.xml", b"<workbook/>")
        duplicate = self.parse(output.getvalue())
        self.assertEqual(duplicate.error["code"], "xlsx_duplicate_archive_entry")

    def test_unsupported_macro_extension_is_skipped(self):
        result = self.parse(make_minimal_xlsx(), filename="macro.xlsm")
        self.assertEqual(result.status, "skipped")


@unittest.skipUnless(importlib.util.find_spec("openpyxl"), "install optional openpyxl dependency")
class TestXlsxDocumentParserCapability(unittest.TestCase):
    def setUp(self):
        self.parser = XlsxDocumentParserCapability()

    def parse(self, content):
        return self.parser.execute(CapabilityContext(
            operation="parse",
            inputs={"content": content, "uri": "https://example.test/ledger.xlsx",
                    "filename": "ledger.xlsx"},
        ))

    def test_descriptor_source_hash_and_evidence_boundary(self):
        content = make_workbook()
        result = self.parse(content)
        self.assertEqual((self.parser.descriptor.name, self.parser.descriptor.kind), ("xlsx", "parser"))
        self.assertIn(result.status, ("succeeded", "partial"))
        self.assertEqual(result.metadata["document_sha256"], hashlib.sha256(content).hexdigest())
        self.assertTrue(all(r["record_type"] == "document_fragment" for r in result.records))
        self.assertFalse(result.metadata["evidence_promoted"])

    def test_sheet_visibility_merged_ranges_tables_and_defined_names(self):
        result = self.parse(make_workbook())
        sheet = next(r for r in result.records if r["fragment_type"] == "xlsx_worksheet")
        self.assertEqual(sheet["sheet_state"], "veryHidden")
        self.assertIn("E1:F1", sheet["merged_ranges"])
        self.assertEqual(sheet["tables"][0]["name"], "SalesTable")
        defined = next(r for r in result.records if r["fragment_type"] == "xlsx_defined_name")
        self.assertEqual(defined["defined_name"], "SalesTotal")

    def test_cell_locators_dates_and_formula_cache(self):
        content = with_cached_formula(make_workbook())
        result = self.parse(content)
        formula = next(r for r in result.records if r.get("formula"))
        self.assertEqual(formula["formula"], "=SUM(B2:B3)")
        self.assertEqual(formula["cached_value"], 30)
        self.assertEqual(formula["locator"]["scheme"], "xlsx-cell")
        self.assertEqual(formula["locator"]["coordinate"], "C2")
        date_cell = next(r for r in result.records if r["locator"].get("coordinate") == "D2")
        self.assertTrue(date_cell["cell_value"].startswith("2026-01-02"))

    def test_missing_formula_cache_is_explicit(self):
        result = self.parse(make_workbook())
        self.assertTrue(any(w["code"] == "xlsx_formula_cache_missing" for w in result.warnings))

    def test_formula_is_not_evaluated_or_promoted(self):
        result = self.parse(make_workbook())
        formula = next(r for r in result.records if r.get("formula"))
        self.assertEqual(formula["formula"], "=SUM(B2:B3)")
        self.assertIn("cached_value", formula)
        self.assertNotIn("evidence", formula)


if __name__ == "__main__":
    unittest.main()
