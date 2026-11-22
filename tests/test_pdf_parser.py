import hashlib
import importlib.util
import unittest

from radar.capabilities import CapabilityContext
from radar.pdf_parser import PdfDocumentParserCapability


def make_pdf(pages):
    """Build a tiny valid PDF fixture with one Helvetica text stream per page."""
    objects = {}
    page_ids = []
    for index, text in enumerate(pages):
        page_id = 3 + index * 2
        content_id = page_id + 1
        page_ids.append(page_id)
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = ("BT /F1 12 Tf 72 720 Td (%s) Tj ET" % escaped).encode("ascii")
        objects[page_id] = (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
            % (3 + len(pages) * 2, content_id)
        ).encode("ascii")
        objects[content_id] = (
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"
        )
    font_id = 3 + len(pages) * 2
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[2] = (
        "<< /Type /Pages /Kids [%s] /Count %d >>"
        % (" ".join("%d 0 R" % item for item in page_ids), len(page_ids))
    ).encode("ascii")
    objects[font_id] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0] * (font_id + 1)
    for object_id in range(1, font_id + 1):
        offsets[object_id] = len(output)
        output.extend(("%d 0 obj\n" % object_id).encode("ascii"))
        output.extend(objects[object_id])
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(("xref\n0 %d\n" % (font_id + 1)).encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(("%010d 00000 n \n" % offset).encode("ascii"))
    output.extend(
        ("trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF"
         % (font_id + 1, xref_offset)).encode("ascii")
    )
    return bytes(output)


@unittest.skipUnless(importlib.util.find_spec("pypdf"), "install requirements-pdf.txt")
class TestPdfDocumentParserCapability(unittest.TestCase):
    def setUp(self):
        self.parser = PdfDocumentParserCapability()

    def parse(self, content, filename="manual.pdf"):
        return self.parser.execute(CapabilityContext(
            operation="parse",
            inputs={"content": content, "uri": "https://example.test/" + filename,
                    "filename": filename},
        ))

    def test_descriptor_is_pdf_parser(self):
        descriptor = self.parser.descriptor
        self.assertEqual((descriptor.name, descriptor.kind, descriptor.version),
                         ("pdf", "parser", "1.0.0"))

    def test_extracts_page_text_with_exact_page_locator_and_hash(self):
        pdf = make_pdf(["Purchase order terms", "Delivery and acceptance"])
        result = self.parse(pdf)
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.metadata["page_count"], 2)
        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.records[0]["text"], "Purchase order terms")
        self.assertEqual(result.records[0]["locator"]["page_number"], 1)
        self.assertEqual(result.records[1]["locator"]["page_index"], 1)
        self.assertEqual(
            result.records[0]["document_sha256"],
            hashlib.sha256(pdf).hexdigest(),
        )
        self.assertEqual(
            result.records[0]["locator"]["page_text_sha256"],
            hashlib.sha256(result.records[0]["text"].encode("utf-8")).hexdigest(),
        )

    def test_empty_page_produces_partial_result_not_silent_success(self):
        result = self.parse(make_pdf(["Readable page", ""]))
        self.assertEqual(result.status, "partial")
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.warnings[0]["page_number"], 2)
        self.assertEqual(result.metadata["empty_page_count"], 1)

    def test_scanned_like_pdf_with_no_text_is_skipped(self):
        result = self.parse(make_pdf(["", ""]))
        self.assertEqual(result.status, "skipped")
        self.assertEqual(result.metadata["fragment_count"], 0)

    def test_page_limit_and_byte_limit_are_enforced(self):
        page_limited = PdfDocumentParserCapability(max_pages=1).execute(
            CapabilityContext(operation="parse", inputs={
                "content": make_pdf(["one", "two"]), "uri": "file:///x.pdf",
                "filename": "x.pdf",
            })
        )
        byte_limited = PdfDocumentParserCapability(max_bytes=10).execute(
            CapabilityContext(operation="parse", inputs={
                "content": make_pdf(["one"]), "uri": "file:///x.pdf",
                "filename": "x.pdf",
            })
        )
        self.assertEqual(page_limited.error["code"], "pdf_page_limit_exceeded")
        self.assertEqual(byte_limited.error["code"], "pdf_too_large")

    def test_invalid_input_and_header_fail_explicitly(self):
        invalid = self.parse(b"not a pdf")
        self.assertEqual(invalid.error["code"], "invalid_pdf_header")
        missing_uri = self.parser.execute(CapabilityContext(
            operation="parse", inputs={"content": make_pdf(["one"])}
        ))
        self.assertEqual(missing_uri.error["code"], "missing_uri")

    def test_encrypted_pdf_is_skipped(self):
        from pypdf import PdfReader, PdfWriter
        from io import BytesIO
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.encrypt("secret")
        stream = BytesIO()
        writer.write(stream)
        result = self.parse(stream.getvalue())
        self.assertEqual(result.status, "skipped")
        self.assertEqual(result.warnings[0]["code"], "encrypted_pdf_not_supported")

    def test_parser_does_not_promote_fragments_to_evidence(self):
        result = self.parse(make_pdf(["A clause."]))
        self.assertEqual(result.records[0]["record_type"], "document_fragment")
        self.assertFalse(result.metadata["evidence_promoted"])


if __name__ == "__main__":
    unittest.main()
