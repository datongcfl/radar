import unittest
from io import BytesIO
from zipfile import ZipFile
from radar.document_parser import extract_csv_document, extract_office_document

def make_zip(files):
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()

class TestOfficeDocumentParser(unittest.TestCase):
    def test_docx_paragraph_and_table_cell_locators(self):
        data = make_zip({"word/document.xml":
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>Purchase Order approval</w:t></w:r></w:p>'
            '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Material receipt</w:t></w:r></w:p>'
            '</w:tc></w:tr></w:tbl></w:body></w:document>'})
        result = extract_office_document(data, "docx")
        self.assertEqual(result["status"], "parsed")
        self.assertEqual(result["chunks"][0]["locator"]["paragraph"], 1)
        self.assertEqual(result["chunks"][1]["locator"], {
            "table": 1, "row": 1, "column": 1, "block": "table_cell"})

    def test_xlsx_shared_and_inline_strings_keep_sheet_cell(self):
        data = make_zip({
            "xl/workbook.xml": '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="采购订单" sheetId="1" r:id="rId1"/></sheets></workbook>',
            "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
            "xl/sharedStrings.xml": '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>Purchase Order</t></si></sst>',
            "xl/worksheets/sheet1.xml": '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="inlineStr"><is><t>Approval</t></is></c></row></sheetData></worksheet>'})
        result = extract_office_document(data, "xlsx")
        self.assertEqual(result["status"], "parsed")
        self.assertEqual(result["chunks"][0]["locator"], {
            "sheet": "采购订单", "cell": "A1", "block": "cell"})
        self.assertEqual(result["chunks"][1]["text"], "Approval")

    def test_pptx_slide_and_paragraph_locators(self):
        data = make_zip({"ppt/slides/slide1.xml":
            '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>Procurement workflow</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>'})
        result = extract_office_document(data, "pptx")
        self.assertEqual(result["status"], "parsed")
        self.assertEqual(result["chunks"][0]["locator"], {
            "slide": 1, "paragraph": 1, "block": "slide_paragraph"})


    def test_csv_rows_keep_header_and_cell_coordinates(self):
        result = extract_csv_document("Item,Quantity,Unit" + chr(10) + "Cable,12,m" + chr(10) + "Switch,2,pcs" + chr(10))
        self.assertEqual(result["status"], "parsed")
        self.assertEqual(result["chunks"][3]["locator"], {
            "row": 2, "column": 1, "block": "cell", "header": "Item"})
        self.assertEqual(result["chunks"][4]["locator"]["header"], "Quantity")

    def test_pdf_and_legacy_office_are_explicitly_unsupported(self):
        self.assertEqual(extract_office_document(b"%PDF", "pdf")["status"], "unsupported")
        self.assertEqual(extract_office_document(b"binary", "doc")["status"], "unsupported")

    def test_corrupt_office_container_is_failed_not_empty_success(self):
        result = extract_office_document(b"not a zip", "docx")
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["reason"])

if __name__ == "__main__":
    unittest.main()
