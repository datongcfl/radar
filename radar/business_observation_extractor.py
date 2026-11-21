"""Conservative extraction of provenance-backed observations from CSV/XLSX tables.

Only explicit Pack header aliases are used. This module does not infer business
meaning from free text, aggregate across rows, or invent missing Evidence.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from hashlib import sha256
import re
from typing import Any, Iterable


class ObservationExtractionError(ValueError):
    """Raised when tabular inputs or Pack aliases are ambiguous."""


def _normalize_header(value: Any) -> str:
    return re.sub(r"[\W_]+", "", str(value or "").casefold(), flags=re.UNICODE)


def _column_number(reference: str) -> int:
    match = re.match(r"^([A-Z]+)", str(reference or "").upper())
    if not match:
        return 0
    number = 0
    for char in match.group(1):
        number = number * 26 + ord(char) - 64
    return number


def _cell_identity(locator: dict[str, Any]) -> tuple:
    if "cell" in locator:
        return ("xlsx", str(locator.get("path", "")), str(locator.get("sheet", "")),
                str(locator.get("cell", "")).upper())
    return ("csv", str(locator.get("path", "")),
            int(locator.get("row", 0)), int(locator.get("column", 0)))


def _numeric(value: Any, field: str):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ObservationExtractionError("%s is not a numeric table value" % field)
    try:
        number = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        raise ObservationExtractionError("%s is not a numeric table value" % field)
    if not number.is_finite():
        raise ObservationExtractionError("%s is not finite" % field)
    return str(number)


def extract_table_observations(invariants: Iterable[dict[str, Any]],
                               chunks: Iterable[dict[str, Any]],
                               evidence_records: Iterable[dict[str, Any]],
                               asset_id: str,
                               origin: str = "static_source") -> dict[str, Any]:
    """Build row-scoped observations only where every field has a cell Evidence.

    Supported locators are CSV row/column and XLSX sheet/cell. The first row
    within each CSV file or worksheet is treated as the header row.
    """
    if origin not in ("static_source", "test", "manual", "runtime"):
        raise ObservationExtractionError("unsupported observation origin")
    rows = list(chunks)
    evidence = list(evidence_records)
    evidence_by_cell = {}
    for item in evidence:
        locator = item.get("locator", {})
        if item.get("asset_id") == asset_id:
            evidence_by_cell[_cell_identity(locator)] = item
    observations = []
    skipped = []
    for invariant in invariants:
        aliases = invariant.get("field_aliases")
        if not isinstance(aliases, dict):
            continue
        fields = list(invariant.get("fields", []))
        target = invariant.get("target_field")
        required = list(fields)
        if target and target not in required:
            required.append(target)
        if invariant.get("operator") in ("less_than_or_equal", "equal_with_tolerance"):
            pass
        if invariant.get("operator") == "separate_fields":
            # Table values cannot prove code/schema field identity.
            continue
        alias_to_field = {}
        ambiguous = False
        for field in required:
            field_aliases = aliases.get(field, [])
            if not isinstance(field_aliases, list) or not field_aliases:
                ambiguous = True
                break
            for alias in field_aliases:
                key = _normalize_header(alias)
                if not key or (key in alias_to_field and alias_to_field[key] != field):
                    ambiguous = True
                    break
                alias_to_field[key] = field
            if ambiguous:
                break
        if ambiguous:
            skipped.append({"invariant_id": invariant.get("id"), "reason": "missing_or_ambiguous_field_aliases"})
            continue

        groups = {}
        for chunk in rows:
            locator = chunk.get("locator", {})
            if not isinstance(locator, dict):
                continue
            if "cell" in locator:
                sheet = str(locator.get("sheet", ""))
                column = _column_number(locator["cell"])
                row_number_match = re.search(r"([0-9]+)$", str(locator["cell"]))
                row_number = int(row_number_match.group(1)) if row_number_match else 0
                key = ("xlsx", str(locator.get("path", "")), sheet)
            elif "row" in locator and "column" in locator:
                row_number, column = int(locator["row"]), int(locator["column"])
                key = ("csv", str(locator.get("path", "")), "")
            else:
                continue
            if row_number < 1 or column < 1:
                continue
            groups.setdefault(key, {}).setdefault(row_number, {})[column] = chunk

        for table_key, table_rows in sorted(groups.items()):
            header_row = min(table_rows)
            header_map = {}
            for column, chunk in table_rows[header_row].items():
                field = alias_to_field.get(_normalize_header(chunk.get("text", "")))
                if field:
                    header_map[field] = column
            if not set(required).issubset(header_map):
                continue
            for row_number, cells in sorted(table_rows.items()):
                if row_number == header_row:
                    continue
                values, provenance = {}, {}
                missing = False
                for field in required:
                    chunk = cells.get(header_map[field])
                    if chunk is None:
                        missing = True
                        break
                    locator = dict(chunk.get("locator", {}))
                    locator.setdefault("path", table_key[1])
                    evidence_item = evidence_by_cell.get(_cell_identity(locator))
                    if evidence_item is None:
                        missing = True
                        break
                    try:
                        values[field] = _numeric(chunk.get("text", ""), field)
                    except ObservationExtractionError:
                        missing = True
                        break
                    provenance[field] = {
                        "evidence_id": evidence_item["id"],
                        "locator": locator,
                        "verification_level": (evidence_item.get("metadata") or {}).get(
                            "verification", {}).get("level", "document_text"),
                        "runtime_observed": False,
                    }
                if missing:
                    skipped.append({"invariant_id": invariant.get("id"),
                                    "scope_key": "%s:%s" % (table_key, row_number),
                                    "reason": "incomplete_row_or_missing_cell_evidence"})
                    continue
                scope_key = "%s:%s" % (table_key, row_number)
                observation_id = "obs_" + sha256(
                    (asset_id + "|" + invariant["id"] + "|" + scope_key).encode("utf-8")
                ).hexdigest()[:20]
                observations.append({
                    "id": observation_id, "invariant_id": invariant["id"],
                    "scope_key": scope_key, "origin": origin,
                    "values": values, "field_provenance": provenance,
                    "captured_at": None,
                })
    observations.sort(key=lambda item: (item["invariant_id"], item["scope_key"]))
    return {"schema_version": 1, "observations": observations,
            "skipped": skipped, "summary": {
                "observations": len(observations),
                "skipped_rows": len(skipped),
                "invariants_with_aliases": len(set(item["invariant_id"] for item in observations)),
            }}
