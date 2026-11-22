"""Explicit, provenance-preserving CSV/XLSX source adapter for stock and GL ledgers."""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO, StringIO
import json
import re
import unicodedata
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from typing import Any

from .discovery import new_record
from .discovery_store import JsonWorkspaceStore
from .document_parser import extract_office_document
from .ledger_effects import LedgerEffectError, validate_ledger_effects
from .ledger_workspace import import_ledger_bundle


class LedgerSourceAdapterError(ValueError):
    pass


COMMON = {
    "ledger_entry_id", "company_id", "voucher_type", "voucher_id",
    "voucher_item_id", "event_kind", "posting_status", "currency", "accounting_period",
}
OPTIONAL = {"posting_date", "period_start_date", "period_end_date", "reversal_of", "valuation_method"}
STOCK = {"item_id", "warehouse_id", "quantity_delta", "quantity_uom", "stock_value_delta"}
GL = {"account_id", "debit_amount", "credit_amount"}
ALL_FIELDS = COMMON | OPTIONAL | STOCK | GL


def _norm(value: Any) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[\s_\-]+", "", value)


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LedgerSourceAdapterError("%s must be a non-empty string" % field)
    return value.strip()


def validate_ledger_source_adapter(config: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise LedgerSourceAdapterError("adapter config must be an object")
    for key in ("id", "source_system", "format", "ledger_kind", "header_row",
                "field_map", "number_format"):
        if key not in config:
            raise LedgerSourceAdapterError("adapter config missing %s" % key)
    _required_text(config["id"], "id")
    _required_text(config["source_system"], "source_system")
    if config["format"] not in ("csv", "xlsx"):
        raise LedgerSourceAdapterError("format must be csv or xlsx")
    if config["ledger_kind"] not in ("stock", "general_ledger"):
        raise LedgerSourceAdapterError("ledger_kind must be stock or general_ledger")
    if isinstance(config["header_row"], bool) or not isinstance(config["header_row"], int) or config["header_row"] < 1:
        raise LedgerSourceAdapterError("header_row must be a positive 1-based row")
    if config["format"] == "csv":
        if not isinstance(config.get("delimiter"), str) or len(config["delimiter"]) != 1:
            raise LedgerSourceAdapterError("CSV mapping requires a one-character delimiter")
    elif not isinstance(config.get("sheet_name"), str) or not config["sheet_name"].strip():
        raise LedgerSourceAdapterError("XLSX mapping requires an exact sheet_name")

    field_map = config["field_map"]
    constants = config.get("constants", {})
    if not isinstance(field_map, dict) or not isinstance(constants, dict):
        raise LedgerSourceAdapterError("field_map and constants must be objects")
    allowed = ALL_FIELDS
    for field, aliases in field_map.items():
        if field not in allowed:
            raise LedgerSourceAdapterError("unsupported mapped field: %s" % field)
        aliases = [aliases] if isinstance(aliases, str) else aliases
        if not isinstance(aliases, list) or not aliases or any(
                not isinstance(item, str) or not item.strip() for item in aliases):
            raise LedgerSourceAdapterError("field_map.%s must be a header or non-empty header list" % field)
    for field, value in constants.items():
        if field not in allowed or field in field_map:
            raise LedgerSourceAdapterError("invalid or duplicate constant field: %s" % field)
        if isinstance(value, bool) or not isinstance(value, (str, int, float)) or not str(value).strip():
            raise LedgerSourceAdapterError("constants.%s must be a non-empty scalar" % field)

    required = COMMON | (STOCK if config["ledger_kind"] == "stock" else GL)
    missing = sorted(required - (set(field_map) | set(constants)))
    if missing:
        raise LedgerSourceAdapterError("mapping missing required fields: %s" % ", ".join(missing))
    optional_fields = config.get("optional_fields", [])
    if not isinstance(optional_fields, list) or any(field not in OPTIONAL for field in optional_fields):
        raise LedgerSourceAdapterError("optional_fields contains unsupported values")

    number_format = config["number_format"]
    if not isinstance(number_format, dict):
        raise LedgerSourceAdapterError("number_format must be an object")
    decimal_sep = number_format.get("decimal_separator")
    thousands_sep = number_format.get("thousands_separator")
    if not isinstance(decimal_sep, str) or len(decimal_sep) != 1:
        raise LedgerSourceAdapterError("decimal_separator must be one character")
    if not isinstance(thousands_sep, str) or len(thousands_sep) > 1 or thousands_sep == decimal_sep:
        raise LedgerSourceAdapterError("thousands_separator must be empty or a different single character")
    value_maps = config.get("value_maps", {})
    if not isinstance(value_maps, dict):
        raise LedgerSourceAdapterError("value_maps must be an object")
    for field, mapping in value_maps.items():
        if field not in allowed or not isinstance(mapping, dict) or not mapping:
            raise LedgerSourceAdapterError("invalid value map for %s" % field)
        if any(not isinstance(k, str) or not isinstance(v, str) or not v.strip()
               for k, v in mapping.items()):
            raise LedgerSourceAdapterError("value map keys/values must be non-empty strings")
    return config


def _csv_rows(data: bytes, config: dict[str, Any]):
    try:
        text = data.decode(config.get("encoding", "utf-8-sig"))
        rows = list(csv.reader(StringIO(text), delimiter=config["delimiter"]))
    except (UnicodeError, LookupError, csv.Error) as exc:
        raise LedgerSourceAdapterError("CSV could not be parsed: %s" % exc)
    header_index = config["header_row"] - 1
    if header_index >= len(rows) or not rows[header_index]:
        raise LedgerSourceAdapterError("CSV header row is missing")
    return rows[header_index], [(i + 1, row) for i, row in enumerate(rows) if i > header_index], None


def _col_number(letters: str) -> int:
    number = 0
    for char in letters.upper():
        if not ("A" <= char <= "Z"):
            raise LedgerSourceAdapterError("invalid XLSX column reference")
        number = number * 26 + ord(char) - 64
    return number


def _xlsx_rows(data: bytes, config: dict[str, Any]):
    try:
        with ZipFile(BytesIO(data)) as archive:
            infos = archive.infolist()
            if sum(info.file_size for info in infos) > int(config.get("max_uncompressed_bytes", 200 * 1024 * 1024)):
                raise LedgerSourceAdapterError("XLSX uncompressed size exceeds limit")
            if any(info.compress_size and info.file_size / info.compress_size >
                   int(config.get("max_compression_ratio", 1000)) for info in infos):
                raise LedgerSourceAdapterError("XLSX compression ratio exceeds limit")
    except BadZipFile as exc:
        raise LedgerSourceAdapterError("invalid XLSX container: %s" % exc)
    parsed = extract_office_document(data, "xlsx")
    if parsed.get("status") != "parsed":
        raise LedgerSourceAdapterError("XLSX parse failed: %s" % parsed.get("reason"))
    sheet = config["sheet_name"]
    cells = {}
    found = False
    for chunk in parsed["chunks"]:
        locator = chunk.get("locator", {})
        if locator.get("sheet") != sheet:
            continue
        found = True
        match = re.fullmatch(r"([A-Za-z]+)([0-9]+)", str(locator.get("cell", "")))
        if match:
            cells.setdefault(int(match.group(2)), {})[_col_number(match.group(1))] = str(chunk.get("text", ""))
    if not found:
        raise LedgerSourceAdapterError("XLSX sheet not found: %s" % sheet)
    header_cells = cells.get(config["header_row"], {})
    if not header_cells:
        raise LedgerSourceAdapterError("XLSX header row is empty")
    width = max(header_cells)
    headers = [header_cells.get(i, "") for i in range(1, width + 1)]
    rows = []
    for row_num, row_cells in sorted(cells.items()):
        if row_num > config["header_row"]:
            row_width = max(width, max(row_cells) if row_cells else 0)
            rows.append((row_num, [row_cells.get(i, "") for i in range(1, row_width + 1)]))
    return headers, rows, sheet


def _resolve_columns(headers: list[str], config: dict[str, Any]) -> dict[str, int]:
    available = {}
    for index, header in enumerate(headers, 1):
        if _norm(header):
            available.setdefault(_norm(header), []).append(index)
    resolved, claimed = {}, {}
    for field, aliases in config["field_map"].items():
        aliases = [aliases] if isinstance(aliases, str) else aliases
        matches = sorted({column for alias in aliases for column in available.get(_norm(alias), [])})
        if len(matches) > 1:
            raise LedgerSourceAdapterError("ambiguous source headers for %s: %s" % (field, matches))
        if not matches:
            if field not in config.get("optional_fields", []):
                raise LedgerSourceAdapterError("source header missing field: %s" % field)
            continue
        column = matches[0]
        if column in claimed:
            raise LedgerSourceAdapterError("one source column maps to both %s and %s" % (claimed[column], field))
        claimed[column] = field
        resolved[field] = column
    return resolved


def _decimal(value: Any, config: dict[str, Any], field: str) -> str:
    if value is None or isinstance(value, bool) or not str(value).strip():
        raise LedgerSourceAdapterError("%s is empty or invalid" % field)
    text = str(value).strip()
    fmt = config["number_format"]
    if text.startswith("(") and text.endswith(")"):
        if not fmt.get("negative_parentheses", False):
            raise LedgerSourceAdapterError("%s uses undeclared negative-parentheses format" % field)
        text = "-" + text[1:-1].strip()
    if fmt["thousands_separator"]:
        text = text.replace(fmt["thousands_separator"], "")
    if fmt["decimal_separator"] != ".":
        text = text.replace(fmt["decimal_separator"], ".")
    try:
        parsed = Decimal(text)
    except InvalidOperation:
        raise LedgerSourceAdapterError("%s is not a valid decimal" % field)
    if not parsed.is_finite():
        raise LedgerSourceAdapterError("%s must be finite" % field)
    return str(parsed)


def _date(value: Any, config: dict[str, Any], field: str) -> str:
    text = str(value or "").strip()
    try:
        parsed = datetime.strptime(text, config["date_format"]).date() if config.get("date_format") else date.fromisoformat(text)
    except ValueError:
        raise LedgerSourceAdapterError("%s does not match declared date format" % field)
    return parsed.isoformat()


def _map_field(field: str, value: Any, config: dict[str, Any]) -> str:
    text = str(value or "").strip()
    if not text:
        raise LedgerSourceAdapterError("%s is empty" % field)
    mapping = config.get("value_maps", {}).get(field)
    if mapping is None:
        return text
    normalized = {_norm(key): value for key, value in mapping.items()}
    if _norm(text) not in normalized:
        raise LedgerSourceAdapterError("%s has no declared mapping for %s" % (field, text))
    return normalized[_norm(text)]


def _signature(effect: dict[str, Any]) -> str:
    return json.dumps({k: v for k, v in effect.items()
                       if k not in ("asset_id", "evidence_id", "locator")},
                      ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _get_asset(store: JsonWorkspaceStore, path_name: str, data: bytes,
               fmt: str, adapter_id: str):
    digest = sha256(data).hexdigest()
    uri = "file+sha256://%s/%s" % (digest, path_name)
    source = next((r for r in store.list_records("source") if r.get("uri") == uri), None)
    if source is None:
        source = new_record("source", workspace_id=store.workspace_id,
            provider="filesystem", uri=uri, name=path_name, access_status="unknown",
            metadata={"content_sha256": digest, "format": fmt}).to_dict()
        store.append(source)
    asset = next((r for r in store.list_records("asset")
                  if r.get("uri") == uri and (r.get("metadata") or {}).get("content_sha256") == digest), None)
    if asset is None:
        asset = new_record("asset", workspace_id=store.workspace_id,
            source_id=source["id"], asset_type="dataset", uri=uri, title=path_name,
            status="active", metadata={"content_sha256": digest, "format": fmt,
                                       "source_adapter_id": adapter_id}).to_dict()
        store.append(asset)
    return asset, digest


def _get_evidence(store: JsonWorkspaceStore, asset: dict[str, Any], path_name: str,
                  row_number: int, headers: list[str], cells: list[str],
                  digest: str, adapter_id: str, sheet: str | None = None):
    locator = {"path": path_name, "row": row_number, "block": "row"}
    if sheet:
        locator["sheet"] = sheet
    statement = json.dumps({"headers": headers, "values": cells},
                           ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    existing = next((r for r in store.list_records("evidence")
                     if r.get("asset_id") == asset["id"] and r.get("locator") == locator
                     and r.get("statement") == statement), None)
    if existing:
        return existing
    evidence = new_record("evidence", workspace_id=store.workspace_id,
        asset_id=asset["id"], evidence_kind="data", statement=statement,
        locator=locator, captured_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        verification_status="source_confirmed",
        metadata={"content_sha256": digest, "source_adapter_id": adapter_id,
                  "extraction_method": "xlsx_row" if sheet else "csv_row"}).to_dict()
    store.append(evidence)
    return evidence


def _read_manifest(store: JsonWorkspaceStore, path: str, adapter: dict[str, Any]):
    data = Path(path).read_bytes()
    if len(data) > int(adapter.get("max_manifest_bytes", 10 * 1024 * 1024)):
        raise LedgerSourceAdapterError("manifest exceeds size limit")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeError as exc:
        raise LedgerSourceAdapterError("manifest must be UTF-8 JSONL: %s" % exc)
    name = Path(path).name
    asset, digest = _get_asset(store, name, data, "jsonl", adapter["id"] + ".manifest")
    manifests, evidence, unresolved = [], [], []
    existing = {r.get("manifest", {}).get("id"): r.get("manifest")
                for r in store.list_records("ledger_manifest")}
    for line_num, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            unresolved.append({"line": line_num, "reason": "invalid_manifest_json", "detail": str(exc)[:160]})
            continue
        if not isinstance(row, dict):
            unresolved.append({"line": line_num, "reason": "manifest_line_must_be_object"})
            continue
        required = ("company_id", "currency", "voucher_type", "voucher_id",
                    "accounting_period", "expected_ledger_entry_ids")
        try:
            for field in required[:-1]:
                row[field] = _required_text(row.get(field), "manifest.%s" % field)
        except LedgerSourceAdapterError as exc:
            unresolved.append({"line": line_num, "reason": "invalid_manifest_field", "detail": str(exc)})
            continue
        if row.get("source_system", adapter["source_system"]) != adapter["source_system"]:
            unresolved.append({"line": line_num, "reason": "manifest_source_system_mismatch"})
            continue
        ids = row["expected_ledger_entry_ids"]
        if not isinstance(ids, list) or not ids or any(not isinstance(v, str) or not v.strip() for v in ids):
            unresolved.append({"line": line_num, "reason": "invalid_expected_ledger_entry_ids"})
            continue
        ids = [v.strip() for v in ids]
        if len(set(ids)) != len(ids):
            unresolved.append({"line": line_num, "reason": "duplicate_expected_ledger_entry_ids"})
            continue
        manifest_id = row.get("id")
        if not isinstance(manifest_id, str) or not manifest_id.strip():
            manifest_id = "MAN-" + sha256((digest + "|" + str(line_num)).encode()).hexdigest()[:20]
        locator = {"path": name, "line": line_num, "block": "json_line"}
        statement = line.strip()
        ev = next((r for r in store.list_records("evidence")
                   if r.get("asset_id") == asset["id"] and r.get("locator") == locator
                   and r.get("statement") == statement), None)
        if ev is None:
            ev = new_record("evidence", workspace_id=store.workspace_id,
                asset_id=asset["id"], evidence_kind="data", statement=statement,
                locator=locator, captured_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                verification_status="unverified",
                metadata={"content_sha256": digest, "manifest_assertion": True}).to_dict()
            store.append(ev)
        evidence.append(ev)
        manifest = dict(row)
        manifest.update({"id": manifest_id, "source_system": adapter["source_system"],
                         "expected_ledger_entry_ids": ids, "asset_id": asset["id"],
                         "evidence_id": ev["id"], "locator": locator})
        prior = existing.get(manifest_id)
        if prior is not None:
            prior_cmp = {k: v for k, v in prior.items() if k not in ("asset_id", "evidence_id", "locator")}
            new_cmp = {k: v for k, v in manifest.items() if k not in ("asset_id", "evidence_id", "locator")}
            if prior_cmp == new_cmp:
                continue
            unresolved.append({"line": line_num, "reason": "conflicting_existing_manifest_id",
                               "manifest_id": manifest_id})
            continue
        existing[manifest_id] = manifest
        manifests.append(manifest)
    return manifests, evidence, unresolved


def adapt_ledger_source(store: JsonWorkspaceStore, input_path: str,
                        adapter_config: dict[str, Any],
                        aggregation_rules: list[dict[str, Any]] | None = None,
                        manifest_path: str | None = None) -> dict[str, Any]:
    config = validate_ledger_source_adapter(adapter_config)
    data = Path(input_path).read_bytes()
    if len(data) > int(config.get("max_input_bytes", 50 * 1024 * 1024)):
        raise LedgerSourceAdapterError("input exceeds configured byte limit")
    name = Path(input_path).name
    if config["format"] == "csv":
        headers, rows, sheet = _csv_rows(data, config)
    else:
        headers, rows, sheet = _xlsx_rows(data, config)
    columns = _resolve_columns(headers, config)
    asset, digest = _get_asset(store, name, data, config["format"], config["id"])

    evidence_records, effects, unresolved, duplicates = [], [], [], []
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    optional = set(config.get("optional_fields", []))
    value_maps = config.get("value_maps", {})
    for row_num, cells in rows:
        if not any(str(value).strip() for value in cells):
            continue
        ev = _get_evidence(store, asset, name, row_num, headers, cells, digest, config["id"], sheet)
        evidence_records.append(ev)
        raw = {field: (cells[column - 1] if column <= len(cells) else "")
               for field, column in columns.items()}
        values = dict(config.get("constants", {}))
        try:
            for field in config["field_map"]:
                value = raw.get(field, "")
                if not str(value).strip():
                    if field in optional:
                        values.pop(field, None)
                        continue
                    raise LedgerSourceAdapterError("%s is empty" % field)
                values[field] = _map_field(field, value, config) if field in value_maps else str(value).strip()
            for field in COMMON:
                values[field] = _required_text(values.get(field), field)
            if values["posting_status"] not in ("posted", "reversal", "adjustment"):
                raise LedgerSourceAdapterError("posting_status must map to posted/reversal/adjustment")
            for field in ("posting_date", "period_start_date", "period_end_date"):
                if field in values:
                    values[field] = _date(values[field], config, field)
            for field in ("quantity_delta", "stock_value_delta", "debit_amount", "credit_amount"):
                if field in values:
                    values[field] = _decimal(values[field], config, field)
            effect = {
                "ledger_entry_id": values["ledger_entry_id"],
                "source_system": config["source_system"],
                "ledger_kind": config["ledger_kind"],
                "company_id": values["company_id"],
                "voucher_type": values["voucher_type"],
                "voucher_id": values["voucher_id"],
                "voucher_item_id": values["voucher_item_id"],
                "source_document_ref": {
                    "voucher_type": values["voucher_type"],
                    "voucher_id": values["voucher_id"],
                    "voucher_item_id": values["voucher_item_id"],
                },
                "event_kind": values["event_kind"],
                "posting_status": values["posting_status"],
                "currency": values["currency"],
                "accounting_period": values["accounting_period"],
                "asset_id": asset["id"], "evidence_id": ev["id"], "locator": ev["locator"],
            }
            for field in OPTIONAL:
                if field in values:
                    effect[field] = values[field]
            dimensions = STOCK if config["ledger_kind"] == "stock" else GL
            for field in sorted(dimensions):
                effect[field] = values[field]
            checked = validate_ledger_effects([effect], [ev])
            if checked["summary"]["accepted"] != 1:
                raise LedgerSourceAdapterError("ledger effect validator did not accept row")
            effect = checked["ledger_effects"][0]
        except (LedgerSourceAdapterError, LedgerEffectError, KeyError) as exc:
            unresolved.append({"row": row_num, "locator": ev["locator"],
                               "reason": "row_mapping_or_validation_failed", "detail": str(exc)[:240]})
            continue

        identity = (effect["source_system"], effect["ledger_entry_id"])
        if identity in seen:
            previous = seen[identity]
            if _signature(previous) == _signature(effect):
                duplicates.append({"row": row_num, "ledger_entry_id": identity[1],
                                   "reason": "identical_duplicate_source_row"})
            else:
                previous["_conflicted"] = True
                unresolved.append({"row": row_num, "ledger_entry_id": identity[1],
                                   "reason": "conflicting_duplicate_source_identity"})
            continue
        seen[identity] = effect
        effects.append(effect)

    effects = [effect for effect in effects if not effect.pop("_conflicted", False)]
    existing_effects = {}
    for record in store.list_records("ledger_effect"):
        effect = record.get("effect", {})
        existing_effects[(record.get("source_system"), record.get("ledger_entry_id"))] = effect
    new_effects = []
    for effect in effects:
        identity = (effect["source_system"], effect["ledger_entry_id"])
        old = existing_effects.get(identity)
        if old is None:
            new_effects.append(effect)
        elif _signature(old) == _signature(effect):
            duplicates.append({"ledger_entry_id": identity[1],
                               "reason": "identical_ledger_entry_already_in_workspace"})
        else:
            unresolved.append({"ledger_entry_id": identity[1],
                               "reason": "conflicting_existing_ledger_identity"})

    manifests, manifest_evidence, manifest_unresolved = ([], [], [])
    if manifest_path:
        manifests, manifest_evidence, manifest_unresolved = _read_manifest(store, manifest_path, config)
        unresolved.extend(manifest_unresolved)

    existing_rules = {r["rule_id"]: r["rule"] for r in store.list_records("ledger_aggregation_rule")}
    new_rules = []
    for rule in aggregation_rules or []:
        rule_id = rule.get("id") if isinstance(rule, dict) else None
        if not isinstance(rule_id, str) or not rule_id.strip():
            unresolved.append({"reason": "invalid_pack_ledger_aggregation_rule"})
        elif rule_id not in existing_rules:
            new_rules.append(rule)
        elif existing_rules[rule_id] != rule:
            unresolved.append({"reason": "conflicting_existing_aggregation_rule", "rule_id": rule_id})

    evidence_by_id = {r["id"]: r for r in store.list_records("evidence")}
    referenced = {r["evidence_id"] for r in new_effects + manifests}
    bundle_evidence = [evidence_by_id[key] for key in sorted(referenced) if key in evidence_by_id]
    imported = import_ledger_bundle(store, {
        "ledger_effects": new_effects,
        "evidence_records": bundle_evidence,
        "extraction_manifests": manifests,
        "aggregation_rules": new_rules,
    })
    return {
        "schema_version": 1,
        "adapter_id": config["id"],
        "source_system": config["source_system"],
        "ledger_kind": config["ledger_kind"],
        "asset_id": asset["id"],
        "content_sha256": digest,
        "rows_seen": len(rows),
        "rows_with_evidence": len(evidence_records),
        "ledger_effects_ready": len(effects),
        "ledger_effects_imported": imported["ledger_effects"],
        "extraction_manifests_imported": imported["extraction_manifests"],
        "aggregation_rules_imported": imported["aggregation_rules"],
        "duplicates": duplicates,
        "unresolved": unresolved,
        "summary": {
            "imported": imported["ledger_effects"],
            "duplicates": len(duplicates),
            "unresolved": len(unresolved),
            "partial": bool(unresolved or duplicates),
        },
    }
