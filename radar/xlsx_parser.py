"""Optional XLSX parser with bounded ZIP/XML preflight and native locators.

The capability emits document fragments only. It never calculates formulas,
executes macros, follows external links, or creates Evidence/Assessment records.
"""
from __future__ import annotations

import hashlib
import io
import zipfile
import zlib
import xml.etree.ElementTree as ET
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional

from .capabilities import CapabilityContext, CapabilityDescriptor, CapabilityResult
from .xml_safety import contains_forbidden_xml_declarations


class XlsxDocumentParserCapability:
    """Extract workbook, worksheet, and populated-cell observations."""

    def __init__(
        self,
        max_bytes: int = 20 * 1024 * 1024,
        max_zip_entries: int = 2048,
        max_entry_bytes: int = 20 * 1024 * 1024,
        max_total_uncompressed_bytes: int = 100 * 1024 * 1024,
        max_compression_ratio: int = 200,
        max_xml_bytes: int = 20 * 1024 * 1024,
        max_sheets: int = 200,
        max_cells: int = 100_000,
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
            "max_sheets": max_sheets,
            "max_cells": max_cells,
            "max_fragments": max_fragments,
            "max_characters": max_characters,
        }
        for name, value in limits.items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError("%s must be a positive integer" % name)
        self.__dict__.update(limits)
        self._descriptor = CapabilityDescriptor(
            name="xlsx",
            kind="parser",
            version="1.0.0",
            description="Optional XLSX workbook and cell parser",
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def _preflight(self, content: bytes) -> Optional[str]:
        """Validate and stream the archive before openpyxl sees untrusted XML."""
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                infos = archive.infolist()
                if len(infos) > self.max_zip_entries:
                    return "xlsx_zip_entry_limit_exceeded"
                total_actual = 0
                xml_actual = 0
                names = set()
                worksheet_xml = []
                workbook_xml = None
                for info in infos:
                    name = info.filename
                    normalized = name.replace("\\", "/")
                    if (
                        normalized.startswith("/")
                        or "\\" in name
                        or any(part == ".." for part in normalized.split("/"))
                    ):
                        return "xlsx_unsafe_archive_path"
                    if name in names:
                        return "xlsx_duplicate_archive_entry"
                    names.add(name)
                    if info.flag_bits & 0x1:
                        return "xlsx_encrypted_archive_member"
                    is_xml = name.lower().endswith(".xml") or name.lower().endswith(".rels")
                    chunks = [] if is_xml else None
                    entry_actual = 0
                    with archive.open(info, "r") as stream:
                        while True:
                            chunk = stream.read(64 * 1024)
                            if not chunk:
                                break
                            entry_actual += len(chunk)
                            total_actual += len(chunk)
                            if entry_actual > self.max_entry_bytes:
                                return "xlsx_zip_entry_too_large"
                            if total_actual > self.max_total_uncompressed_bytes:
                                return "xlsx_uncompressed_size_limit_exceeded"
                            if is_xml:
                                xml_actual += len(chunk)
                                if xml_actual > self.max_xml_bytes:
                                    return "xlsx_xml_size_limit_exceeded"
                                chunks.append(chunk)
                    if entry_actual != info.file_size:
                        return "xlsx_archive_size_mismatch"
                    if entry_actual and info.compress_size == 0:
                        return "xlsx_invalid_compression_metadata"
                    if info.compress_size and entry_actual / info.compress_size > self.max_compression_ratio:
                        return "xlsx_compression_ratio_exceeded"
                    if is_xml:
                        xml_bytes = b"".join(chunks)
                        if contains_forbidden_xml_declarations(xml_bytes):
                            return "xlsx_unsafe_xml_declaration"
                        if name == "xl/workbook.xml":
                            workbook_xml = xml_bytes
                        if name.startswith("xl/worksheets/") and name.lower().endswith(".xml"):
                            worksheet_xml.append(xml_bytes)

                if "[Content_Types].xml" not in names or workbook_xml is None:
                    return "invalid_xlsx_package"
                if "xl/vbaProject.bin" in names:
                    return "xlsx_macro_content_not_supported"

                try:
                    sheet_count = sum(
                        1 for _, element in ET.iterparse(
                            io.BytesIO(workbook_xml), events=("end",)
                        ) if element.tag.rsplit("}", 1)[-1] == "sheet"
                    )
                except ET.ParseError:
                    return "xlsx_invalid_xml"
                if sheet_count > self.max_sheets:
                    return "xlsx_sheet_limit_exceeded"

                cell_count = 0
                for xml_bytes in worksheet_xml:
                    try:
                        for _, element in ET.iterparse(io.BytesIO(xml_bytes), events=("end",)):
                            if element.tag.rsplit("}", 1)[-1] == "c":
                                cell_count += 1
                                if cell_count > self.max_cells:
                                    return "xlsx_cell_limit_exceeded"
                            element.clear()
                    except ET.ParseError:
                        return "xlsx_invalid_xml"
        except (
            zipfile.BadZipFile, zipfile.LargeZipFile, OSError, RuntimeError,
            EOFError, ValueError, zlib.error, NotImplementedError,
        ):
            return "invalid_xlsx_package"
        return None

    @staticmethod
    def _json_value(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (datetime, date, time)):
            return value.isoformat()
        if isinstance(value, timedelta):
            return str(value)
        formula_text = getattr(value, "text", None)
        if isinstance(formula_text, str):
            return formula_text
        return str(value)

    def execute(self, context: CapabilityContext) -> CapabilityResult:
        if context.operation != "parse":
            return CapabilityResult(status="failed", error={"code": "unsupported_operation"})
        content = context.inputs.get("content")
        uri = context.inputs.get("uri")
        filename = context.inputs.get("filename", "")
        if not isinstance(content, (bytes, bytearray)):
            return CapabilityResult(status="failed", error={"code": "invalid_xlsx_content"})
        content = bytes(content)
        if not isinstance(uri, str) or not uri.strip():
            return CapabilityResult(status="failed", error={"code": "missing_uri"})
        if not isinstance(filename, str):
            return CapabilityResult(status="failed", error={"code": "invalid_filename"})
        if filename and not filename.lower().endswith(".xlsx"):
            return CapabilityResult(
                status="skipped", warnings=({"code": "unsupported_document_format"},)
            )
        if len(content) > self.max_bytes:
            return CapabilityResult(
                status="failed", error={"code": "xlsx_too_large", "max_bytes": self.max_bytes}
            )
        if not content.startswith(b"PK"):
            return CapabilityResult(status="failed", error={"code": "invalid_xlsx_header"})

        preflight_error = self._preflight(content)
        if preflight_error:
            return CapabilityResult(status="failed", error={"code": preflight_error})

        try:
            import defusedxml.ElementTree  # noqa: F401 - openpyxl selects its safe XML backend
        except ImportError:
            return CapabilityResult(
                status="unavailable",
                warnings=({
                    "code": "optional_dependency_missing",
                    "dependency": "defusedxml",
                    "install_hint": "pip install --require-hashes -r requirements-xlsx.txt",
                },),
            )
        try:
            import openpyxl
        except ImportError:
            return CapabilityResult(
                status="unavailable",
                warnings=({
                    "code": "optional_dependency_missing",
                    "dependency": "openpyxl",
                    "install_hint": "pip install --require-hashes -r requirements-xlsx.txt",
                },),
            )

        digest = hashlib.sha256(content).hexdigest()
        try:
            workbook = openpyxl.load_workbook(
                io.BytesIO(content), read_only=False, data_only=False, keep_links=False
            )
            formula_count = sum(
                1 for ws in workbook.worksheets for cell in ws._cells.values()
                if getattr(cell, "data_type", None) == "f"
            )
            cached_workbook = None
            if formula_count:
                cached_workbook = openpyxl.load_workbook(
                    io.BytesIO(content), read_only=False, data_only=True, keep_links=False
                )
        except Exception as exc:
            return CapabilityResult(
                status="failed",
                error={"code": "xlsx_parse_failed", "exception_type": type(exc).__name__},
                metadata={"document_sha256": digest},
            )

        records: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []
        counters = {"cells": 0, "characters": 0, "formulas": 0, "missing_formula_cache": 0}
        stopped = False

        def append_fragment(fragment_type: str, text: str, locator: Dict[str, Any],
                            fields: Optional[Dict[str, Any]] = None) -> bool:
            if len(records) >= self.max_fragments:
                return False
            counters["characters"] += len(text)
            if counters["characters"] > self.max_characters:
                return False
            record = {
                "record_type": "document_fragment",
                "document_uri": uri,
                "document_sha256": digest,
                "document_format": "xlsx",
                "parser": "radar.xlsx",
                "parser_version": self.descriptor.version,
                "fragment_index": len(records),
                "fragment_type": fragment_type,
                "text": text,
                "heading_path": [],
                "locator": locator,
            }
            if fields:
                record.update(fields)
            records.append(record)
            return True

        try:
            active_sheet = workbook.index(workbook.active) if workbook.active else None
            if not append_fragment(
                "xlsx_workbook",
                "Workbook with %d worksheet(s)" % len(workbook.worksheets),
                {"scheme": "xlsx-workbook", "active_sheet_index": active_sheet},
                {"sheet_count": len(workbook.worksheets), "active_sheet_index": active_sheet},
            ):
                stopped = True

            for name, defined_name in workbook.defined_names.items():
                if stopped:
                    break
                target = getattr(defined_name, "attr_text", None)
                local_id = getattr(defined_name, "localSheetId", None)
                if not append_fragment(
                    "xlsx_defined_name", "%s: %s" % (name, target or ""),
                    {"scheme": "xlsx-defined-name", "name": name, "local_sheet_id": local_id},
                    {
                        "defined_name": name,
                        "target": target,
                        "hidden": bool(getattr(defined_name, "hidden", False)),
                    },
                ):
                    stopped = True
                    break

            for sheet_index, worksheet in enumerate(workbook.worksheets):
                if stopped:
                    break
                merged_ranges = sorted(str(item) for item in worksheet.merged_cells.ranges)
                table_refs = []
                for table_name in worksheet.tables.keys():
                    table = worksheet.tables[table_name]
                    table_refs.append({
                        "name": getattr(table, "displayName", table_name),
                        "ref": getattr(table, "ref", None),
                    })
                if not append_fragment(
                    "xlsx_worksheet",
                    "Worksheet %s (%s)" % (worksheet.title, worksheet.sheet_state),
                    {"scheme": "xlsx-worksheet", "sheet_index": sheet_index,
                     "sheet_name": worksheet.title},
                    {
                        "sheet_name": worksheet.title,
                        "sheet_state": worksheet.sheet_state,
                        "dimension": worksheet.calculate_dimension(),
                        "merged_ranges": merged_ranges,
                        "tables": table_refs,
                    },
                ):
                    stopped = True
                    break

                for cell in sorted(worksheet._cells.values(),
                                   key=lambda item: (item.row, item.column)):
                    if cell.value is None:
                        continue
                    counters["cells"] += 1
                    if counters["cells"] > self.max_cells:
                        warnings.append({"code": "xlsx_cell_limit_reached"})
                        stopped = True
                        break

                    is_formula = getattr(cell, "data_type", None) == "f"
                    raw_value = cell.value
                    formula = None
                    cached_value = None
                    if is_formula:
                        counters["formulas"] += 1
                        formula_obj_text = getattr(raw_value, "text", None)
                        formula = formula_obj_text if isinstance(formula_obj_text, str) else str(raw_value)
                        if cached_workbook is not None:
                            try:
                                cached_value = self._json_value(
                                    cached_workbook[worksheet.title][cell.coordinate].value
                                )
                            except Exception:
                                cached_value = None
                        if cached_value is None:
                            counters["missing_formula_cache"] += 1
                    value = self._json_value(raw_value)
                    if is_formula:
                        text = formula
                        if cached_value is not None:
                            text += "\nCached value: " + str(cached_value)
                    else:
                        text = str(value)
                    locator = {
                        "scheme": "xlsx-cell",
                        "sheet_index": sheet_index,
                        "sheet_name": worksheet.title,
                        "coordinate": cell.coordinate,
                        "row_index": cell.row - 1,
                        "column_index": cell.column - 1,
                    }
                    fields = {
                        "cell_value": None if is_formula else value,
                        "cell_data_type": cell.data_type,
                        "number_format": cell.number_format,
                        "style_id": cell.style_id,
                    }
                    if is_formula:
                        fields["formula"] = formula
                        fields["cached_value"] = cached_value
                    if not append_fragment("xlsx_cell", text, locator, fields):
                        warnings.append({"code": "xlsx_fragment_or_character_limit_reached"})
                        stopped = True
                        break
        except Exception as exc:
            return CapabilityResult(
                status="failed",
                error={"code": "xlsx_extraction_failed", "exception_type": type(exc).__name__},
                records=tuple(records),
                metadata={"document_sha256": digest, "fragment_count": len(records)},
            )

        if stopped and not warnings:
            warnings.append({"code": "xlsx_fragment_or_character_limit_reached"})
        if counters["missing_formula_cache"]:
            warnings.append({
                "code": "xlsx_formula_cache_missing",
                "count": counters["missing_formula_cache"],
            })
        if not records:
            return CapabilityResult(
                status="skipped",
                warnings=tuple(warnings) or ({"code": "xlsx_contains_no_extractable_content"},),
                metadata={"document_sha256": digest, "evidence_promoted": False},
            )
        return CapabilityResult(
            status="partial" if warnings else "succeeded",
            records=tuple(records),
            warnings=tuple(warnings),
            metadata={
                "parser": "radar.xlsx",
                "parser_version": self.descriptor.version,
                "document_format": "xlsx",
                "document_sha256": digest,
                "sheet_count": len(workbook.worksheets),
                "cell_count": counters["cells"],
                "formula_count": counters["formulas"],
                "missing_formula_cache_count": counters["missing_formula_cache"],
                "fragment_count": len(records),
                "extracted_characters": counters["characters"],
                "evidence_promoted": False,
            },
        )
