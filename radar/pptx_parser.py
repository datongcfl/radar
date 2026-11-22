"""Optional PPTX parser with bounded ZIP/XML preflight and native locators."""
from __future__ import annotations
import hashlib, io, re, zipfile, zlib
from typing import Any, Dict, List, Optional
from .capabilities import CapabilityContext, CapabilityDescriptor, CapabilityResult

class PptxDocumentParserCapability:
    def __init__(self, max_bytes=30*1024*1024, max_zip_entries=4096,
                 max_entry_bytes=30*1024*1024, max_total_uncompressed_bytes=150*1024*1024,
                 max_compression_ratio=200, max_xml_bytes=30*1024*1024,
                 max_slides=500, max_shapes=50000, max_cells=100000,
                 max_fragments=100000, max_characters=2000000):
        limits = locals().copy()
        limits.pop("self")
        for name, value in limits.items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError("%s must be a positive integer" % name)
        self.__dict__.update(limits)
        self._descriptor = CapabilityDescriptor(
            name="pptx", kind="parser", version="1.0.0",
            description="Optional PPTX slide, table, and speaker-notes parser")

    @property
    def descriptor(self):
        return self._descriptor

    def _preflight(self, content: bytes) -> Optional[str]:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                infos = archive.infolist()
                if len(infos) > self.max_zip_entries:
                    return "pptx_zip_entry_limit_exceeded"
                names, total, xml_total, slides = set(), 0, 0, 0
                for info in infos:
                    name = info.filename
                    normalized = name.replace("\\", "/")
                    if normalized.startswith("/") or "\\" in name or any(
                        p == ".." for p in normalized.split("/")
                    ):
                        return "pptx_unsafe_archive_path"
                    if name in names:
                        return "pptx_duplicate_archive_entry"
                    names.add(name)
                    if info.flag_bits & 1:
                        return "pptx_encrypted_archive_member"
                    if name.lower().endswith("/vbaproject.bin"):
                        return "pptx_macro_content_not_supported"
                    if re.fullmatch(r"ppt/slides/slide[0-9]+\.xml", name):
                        slides += 1
                    is_xml = name.lower().endswith(".xml") or name.lower().endswith(".rels")
                    chunks, actual = ([] if is_xml else None), 0
                    with archive.open(info, "r") as stream:
                        while True:
                            chunk = stream.read(65536)
                            if not chunk:
                                break
                            actual += len(chunk)
                            total += len(chunk)
                            if actual > self.max_entry_bytes:
                                return "pptx_zip_entry_too_large"
                            if total > self.max_total_uncompressed_bytes:
                                return "pptx_uncompressed_size_limit_exceeded"
                            if is_xml:
                                xml_total += len(chunk)
                                if xml_total > self.max_xml_bytes:
                                    return "pptx_xml_size_limit_exceeded"
                                chunks.append(chunk)
                    if actual != info.file_size:
                        return "pptx_archive_size_mismatch"
                    if actual and info.compress_size == 0:
                        return "pptx_invalid_compression_metadata"
                    if info.compress_size and actual / info.compress_size > self.max_compression_ratio:
                        return "pptx_compression_ratio_exceeded"
                    if is_xml:
                        upper = b"".join(chunks).upper()
                        if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
                            return "pptx_unsafe_xml_declaration"
                if "[Content_Types].xml" not in names or "ppt/presentation.xml" not in names:
                    return "invalid_pptx_package"
                if slides > self.max_slides:
                    return "pptx_slide_limit_exceeded"
        except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, RuntimeError,
                EOFError, ValueError, zlib.error, NotImplementedError):
            return "invalid_pptx_package"
        return None

    def execute(self, context: CapabilityContext) -> CapabilityResult:
        if context.operation != "parse":
            return CapabilityResult(status="failed", error={"code":"unsupported_operation"})
        content, uri = context.inputs.get("content"), context.inputs.get("uri")
        filename = context.inputs.get("filename", "")
        if not isinstance(content, (bytes, bytearray)):
            return CapabilityResult(status="failed", error={"code":"invalid_pptx_content"})
        content = bytes(content)
        if not isinstance(uri, str) or not uri.strip():
            return CapabilityResult(status="failed", error={"code":"missing_uri"})
        if not isinstance(filename, str):
            return CapabilityResult(status="failed", error={"code":"invalid_filename"})
        if filename and not filename.lower().endswith(".pptx"):
            return CapabilityResult(status="skipped", warnings=({"code":"unsupported_document_format"},))
        if len(content) > self.max_bytes:
            return CapabilityResult(status="failed", error={"code":"pptx_too_large","max_bytes":self.max_bytes})
        if not content.startswith(b"PK"):
            return CapabilityResult(status="failed", error={"code":"invalid_pptx_header"})
        preflight = self._preflight(content)
        if preflight:
            return CapabilityResult(status="failed", error={"code":preflight})
        try:
            from pptx import Presentation
        except ImportError as exc:
            return CapabilityResult(status="unavailable", warnings=({
                "code":"optional_dependency_missing",
                "dependency":getattr(exc, "name", None) or "python-pptx",
                "install_hint":"pip install --require-hashes -r requirements-pptx.txt"},))
        digest = hashlib.sha256(content).hexdigest()
        try:
            presentation = Presentation(io.BytesIO(content))
        except Exception as exc:
            return CapabilityResult(status="failed",
                error={"code":"pptx_parse_failed","exception_type":type(exc).__name__},
                metadata={"document_sha256":digest})
        records, warnings = [], []
        counters = {"shapes":0,"cells":0,"characters":0}
        stopped = False

        def append(kind, text, locator, fields=None):
            if len(records) >= self.max_fragments or counters["characters"] + len(text) > self.max_characters:
                return False
            counters["characters"] += len(text)
            item = {"record_type":"document_fragment","document_uri":uri,
                "document_sha256":digest,"document_format":"pptx","parser":"radar.pptx",
                "parser_version":self.descriptor.version,"fragment_index":len(records),
                "fragment_type":kind,"text":text,"heading_path":[],"locator":locator}
            if fields:
                item.update(fields)
            records.append(item)
            return True

        def visit_shape(shape, slide_index, shape_index, path):
            counters["shapes"] += 1
            if counters["shapes"] > self.max_shapes:
                return False
            base = {"slide_index":slide_index,"slide_number":slide_index+1,
                    "shape_index":shape_index,"shape_path":list(path),
                    "shape_type":str(getattr(shape,"shape_type","unknown"))}
            if getattr(shape,"has_table",False):
                table = shape.table
                for ri, row in enumerate(table.rows):
                    for ci, cell in enumerate(row.cells):
                        counters["cells"] += 1
                        if counters["cells"] > self.max_cells:
                            return False
                        value = cell.text.strip()
                        if value:
                            loc = dict(base, scheme="pptx-table-cell", row_index=ri, cell_index=ci)
                            if not append("pptx_table_cell", value, loc,
                                {"table_row_count":len(table.rows),"table_column_count":len(table.columns)}):
                                return False
            elif getattr(shape,"has_text_frame",False):
                for pi, paragraph in enumerate(shape.text_frame.paragraphs):
                    value = paragraph.text.strip()
                    if value:
                        loc = dict(base, scheme="pptx-text-paragraph", paragraph_index=pi)
                        if not append("pptx_text_paragraph", value, loc,
                                      {"paragraph_level":getattr(paragraph,"level",0)}):
                            return False
            if getattr(shape,"shape_type",None) == 6 and hasattr(shape,"shapes"):
                for ci, child in enumerate(shape.shapes):
                    if not visit_shape(child, slide_index, ci, list(path)+[ci]):
                        return False
            return True

        if not append("pptx_presentation", "Presentation with %d slide(s)" % len(presentation.slides),
                      {"scheme":"pptx-presentation"},{"slide_count":len(presentation.slides)}):
            stopped = True
        for si, slide in enumerate(presentation.slides):
            if stopped:
                break
            for shi, shape in enumerate(slide.shapes):
                if not visit_shape(shape, si, shi, [shi]):
                    warnings.append({"code":"pptx_shape_cell_or_fragment_limit_reached"})
                    stopped = True
                    break
            if stopped:
                break
            try:
                if slide.has_notes_slide:
                    frame = slide.notes_slide.notes_text_frame
                    note_text = frame.text.strip() if frame is not None else ""
                    if note_text and not append("pptx_speaker_notes", note_text,
                        {"scheme":"pptx-speaker-notes","slide_index":si,"slide_number":si+1}):
                        warnings.append({"code":"pptx_fragment_or_character_limit_reached"})
                        stopped = True
            except Exception:
                warnings.append({"code":"pptx_speaker_notes_unavailable","slide_index":si})
        if stopped and not warnings:
            warnings.append({"code":"pptx_fragment_or_character_limit_reached"})
        if not records:
            return CapabilityResult(status="skipped",
                warnings=tuple(warnings) or ({"code":"pptx_contains_no_extractable_text"},),
                metadata={"document_sha256":digest,"evidence_promoted":False})
        return CapabilityResult(status="partial" if warnings else "succeeded",
            records=tuple(records),warnings=tuple(warnings),
            metadata={"parser":"radar.pptx","parser_version":self.descriptor.version,
                "document_format":"pptx","document_sha256":digest,
                "slide_count":len(presentation.slides),"shape_count":counters["shapes"],
                "cell_count":counters["cells"],"fragment_count":len(records),
                "extracted_characters":counters["characters"],"evidence_promoted":False})
