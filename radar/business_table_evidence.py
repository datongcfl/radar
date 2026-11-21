"""Select table cells whose headers explicitly match Pack business fields."""
from __future__ import annotations

from typing import Any, Iterable
import re


def _norm(value: Any) -> str:
    return re.sub(r"[\W_]+", "", str(value or "").casefold(), flags=re.UNICODE)


def _group_key(locator: dict[str, Any]) -> tuple:
    if "cell" in locator:
        return ("xlsx", str(locator.get("path", "")), str(locator.get("sheet", "")))
    if "row" in locator and "column" in locator:
        return ("csv", str(locator.get("path", "")), "")
    return ("unsupported", str(locator.get("path", "")), "")


def _position(locator: dict[str, Any]) -> tuple[int, int]:
    if "cell" in locator:
        match = re.match(r"^([A-Z]+)([0-9]+)$", str(locator["cell"]).upper())
        if not match:
            return 0, 0
        column = 0
        for char in match.group(1):
            column = column * 26 + ord(char) - 64
        return int(match.group(2)), column
    try:
        return int(locator.get("row", 0)), int(locator.get("column", 0))
    except (TypeError, ValueError):
        return 0, 0


def select_required_table_chunks(invariants: Iterable[dict[str, Any]],
                                 chunks: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return header/data cells only for tables with an exact declared field mapping.

    The first populated row in each CSV file or XLSX worksheet is the header.
    Every selected cell is later given its own immutable Evidence record.
    """
    groups: dict[tuple, dict[int, dict[int, dict[str, Any]]]] = {}
    for chunk in chunks:
        locator = chunk.get("locator", {})
        if not isinstance(locator, dict):
            continue
        key = _group_key(locator)
        row, column = _position(locator)
        if key[0] == "unsupported" or row < 1 or column < 1:
            continue
        groups.setdefault(key, {}).setdefault(row, {})[column] = chunk

    selected: dict[tuple, dict[str, dict[str, Any]]] = {}
    for invariant in invariants:
        aliases = invariant.get("field_aliases")
        if not isinstance(aliases, dict):
            continue
        required = list(invariant.get("fields", []))
        target = invariant.get("target_field")
        if target and target not in required:
            required.append(target)
        if not required or invariant.get("operator") == "separate_fields":
            continue
        normalized: dict[str, str] = {}
        for field in required:
            values = aliases.get(field)
            if not isinstance(values, list) or not values:
                normalized = {}
                break
            for alias in values:
                key = _norm(alias)
                if not key or (key in normalized and normalized[key] != field):
                    normalized = {}
                    break
                normalized[key] = field
            if not normalized:
                break
        if not normalized:
            continue
        for table_key, table_rows in groups.items():
            header_row = min(table_rows)
            columns: dict[str, int] = {}
            for column, chunk in table_rows[header_row].items():
                field = normalized.get(_norm(chunk.get("text", "")))
                if field:
                    columns[field] = column
            if not set(required).issubset(columns):
                continue
            # Keep header cells so the downstream extractor can reconstruct the
            # same table schema from the selected, provenance-backed subset.
            for field in required:
                column = columns[field]
                header_chunk = table_rows[header_row][column]
                selected.setdefault((table_key, header_row, column), header_chunk)
            for row_number, cells in table_rows.items():
                if row_number == header_row:
                    continue
                # Select only fields needed by this invariant; do not collect unrelated cells.
                for field in required:
                    chunk = cells.get(columns[field])
                    if chunk is None or not str(chunk.get("text", "")).strip():
                        continue
                    locator = chunk.get("locator", {})
                    identity = (table_key, row_number, columns[field])
                    selected.setdefault(identity, chunk)
    return [selected[key] for key in sorted(selected, key=lambda item: (item[0], item[1], item[2]))]
