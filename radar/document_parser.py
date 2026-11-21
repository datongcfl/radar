"""Dependency-free extraction for common Office Open XML documents."""
from __future__ import annotations
from io import BytesIO
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree
import posixpath
import re

class DocumentParseError(ValueError):
    """The document container or its XML parts are invalid."""

def _xml(archive, name):
    try:
        return ElementTree.fromstring(archive.read(name))
    except (KeyError, ElementTree.ParseError) as exc:
        raise DocumentParseError("missing or invalid XML part: %s" % name) from exc

def _text(node):
    return " ".join("".join(node.itertext()).split())

def _docx(data):
    with ZipFile(BytesIO(data)) as archive:
        root = _xml(archive, "word/document.xml")
        ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        body = root.find(".//{%s}body" % ns)
        if body is None:
            return []
        chunks = []
        para_no = table_no = 0
        for child in list(body):
            if child.tag == "{%s}p" % ns:
                para_no += 1
                value = _text(child)
                if value:
                    chunks.append({"text": value, "locator": {"paragraph": para_no, "block": "paragraph"}})
            elif child.tag == "{%s}tbl" % ns:
                table_no += 1
                for row_no, row in enumerate(child.findall(".//{%s}tr" % ns), 1):
                    for col_no, cell in enumerate(row.findall("./{%s}tc" % ns), 1):
                        value = " ".join(_text(p) for p in cell.findall(".//{%s}p" % ns))
                        if value.strip():
                            chunks.append({"text": value.strip(), "locator": {
                                "table": table_no, "row": row_no, "column": col_no, "block": "table_cell"}})
        return chunks

def _xlsx(data):
    with ZipFile(BytesIO(data)) as archive:
        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
              "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
              "p": "http://schemas.openxmlformats.org/package/2006/relationships"}
        workbook = _xml(archive, "xl/workbook.xml")
        rels = _xml(archive, "xl/_rels/workbook.xml.rels")
        targets = {x.attrib.get("Id"): x.attrib.get("Target") for x in rels.findall("p:Relationship", ns)}
        shared = []
        try:
            shared_root = _xml(archive, "xl/sharedStrings.xml")
            shared = ["".join(x.itertext()) for x in shared_root.findall("m:si", ns)]
        except DocumentParseError:
            pass
        chunks = []
        for sheet in workbook.findall("m:sheets/m:sheet", ns):
            sheet_name = sheet.attrib.get("name", "Sheet")
            target = targets.get(sheet.attrib.get("{%s}id" % ns["r"]))
            if not target:
                continue
            path = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
            root = _xml(archive, path)
            for cell in root.findall(".//m:sheetData/m:row/m:c", ns):
                ref = cell.attrib.get("r", "")
                value_node, inline = cell.find("m:v", ns), cell.find("m:is", ns)
                value = ""
                if cell.attrib.get("t") == "s" and value_node is not None:
                    try:
                        value = shared[int(value_node.text)]
                    except (ValueError, IndexError, TypeError):
                        value = ""
                elif inline is not None:
                    value = "".join(inline.itertext())
                elif value_node is not None:
                    value = value_node.text or ""
                if value.strip():
                    chunks.append({"text": value.strip(), "locator": {
                        "sheet": sheet_name, "cell": ref, "block": "cell"}})
        return chunks

def _pptx(data):
    with ZipFile(BytesIO(data)) as archive:
        names = [n for n in archive.namelist() if re.fullmatch(r"ppt/slides/slide[0-9]+\.xml", n)]
        names.sort(key=lambda n: int(re.search(r"slide([0-9]+)", n).group(1)))
        ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
        chunks = []
        for slide_no, name in enumerate(names, 1):
            root = _xml(archive, name)
            for para_no, para in enumerate(root.findall(".//{%s}p" % ns), 1):
                value = _text(para)
                if value:
                    chunks.append({"text": value, "locator": {
                        "slide": slide_no, "paragraph": para_no, "block": "slide_paragraph"}})
        return chunks

def extract_office_document(data, extension):
    """Extract DOCX/XLSX/PPTX text chunks with native locators."""
    ext = extension.lower().lstrip(".")
    try:
        if ext == "docx":
            chunks = _docx(data)
        elif ext == "xlsx":
            chunks = _xlsx(data)
        elif ext == "pptx":
            chunks = _pptx(data)
        else:
            return {"status": "unsupported", "chunks": [], "reason": "format is not supported by the stdlib parser"}
    except (BadZipFile, OSError, DocumentParseError, ElementTree.ParseError) as exc:
        return {"status": "failed", "chunks": [], "reason": str(exc)[:240]}
    return {"status": "parsed", "chunks": chunks, "reason": None}
