import hashlib
import importlib.util
import io
import unittest
import zipfile

from radar.capabilities import CapabilityContext
from radar.docx_parser import DocxDocumentParserCapability


def make_docx():
    from docx import Document
    document = Document()
    document.add_heading("Purchase", level=1)
    document.add_paragraph("采购合同正文")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "物料"
    table.cell(0, 1).text = "数量"
    table.cell(1, 0).text = "钢材"
    table.cell(1, 1).text = "120"
    nested = table.cell(1, 0).add_table(rows=1, cols=1)
    nested.cell(0, 0).text = "嵌套说明"
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


@unittest.skipUnless(importlib.util.find_spec("docx"), "install optional python-docx dependency")
class TestDocxDocumentParserCapability(unittest.TestCase):
    def setUp(self):
        self.parser = DocxDocumentParserCapability()

    def parse(self, content, filename="contract.docx"):
        return self.parser.execute(CapabilityContext(
            operation="parse",
            inputs={
                "content": content,
                "uri": "https://example.test/" + filename,
                "filename": filename,
            },
        ))

    def test_descriptor_and_source_hash(self):
        content = make_docx()
        result = self.parse(content)
        self.assertEqual(
            (self.parser.descriptor.name, self.parser.descriptor.kind),
            ("docx", "parser"),
        )
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.metadata["document_sha256"], hashlib.sha256(content).hexdigest())

    def test_paragraph_heading_path_and_locator(self):
        result = self.parse(make_docx())
        paragraphs = [r for r in result.records if r["fragment_type"] == "docx_paragraph"]
        self.assertEqual(paragraphs[0]["text"], "Purchase")
        self.assertEqual(paragraphs[0]["heading_path"], ["Purchase"])
        self.assertEqual(paragraphs[1]["heading_path"], ["Purchase"])
        self.assertEqual(paragraphs[1]["locator"]["scheme"], "docx-paragraph")
        self.assertEqual(paragraphs[1]["locator"]["paragraph_index"], 1)

    def test_table_cells_and_nested_table_have_distinct_locators(self):
        result = self.parse(make_docx())
        cells = [r for r in result.records if r["fragment_type"] == "docx_table_cell"]
        texts = [r["text"] for r in cells]
        self.assertIn("钢材", texts)
        self.assertIn("120", texts)
        self.assertIn("嵌套说明", texts)
        nested = next(r for r in cells if r["text"] == "嵌套说明")
        self.assertEqual(len(nested["locator"]["table_path"]), 2)
        self.assertEqual(nested["locator"]["scheme"], "docx-table-cell")

    def test_parser_never_promotes_fragments_to_evidence(self):
        result = self.parse(make_docx())
        self.assertTrue(all(r["record_type"] == "document_fragment" for r in result.records))
        self.assertFalse(result.metadata["evidence_promoted"])

    def test_zip_limits_and_unsafe_xml_are_rejected(self):
        content = make_docx()
        limited = DocxDocumentParserCapability(max_bytes=20).execute(CapabilityContext(
            operation="parse",
            inputs={"content": content, "uri": "file:///x.docx", "filename": "x.docx"},
        ))
        self.assertEqual(limited.error["code"], "docx_too_large")

        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(content), "r") as source:
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
                for item in source.infolist():
                    data = source.read(item.filename)
                    if item.filename == "word/document.xml":
                        data = b'<!DOCTYPE x [<!ENTITY e "unsafe">]>' + data
                    target.writestr(item, data)
        unsafe = self.parse(output.getvalue())
        self.assertEqual(unsafe.error["code"], "docx_unsafe_xml_declaration")

    def test_invalid_input_is_explicit(self):
        invalid = self.parse(b"not a zip")
        self.assertEqual(invalid.error["code"], "invalid_docx_header")
        missing_uri = self.parser.execute(CapabilityContext(
            operation="parse", inputs={"content": make_docx()}
        ))
        self.assertEqual(missing_uri.error["code"], "missing_uri")


if __name__ == "__main__":
    unittest.main()
