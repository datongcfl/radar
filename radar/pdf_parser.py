"""Optional PDF text parser capability backed by pypdf.

The provider emits page-level parse fragments. It never creates Evidence or
Assessment records and does not claim OCR, table, or reading-order reconstruction.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Any, Dict, List, Optional

from .capabilities import CapabilityContext, CapabilityDescriptor, CapabilityResult


class PdfDocumentParserCapability:
    """Extract page-level text with source-native page locators."""

    def __init__(self, max_bytes: int = 25 * 1024 * 1024, max_pages: int = 500,
                 max_page_characters: int = 500_000):
        for name, value in (
            ("max_bytes", max_bytes),
            ("max_pages", max_pages),
            ("max_page_characters", max_page_characters),
        ):
            if not isinstance(value, int) or value < 1:
                raise ValueError("%s must be a positive integer" % name)
        self.max_bytes = max_bytes
        self.max_pages = max_pages
        self.max_page_characters = max_page_characters
        self._descriptor = CapabilityDescriptor(
            name="pdf",
            kind="parser",
            version="1.0.0",
            description="Optional page-level PDF text extraction using pypdf",
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def execute(self, context: CapabilityContext) -> CapabilityResult:
        if context.operation != "parse":
            return CapabilityResult(
                status="failed", error={"code": "unsupported_operation"}
            )
        content = context.inputs.get("content")
        uri = context.inputs.get("uri")
        filename = context.inputs.get("filename", "")
        if not isinstance(content, (bytes, bytearray)):
            return CapabilityResult(
                status="failed", error={"code": "invalid_pdf_content"}
            )
        content = bytes(content)
        if not isinstance(uri, str) or not uri.strip():
            return CapabilityResult(
                status="failed", error={"code": "missing_uri"}
            )
        if not isinstance(filename, str):
            return CapabilityResult(
                status="failed", error={"code": "invalid_filename"}
            )
        if filename and not filename.lower().endswith(".pdf"):
            return CapabilityResult(
                status="skipped",
                warnings=({"code": "unsupported_document_format"},),
            )
        if len(content) > self.max_bytes:
            return CapabilityResult(
                status="failed",
                error={"code": "pdf_too_large", "max_bytes": self.max_bytes},
            )
        if not content.startswith(b"%PDF-"):
            return CapabilityResult(
                status="failed", error={"code": "invalid_pdf_header"}
            )

        try:
            from pypdf import PdfReader
        except ImportError:
            return CapabilityResult(
                status="unavailable",
                warnings=({
                    "code": "optional_dependency_missing",
                    "dependency": "pypdf",
                    "install_hint": "pip install -r requirements-pdf.txt",
                },),
            )

        document_sha256 = hashlib.sha256(content).hexdigest()
        try:
            reader = PdfReader(BytesIO(content), strict=False)
            if reader.is_encrypted:
                return CapabilityResult(
                    status="skipped",
                    warnings=({"code": "encrypted_pdf_not_supported"},),
                    metadata={"document_sha256": document_sha256},
                )
            page_count = len(reader.pages)
            if page_count > self.max_pages:
                return CapabilityResult(
                    status="failed",
                    error={
                        "code": "pdf_page_limit_exceeded",
                        "page_count": page_count,
                        "max_pages": self.max_pages,
                    },
                    metadata={"document_sha256": document_sha256},
                )
        except Exception as exc:
            return CapabilityResult(
                status="failed",
                error={
                    "code": "pdf_read_failed",
                    "exception_type": type(exc).__name__,
                },
                metadata={"document_sha256": document_sha256},
            )

        records: List[Dict[str, Any]] = []
        warnings = []
        extraction_errors = 0
        empty_pages = 0
        for page_index, page in enumerate(reader.pages):
            try:
                text = page.extract_text()
            except Exception as exc:
                extraction_errors += 1
                warnings.append({
                    "code": "pdf_page_extraction_failed",
                    "page_number": page_index + 1,
                    "exception_type": type(exc).__name__,
                })
                continue
            if not isinstance(text, str) or not text.strip():
                empty_pages += 1
                warnings.append({
                    "code": "pdf_page_has_no_extractable_text",
                    "page_number": page_index + 1,
                })
                continue
            if len(text) > self.max_page_characters:
                extraction_errors += 1
                warnings.append({
                    "code": "pdf_page_character_limit_exceeded",
                    "page_number": page_index + 1,
                    "max_characters": self.max_page_characters,
                })
                continue

            page_text_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
            records.append({
                "record_type": "document_fragment",
                "document_uri": uri,
                "document_sha256": document_sha256,
                "document_format": "pdf",
                "fragment_index": len(records),
                "fragment_type": "pdf_page_text",
                "text": text,
                "heading_path": [],
                "locator": {
                    "scheme": "pdf-page",
                    "page_number": page_index + 1,
                    "page_index": page_index,
                    "char_start": 0,
                    "char_end": len(text),
                    "line_start": 1,
                    "line_end": len(text.splitlines()) or 1,
                    "page_text_sha256": page_text_sha256,
                },
            })

        metadata = {
            "parser": "radar.pdf",
            "parser_version": self.descriptor.version,
            "document_format": "pdf",
            "document_sha256": document_sha256,
            "page_count": page_count,
            "fragment_count": len(records),
            "empty_page_count": empty_pages,
            "page_error_count": extraction_errors,
            "evidence_promoted": False,
        }
        if not records and extraction_errors:
            return CapabilityResult(
                status="failed",
                error={"code": "pdf_text_extraction_failed"},
                warnings=tuple(warnings),
                metadata=metadata,
            )
        if not records:
            return CapabilityResult(
                status="skipped",
                warnings=tuple(warnings) or (
                    {"code": "pdf_contains_no_extractable_text"},
                ),
                metadata=metadata,
            )
        status = "partial" if warnings else "succeeded"
        return CapabilityResult(
            status=status,
            records=tuple(records),
            warnings=tuple(warnings),
            metadata=metadata,
        )
