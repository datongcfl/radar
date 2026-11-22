"""Optional DOCX parser with bounded ZIP/XML preflight and native locators.

This capability emits document fragments only. It does not create Evidence or
Assessment records and does not execute macros, fields, formulas, or links.
"""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
import zlib
from typing import Any, Dict, List, Optional, Tuple

from .capabilities import CapabilityContext, CapabilityDescriptor, CapabilityResult


class DocxParserError(ValueError):
    """Invalid DOCX package or unsupported parser operation."""


class DocxDocumentParserCapability:
    """Extract Word paragraphs and table cells with source-native locators."""

    def __init__(
        self,
        max_bytes: int = 20 * 1024 * 1024,
        max_zip_entries: int = 2048,
        max_entry_bytes: int = 20 * 1024 * 1024,
        max_total_uncompressed_bytes: int = 100 * 1024 * 1024,
        max_compression_ratio: int = 200,
        max_xml_bytes: int = 20 * 1024 * 1024,
        max_fragments: int = 100_000,
        max_characters: int = 2_000_000,
    ):
        limits = {
            "max_bytes": max_bytes,
            "max_zip_entries": max_zip_entries,
            "max_entry_bytes": max_entry_bytes,
            "max_total_uncompressed_bytes": max_total_uncompressed_bytes,
            "max_compression_ratio": max_compression_ratio,
            "max_xml_bytes": max_xml_bytes,
            "max_fragments": max_fragments,
            "max_characters": max_characters,
        }
        for name, value in limits.items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError("%s must be a positive integer" % name)
        self.__dict__.update(limits)
        self._descriptor = CapabilityDescriptor(
            name="docx",
            kind="parser",
            version="1.0.0",
            description="Optional DOCX paragraph and table-cell parser",
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def _preflight(self, content: bytes) -> Optional[str]:
        """Return a stable error code, or None when the package passes preflight."""
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                infos = archive.infolist()
                if len(infos) > self.max_zip_entries:
                    return "docx_zip_entry_limit_exceeded"
                total_size = 0
                xml_size = 0
                names = set()
                for info in infos:
                    name = info.filename
                    normalized = name.replace("\\", "/")
                    parts = normalized.split("/")
                    if (
                        normalized.startswith("/")
                        or "\\" in name
                        or any(part == ".." for part in parts)
                    ):
                        return "docx_unsafe_archive_path"
                    if name in names:
                        return "docx_duplicate_archive_entry"
                    names.add(name)
                    if info.file_size > self.max_entry_bytes:
                        return "docx_zip_entry_too_large"
                    total_size += info.file_size
                    if total_size > self.max_total_uncompressed_bytes:
                        return "docx_uncompressed_size_limit_exceeded"
                    if info.file_size and info.compress_size == 0:
                        return "docx_invalid_compression_metadata"
                    if info.compress_size:
                        ratio = info.file_size / info.compress_size
                        if ratio > self.max_compression_ratio:
                            return "docx_compression_ratio_exceeded"
                    if name.lower().endswith(".xml") or name.lower().endswith(".rels"):
                        xml_size += info.file_size
                        if xml_size > self.max_xml_bytes:
                            return "docx_xml_size_limit_exceeded"
                        raw = archive.read(info)
                        upper = raw.upper()
                        if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
                            return "docx_unsafe_xml_declaration"
                if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                    return "invalid_docx_package"
        except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, RuntimeError,
                EOFError, ValueError, zlib.error):
            return "invalid_docx_package"
        return None

    def execute(self, context: CapabilityContext) -> CapabilityResult:
        if context.operation != "parse":
            return CapabilityResult(status="failed", error={"code": "unsupported_operation"})
        content = context.inputs.get("content")
        uri = context.inputs.get("uri")
        filename = context.inputs.get("filename", "")
        if not isinstance(content, (bytes, bytearray)):
            return CapabilityResult(status="failed", error={"code": "invalid_docx_content"})
        content = bytes(content)
        if not isinstance(uri, str) or not uri.strip():
            return CapabilityResult(status="failed", error={"code": "missing_uri"})
        if not isinstance(filename, str):
            return CapabilityResult(status="failed", error={"code": "invalid_filename"})
        if filename and not filename.lower().endswith(".docx"):
            return CapabilityResult(
                status="skipped", warnings=({"code": "unsupported_document_format"},)
            )
        if len(content) > self.max_bytes:
            return CapabilityResult(
                status="failed",
                error={"code": "docx_too_large", "max_bytes": self.max_bytes},
            )
        if not content.startswith(b"PK"):
            return CapabilityResult(status="failed", error={"code": "invalid_docx_header"})

        preflight_error = self._preflight(content)
        if preflight_error:
            return CapabilityResult(status="failed", error={"code": preflight_error})

        try:
            from docx import Document
        except ImportError:
            return CapabilityResult(
                status="unavailable",
                warnings=({
                    "code": "optional_dependency_missing",
                    "dependency": "python-docx",
                    "install_hint": "Install the Radar DOCX optional dependency set.",
                },),
            )

        digest = hashlib.sha256(content).hexdigest()
        try:
            document = Document(io.BytesIO(content))
        except Exception as exc:
            return CapabilityResult(
                status="failed",
                error={"code": "docx_parse_failed", "exception_type": type(exc).__name__},
                metadata={"document_sha256": digest},
            )

        records: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []
        counters = {"paragraph": 0, "table": 0, "characters": 0}
        heading_stack: List[str] = []

        def append_fragment(
            fragment_type: str,
            text: str,
            locator: Dict[str, Any],
            heading_path: List[str],
            style_name: Optional[str] = None,
        ) -> bool:
            counters["characters"] += len(text)
            if counters["characters"] > self.max_characters:
                return False
            if len(records) >= self.max_fragments:
                return False
            record = {
                "record_type": "document_fragment",
                "document_uri": uri,
                "document_sha256": digest,
                "document_format": "docx",
                "parser": "radar.docx",
                "parser_version": self.descriptor.version,
                "fragment_index": len(records),
                "fragment_type": fragment_type,
                "text": text,
                "heading_path": list(heading_path),
                "locator": locator,
            }
            if style_name is not None:
                record["style_name"] = style_name
            records.append(record)
            return True

        def paragraph_heading(paragraph: Any) -> Optional[Tuple[int, str]]:
            style_name = getattr(getattr(paragraph, "style", None), "name", "") or ""
            match = re.match(r"^Heading\s+([1-9])$", style_name, re.IGNORECASE)
            if not match:
                return None
            return int(match.group(1)), paragraph.text.strip()

        def visit_table(table: Any, table_path: List[Dict[str, int]],
                        inherited_heading: List[str]) -> bool:
            table_index = counters["table"]
            counters["table"] += 1
            for row_index, row in enumerate(table.rows):
                seen_cells = set()
                for cell_index, cell in enumerate(row.cells):
                    tc_identity = id(cell._tc)
                    if tc_identity in seen_cells:
                        continue
                    seen_cells.add(tc_identity)
                    cell_text = "\n".join(
                        paragraph.text for paragraph in cell.paragraphs
                    ).strip()
                    try:
                        grid_span = int(cell._tc.grid_span)
                    except (AttributeError, TypeError, ValueError):
                        grid_span = 1
                    locator = {
                        "scheme": "docx-table-cell",
                        "table_index": table_index,
                        "table_path": list(table_path) + [{
                            "table_index": table_index,
                            "row_index": row_index,
                            "cell_index": cell_index,
                        }],
                        "row_index": row_index,
                        "cell_index": cell_index,
                        "grid_span": max(1, grid_span),
                        "paragraph_count": len(cell.paragraphs),
                    }
                    if not append_fragment(
                        "docx_table_cell", cell_text, locator, inherited_heading
                    ):
                        return False
                    for nested in cell.tables:
                        if not visit_table(
                            nested,
                            list(table_path) + [{
                                "table_index": table_index,
                                "row_index": row_index,
                                "cell_index": cell_index,
                            }],
                            inherited_heading,
                        ):
                            return False
            return True

        try:
            for body_order_index, block in enumerate(document.iter_inner_content()):
                if hasattr(block, "style") and hasattr(block, "text"):
                    paragraph_index = counters["paragraph"]
                    counters["paragraph"] += 1
                    text = block.text.strip()
                    style_name = getattr(getattr(block, "style", None), "name", "") or ""
                    heading = paragraph_heading(block)
                    if heading:
                        level, heading_text = heading
                        heading_stack = heading_stack[:level - 1]
                        if heading_text:
                            heading_stack.append(heading_text)
                    if text:
                        locator = {
                            "scheme": "docx-paragraph",
                            "body_order_index": body_order_index,
                            "paragraph_index": paragraph_index,
                        }
                        if not append_fragment(
                            "docx_paragraph", text, locator, heading_stack, style_name
                        ):
                            warnings.append({"code": "docx_fragment_limit_reached"})
                            break
                else:
                    if not visit_table(block, [], heading_stack):
                        warnings.append({"code": "docx_fragment_limit_reached"})
                        break
        except Exception as exc:
            return CapabilityResult(
                status="failed",
                error={"code": "docx_extraction_failed", "exception_type": type(exc).__name__},
                records=tuple(records),
                metadata={"document_sha256": digest, "fragment_count": len(records)},
            )

        if warnings:
            status = "partial"
        elif not records:
            status = "skipped"
            warnings.append({"code": "docx_contains_no_extractable_text"})
        else:
            status = "succeeded"
        return CapabilityResult(
            status=status,
            records=tuple(records),
            warnings=tuple(warnings),
            metadata={
                "parser": "radar.docx",
                "parser_version": self.descriptor.version,
                "document_format": "docx",
                "document_sha256": digest,
                "fragment_count": len(records),
                "paragraph_count": counters["paragraph"],
                "table_count": counters["table"],
                "extracted_characters": counters["characters"],
                "evidence_promoted": False,
            },
        )
