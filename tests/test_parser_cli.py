import builtins
import io
import json
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from radar.cli import main


class TestParserCli(unittest.TestCase):
    def invoke(self, args):
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(args)
        return code, json.loads(output.getvalue())

    def test_auto_detects_markdown_and_emits_fragments(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "guide.md"
            path.write_text("# Overview\n\nUseful text.\n", encoding="utf-8")
            code, result = self.invoke(["parse", "--file", str(path)])
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["parser"], "text")
        self.assertTrue(result["records"])
        self.assertTrue(all(r["record_type"] == "document_fragment" for r in result["records"]))
        self.assertFalse(result["metadata"]["evidence_promoted"])

    def test_auto_detects_docx_and_reports_missing_optional_dependency(self):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", b"<Types/>")
            archive.writestr("word/document.xml", b"<document/>")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "contract.docx"
            path.write_bytes(output.getvalue())
            original_import = builtins.__import__

            def block_docx(name, *args, **kwargs):
                if name == "docx":
                    raise ImportError("simulated missing dependency")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=block_docx):
                code, result = self.invoke(["parse", "--file", str(path)])
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["warnings"][0]["dependency"], "python-docx")

    def test_file_size_is_checked_before_reading(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "guide.txt"
            path.write_text("too large", encoding="utf-8")
            output = io.StringIO()
            with redirect_stderr(output):
                code = main(["parse", "--file", str(path), "--max-bytes", "2"])
        self.assertEqual(code, 1)
        self.assertIn("--max-bytes", output.getvalue())

    def test_missing_file_returns_cli_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.md"
            output = io.StringIO()
            with redirect_stderr(output):
                code = main(["parse", "--file", str(path)])
        self.assertEqual(code, 1)
        self.assertIn("input file does not exist", output.getvalue())


if __name__ == "__main__":
    unittest.main()
