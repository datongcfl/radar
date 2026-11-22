"""Built-in text and Markdown parser capability with source-native locators.

This parser emits document fragments, not Evidence or Assessment decisions. The
caller must bind fragments to a validated Asset and apply Radar's Evidence policy.
"""
from __future__ import annotations

import hashlib
import mimetypes
import re
from typing import Any, Dict, List, Optional, Tuple

from .capabilities import (
    CapabilityContext,
    CapabilityDescriptor,
    CapabilityResult,
)

_MARKDOWN_EXTENSIONS = {".md", ".markdown", ".mdown", ".mkd"}
_SOURCE_EXTENSIONS = {
    ".py", ".pyi", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx",
    ".java", ".go", ".rs", ".c", ".h", ".cpp", ".hpp", ".cs",
    ".rb", ".php", ".sh", ".bash", ".zsh", ".sql", ".json",
    ".yaml", ".yml", ".toml", ".ini", ".xml", ".html", ".css",
}
_TEXT_EXTENSIONS = {".txt", ".text", ".rst", ".log", ".csv"}
_SUPPORTED_EXTENSIONS = (
    _MARKDOWN_EXTENSIONS | _SOURCE_EXTENSIONS | _TEXT_EXTENSIONS
)
_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
_LIST = re.compile(r"^\s*(?:[-+*]|\d+[.)])\s+")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


class DocumentParserError(ValueError):
    """Invalid parser input or unsupported parser operation."""


def _format_for(filename: str, media_type: str) -> Optional[str]:
    extension = ""
    if filename:
        dot = filename.rfind(".")
        if dot >= 0:
            extension = filename[dot:].lower()
    media = (media_type or "").split(";", 1)[0].strip().lower()
    if extension in _MARKDOWN_EXTENSIONS or media in (
        "text/markdown", "text/x-markdown"
    ):
        return "markdown"
    if extension in _SOURCE_EXTENSIONS or media.startswith(
        ("text/x-", "application/json", "application/yaml", "application/xml")
    ):
        return "source"
    if extension in _TEXT_EXTENSIONS or media.startswith("text/"):
        return "text"
    if not extension and not media:
        return "text"
    return None


def _split_blocks(content: str, document_format: str) -> List[Tuple[int, int, int, int, str, List[str]]]:
    """Return ordered (char start/end, line start/end, type, heading path) spans."""
    lines = content.splitlines(keepends=True)
    if not lines and content:
        lines = [content]
    blocks = []
    heading_stack = []
    active = None
    fence_char = None
    fence_size = 0

    def flush():
        nonlocal active
        if active is not None:
            start, end, first_line, last_line, kind = active
            if end > start:
                blocks.append((
                    start, end, first_line, last_line, kind,
                    list(heading_stack),
                ))
            active = None

    offset = 0
    for line_number, raw_line in enumerate(lines, 1):
        body = raw_line.rstrip("\r\n")
        stripped = body.strip()
        heading = _HEADING.match(body) if document_format == "markdown" and fence_char is None else None
        fence = _FENCE.match(body) if document_format == "markdown" else None

        if fence_char is not None:
            if active is None:
                active = [offset, offset, line_number, line_number, "code_fence"]
            active[1] = offset + len(body)
            active[3] = line_number
            closing = fence and fence.group(1)[0] == fence_char and len(fence.group(1)) >= fence_size
            if closing:
                flush()
                fence_char = None
                fence_size = 0
            offset += len(raw_line)
            continue

        if fence:
            flush()
            fence_char = fence.group(1)[0]
            fence_size = len(fence.group(1))
            active = [offset, offset + len(body), line_number, line_number, "code_fence"]
            offset += len(raw_line)
            continue

        if heading:
            flush()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            heading_stack = heading_stack[:level - 1]
            heading_stack.append(title)
            blocks.append((
                offset, offset + len(body), line_number, line_number,
                "heading", list(heading_stack),
            ))
            offset += len(raw_line)
            continue

        if not stripped:
            flush()
            offset += len(raw_line)
            continue

        if active is None:
            if document_format == "source":
                kind = "source_lines"
            elif body.lstrip().startswith(">"):
                kind = "blockquote"
            elif _LIST.match(body):
                kind = "list"
            else:
                kind = "paragraph"
            active = [offset, offset + len(body), line_number, line_number, kind]
        else:
            active[1] = offset + len(body)
            active[3] = line_number
        offset += len(raw_line)

    flush()
    return blocks


class TextDocumentParserCapability:
    """Parse Markdown, plain text, and source text without optional dependencies."""

    def __init__(self, max_characters: int = 2_000_000):
        if not isinstance(max_characters, int) or max_characters < 1:
            raise ValueError("max_characters must be a positive integer")
        self.max_characters = max_characters
        self._descriptor = CapabilityDescriptor(
            name="text",
            kind="parser",
            version="1.0.0",
            description="Built-in Markdown, plain-text, and source-text fragment parser",
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def execute(self, context: CapabilityContext) -> CapabilityResult:
        if context.operation != "parse":
            return CapabilityResult(
                status="failed",
                error={"code": "unsupported_operation"},
            )

        content = context.inputs.get("content")
        uri = context.inputs.get("uri")
        filename = context.inputs.get("filename", "")
        media_type = context.inputs.get("media_type", "")
        if not isinstance(content, str):
            return CapabilityResult(status="failed", error={"code": "invalid_content"})
        if not isinstance(uri, str) or not uri.strip():
            return CapabilityResult(status="failed", error={"code": "missing_uri"})
        if not isinstance(filename, str) or not isinstance(media_type, str):
            return CapabilityResult(status="failed", error={"code": "invalid_document_metadata"})
        if len(content) > self.max_characters:
            return CapabilityResult(
                status="failed",
                error={"code": "document_too_large", "max_characters": self.max_characters},
            )
        if "\x00" in content:
            return CapabilityResult(status="failed", error={"code": "binary_content_rejected"})

        document_format = _format_for(filename, media_type)
        if document_format is None:
            return CapabilityResult(
                status="skipped",
                warnings=({"code": "unsupported_document_format"},),
            )

        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        spans = _split_blocks(content, document_format)
        records = []
        byte_cursor = 0
        for index, span in enumerate(spans):
            char_start, char_end, line_start, line_end, fragment_type, heading_path = span
            byte_start = byte_cursor + len(content[byte_cursor * 0:char_start].encode("utf-8")) if False else len(content[:char_start].encode("utf-8"))
            byte_end = len(content[:char_end].encode("utf-8"))
            byte_cursor = byte_end
            fragment = content[char_start:char_end]
            records.append({
                "record_type": "document_fragment",
                "document_uri": uri,
                "document_sha256": digest,
                "document_format": document_format,
                "fragment_index": index,
                "fragment_type": fragment_type,
                "text": fragment,
                "heading_path": heading_path,
                "locator": {
                    "scheme": "text",
                    "line_start": line_start,
                    "line_end": line_end,
                    "char_start": char_start,
                    "char_end": char_end,
                    "byte_start": byte_start,
                    "byte_end": byte_end,
                    "fragment_index": index,
                },
            })

        return CapabilityResult(
            status="succeeded",
            records=tuple(records),
            metadata={
                "parser": "radar.text",
                "parser_version": self.descriptor.version,
                "document_format": document_format,
                "document_sha256": digest,
                "fragment_count": len(records),
                "evidence_promoted": False,
            },
        )
