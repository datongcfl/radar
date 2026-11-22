import hashlib
import unittest

from radar.capabilities import CapabilityContext
from radar.document_parser import TextDocumentParserCapability


class TestTextDocumentParserCapability(unittest.TestCase):
    def setUp(self):
        self.parser = TextDocumentParserCapability()

    def parse(self, content, filename="guide.md", media_type=""):
        return self.parser.execute(CapabilityContext(
            operation="parse",
            inputs={"content": content, "uri": "https://example.test/" + filename,
                    "filename": filename, "media_type": media_type},
        ))

    def test_descriptor_is_parser_capability(self):
        descriptor = self.parser.descriptor
        self.assertEqual((descriptor.name, descriptor.kind, descriptor.version),
                         ("text", "parser", "1.0.0"))

    def test_markdown_fragments_preserve_heading_path_and_line_locator(self):
        content = "# Overview\n\nIntro paragraph.\n\n## Design\n\n- First\n- Second\n"
        result = self.parse(content)
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.metadata["document_format"], "markdown")
        self.assertEqual(result.metadata["fragment_count"], 4)
        design = result.records[2]
        self.assertEqual(design["fragment_type"], "heading")
        self.assertEqual(design["heading_path"], ["Overview", "Design"])
        self.assertEqual(design["locator"]["line_start"], 5)
        self.assertEqual(result.records[3]["fragment_type"], "list")
        self.assertEqual(result.records[3]["locator"]["line_start"], 7)
        self.assertEqual(result.records[3]["locator"]["line_end"], 8)

    def test_fenced_code_is_one_fragment_and_does_not_change_heading_path(self):
        content = "# API\n\n```python\ndef run():\n    return 1\n```\n"
        result = self.parse(content)
        code = result.records[1]
        self.assertEqual(code["fragment_type"], "code_fence")
        self.assertIn("def run()", code["text"])
        self.assertEqual(code["heading_path"], ["API"])
        self.assertEqual(code["locator"]["line_start"], 3)
        self.assertEqual(code["locator"]["line_end"], 6)

    def test_utf8_byte_offsets_are_exact(self):
        content = "# 标题\n\n内容"
        result = self.parse(content)
        fragment = result.records[1]
        self.assertEqual(fragment["locator"]["char_start"], 6)
        self.assertEqual(fragment["locator"]["byte_start"], len("# 标题\n\n".encode("utf-8")))
        self.assertEqual(fragment["locator"]["byte_end"], len(content.encode("utf-8")))

    def test_document_hash_is_stable_sha256(self):
        content = "hello"
        result = self.parse(content, filename="notes.txt")
        self.assertEqual(result.metadata["document_sha256"],
                         hashlib.sha256(content.encode("utf-8")).hexdigest())

    def test_source_files_use_source_line_fragments(self):
        result = self.parse("def a():\n    pass\n\nclass B:\n    pass\n",
                            filename="module.py")
        self.assertEqual(result.records[0]["fragment_type"], "source_lines")
        self.assertEqual(result.records[1]["locator"]["line_start"], 4)

    def test_plain_text_is_split_into_paragraphs(self):
        result = self.parse("one\nline\n\ntwo", filename="notes.txt")
        self.assertEqual([x["text"] for x in result.records], ["one\nline", "two"])

    def test_unsupported_binary_format_is_skipped(self):
        result = self.parse("opaque", filename="scan.pdf", media_type="application/pdf")
        self.assertEqual(result.status, "skipped")
        self.assertEqual(result.warnings[0]["code"], "unsupported_document_format")

    def test_binary_null_bytes_are_rejected(self):
        result = self.parse("abc\x00def", filename="notes.txt")
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error["code"], "binary_content_rejected")

    def test_size_limit_is_enforced(self):
        parser = TextDocumentParserCapability(max_characters=3)
        result = parser.execute(CapabilityContext(
            operation="parse",
            inputs={"content": "four", "uri": "file:///four.txt", "filename": "four.txt"},
        ))
        self.assertEqual(result.error["code"], "document_too_large")

    def test_missing_uri_and_unsupported_operation_fail_explicitly(self):
        missing = self.parser.execute(CapabilityContext(
            operation="parse", inputs={"content": "x", "filename": "x.txt"}
        ))
        wrong_op = self.parser.execute(CapabilityContext(
            operation="discover", inputs={"content": "x", "uri": "file:///x.txt",
                                          "filename": "x.txt"}
        ))
        self.assertEqual(missing.error["code"], "missing_uri")
        self.assertEqual(wrong_op.error["code"], "unsupported_operation")

    def test_result_is_not_promoted_to_evidence(self):
        result = self.parse("A statement.", filename="notes.txt")
        self.assertFalse(result.metadata["evidence_promoted"])
        self.assertEqual(result.records[0]["record_type"], "document_fragment")


if __name__ == "__main__":
    unittest.main()
