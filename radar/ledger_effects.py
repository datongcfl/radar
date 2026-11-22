"""Validation for source-neutral stock and general-ledger effects.

This module validates provenance-backed ledger rows. It deliberately does not
infer accounting entries, valuation, or business outcomes from source documents.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable


class LedgerEffectError(ValueError):
    """Raised when a ledger-effect bundle or its contract is malformed."""


def _decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool):
        raise LedgerEffectError("%s must be a finite decimal" % field)
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise LedgerEffectError("%s must be a finite decimal" % field)
    if not number.is_finite():
        raise LedgerEffectError("%s must be a finite decimal" % field)
    return number


def _has_locator(locator: Any) -> bool:
    if not isinstance(locator, dict):
        return False
    if locator.get("cell") and locator.get("path") and locator.get("sheet"):
        return True
    if locator.get("path") and isinstance(locator.get("row"), int) and isinstance(
            locator.get("column"), int):
        return locator["row"] > 0 and locator["column"] > 0
    if (locator.get("path") and isinstance(locator.get("row"), int)
            and locator["row"] > 0 and locator.get("block") == "row"):
        return True
    if (locator.get("path") and isinstance(locator.get("line"), int)
            and locator["line"] > 0):
        return True
    return False


def _iso_date(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise LedgerEffectError("%s must be an ISO date (YYYY-MM-DD)" % field)
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise LedgerEffectError("%s must be an ISO date (YYYY-MM-DD)" % field)
    if parsed.isoformat() != value:
        raise LedgerEffectError("%s must be an ISO date (YYYY-MM-DD)" % field)
    return value


def _required_text(row: dict[str, Any], field: str, where: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise LedgerEffectError("%s.%s must be a non-empty string" % (where, field))
    return value.strip()


def _normalize_one(row: dict[str, Any], evidence_by_id: dict[str, dict[str, Any]],
                    index: int) -> dict[str, Any]:
    where = "ledger_effects[%d]" % index
    if not isinstance(row, dict):
        raise LedgerEffectError("%s must be an object" % where)

    normalized = dict(row)
    for field in ("ledger_entry_id", "source_system", "ledger_kind", "company_id",
                  "voucher_type", "voucher_id", "event_kind", "posting_status",
                  "currency", "evidence_id"):
        normalized[field] = _required_text(row, field, where)

    if normalized["ledger_kind"] not in ("stock", "general_ledger"):
        raise LedgerEffectError("%s.ledger_kind must be stock or general_ledger" % where)
    if normalized["posting_status"] not in ("posted", "reversal", "adjustment"):
        raise LedgerEffectError("%s.posting_status is unsupported" % where)

    # Posting dates and accounting periods are source facts, not inferred values.
    # A period label is intentionally opaque: fiscal calendars need not be monthly.
    for field in ("posting_date", "period_start_date", "period_end_date"):
        if row.get(field) is not None:
            normalized[field] = _iso_date(row[field], where + "." + field)
    if row.get("accounting_period") is not None:
        normalized["accounting_period"] = _required_text(row, "accounting_period", where)
    has_period_boundary = ("period_start_date" in normalized or
                           "period_end_date" in normalized)
    if has_period_boundary:
        if ("period_start_date" not in normalized or
                "period_end_date" not in normalized or
                "accounting_period" not in normalized):
            raise LedgerEffectError(
                "%s period boundaries require accounting_period, period_start_date, "
                "and period_end_date" % where)
        if normalized["period_start_date"] > normalized["period_end_date"]:
            raise LedgerEffectError("%s period_start_date must not exceed period_end_date" % where)
        posting_date = normalized.get("posting_date")
        if posting_date is not None and not (
                normalized["period_start_date"] <= posting_date <= normalized["period_end_date"]):
            raise LedgerEffectError("%s posting_date falls outside its accounting period bounds" % where)

    source_ref = row.get("source_document_ref")
    if not isinstance(source_ref, dict):
        raise LedgerEffectError("%s.source_document_ref must be an object" % where)
    for field in ("voucher_type", "voucher_id", "voucher_item_id"):
        _required_text(source_ref, field, where + ".source_document_ref")
    if source_ref["voucher_type"] != normalized["voucher_type"] or (
            source_ref["voucher_id"] != normalized["voucher_id"]):
        raise LedgerEffectError("%s source_document_ref conflicts with voucher identity" % where)

    if not _required_text(row, "voucher_item_id", where):
        raise LedgerEffectError("%s.voucher_item_id is required" % where)
    if source_ref["voucher_item_id"] != row["voucher_item_id"]:
        raise LedgerEffectError("%s source_document_ref item conflicts with voucher_item_id" % where)

    evidence = evidence_by_id.get(normalized["evidence_id"])
    if evidence is None:
        raise LedgerEffectError("%s references unknown Evidence %s" %
                                (where, normalized["evidence_id"]))
    if evidence.get("asset_id") != row.get("asset_id"):
        raise LedgerEffectError("%s Evidence belongs to a different Asset" % where)
    if not _has_locator(evidence.get("locator")):
        raise LedgerEffectError("%s Evidence requires a precise source locator" % where)
    if row.get("locator") != evidence.get("locator"):
        raise LedgerEffectError("%s locator must exactly match its Evidence locator" % where)

    reversal_of = row.get("reversal_of")
    if normalized["posting_status"] == "reversal":
        if not isinstance(reversal_of, str) or not reversal_of.strip():
            raise LedgerEffectError("%s reversal requires reversal_of ledger entry identity" % where)
        if reversal_of == normalized["ledger_entry_id"]:
            raise LedgerEffectError("%s cannot reverse itself" % where)
    elif reversal_of:
        raise LedgerEffectError("%s reversal_of is only valid for reversal rows" % where)

    if normalized["ledger_kind"] == "stock":
        for field in ("item_id", "warehouse_id", "quantity_uom"):
            normalized[field] = _required_text(row, field, where)
        normalized["quantity_delta"] = str(_decimal(row.get("quantity_delta"), where + ".quantity_delta"))
        normalized["stock_value_delta"] = str(_decimal(row.get("stock_value_delta"),
                                                       where + ".stock_value_delta"))
        if row.get("valuation_method") is not None:
            normalized["valuation_method"] = _required_text(row, "valuation_method", where)
    else:
        normalized["account_id"] = _required_text(row, "account_id", where)
        debit = _decimal(row.get("debit_amount"), where + ".debit_amount")
        credit = _decimal(row.get("credit_amount"), where + ".credit_amount")
        if debit < 0 or credit < 0:
            raise LedgerEffectError("%s debit_amount and credit_amount cannot be negative" % where)
        if debit and credit:
            raise LedgerEffectError("%s must represent one debit or credit side, not both" % where)
        normalized["debit_amount"] = str(debit)
        normalized["credit_amount"] = str(credit)

    if not isinstance(row.get("asset_id"), str) or not row["asset_id"].strip():
        raise LedgerEffectError("%s.asset_id must be a non-empty string" % where)
    normalized["asset_id"] = row["asset_id"].strip()
    normalized["source_document_ref"] = dict(source_ref)
    normalized["locator"] = dict(evidence["locator"])
    return normalized


def validate_ledger_effects(ledger_effects: Iterable[dict[str, Any]],
                            evidence_records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Validate stock/GL ledger rows and return deterministic accepted/skipped sets.

    Exact duplicate ledger identities are retained once. Conflicting rows with
    the same source_system + ledger_entry_id are all excluded as ambiguous.
    Reversal targets are checked against the supplied ledger bundle; absent
    targets are reported as unresolved rather than silently accepted.
    """
    evidence_by_id = {}
    for item in evidence_records:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            evidence_by_id[item["id"]] = item

    rows = list(ledger_effects)
    normalized = []
    skipped = []
    identities = {}
    conflicted = set()
    for index, row in enumerate(rows):
        item = _normalize_one(row, evidence_by_id, index)
        identity = (item["source_system"], item["ledger_entry_id"])
        if identity in identities:
            if identities[identity] != item:
                conflicted.add(identity)
            else:
                skipped.append({"ledger_entry_id": item["ledger_entry_id"],
                                "reason": "duplicate_ledger_entry"})
            continue
        identities[identity] = item
        normalized.append(item)

    if conflicted:
        for identity in sorted(conflicted):
            skipped.append({"ledger_entry_id": identity[1],
                            "reason": "conflicting_ledger_entry_identity"})
        normalized = [item for item in normalized
                      if (item["source_system"], item["ledger_entry_id"]) not in conflicted]

    available_ids = {(item["source_system"], item["ledger_entry_id"])
                     for item in normalized}
    accepted = []
    normalized_by_identity = {
        (item["source_system"], item["ledger_entry_id"]): item for item in normalized
    }
    for item in normalized:
        if item["posting_status"] == "reversal":
            target = (item["source_system"], item["reversal_of"])
            original = normalized_by_identity.get(target)
            if original is None:
                skipped.append({"ledger_entry_id": item["ledger_entry_id"],
                                "reason": "unresolved_reversal_target",
                                "reversal_of": item["reversal_of"]})
                continue
            identity_fields = ["ledger_kind", "company_id", "currency", "voucher_type",
                               "voucher_id", "voucher_item_id"]
            if item["ledger_kind"] == "stock":
                identity_fields.extend(("item_id", "warehouse_id", "quantity_uom"))
            else:
                identity_fields.append("account_id")
            if any(item.get(field) != original.get(field) for field in identity_fields):
                skipped.append({"ledger_entry_id": item["ledger_entry_id"],
                                "reason": "reversal_target_semantics_mismatch",
                                "reversal_of": item["reversal_of"]})
                continue
            if item["ledger_kind"] == "stock":
                effect_matches = (
                    Decimal(item["quantity_delta"]) == -Decimal(original["quantity_delta"])
                    and Decimal(item["stock_value_delta"]) == -Decimal(original["stock_value_delta"])
                )
            else:
                reversal_net = Decimal(item["debit_amount"]) - Decimal(item["credit_amount"])
                original_net = Decimal(original["debit_amount"]) - Decimal(original["credit_amount"])
                effect_matches = reversal_net == -original_net
            if not effect_matches:
                skipped.append({"ledger_entry_id": item["ledger_entry_id"],
                                "reason": "reversal_effect_does_not_reverse_original",
                                "reversal_of": item["reversal_of"]})
                continue
        accepted.append(item)

    accepted.sort(key=lambda item: (item["source_system"], item["ledger_entry_id"]))
    skipped.sort(key=lambda item: (item.get("ledger_entry_id", ""),
                                   item["reason"]))
    return {
        "schema_version": 1,
        "ledger_effects": accepted,
        "skipped": skipped,
        "summary": {
            "input": len(rows),
            "accepted": len(accepted),
            "skipped": len(skipped),
            "stock_entries": sum(1 for item in accepted if item["ledger_kind"] == "stock"),
            "general_ledger_entries": sum(
                1 for item in accepted if item["ledger_kind"] == "general_ledger"),
            "reversal_entries": sum(1 for item in accepted
                                    if item["posting_status"] == "reversal"),
            "missing_posting_date": sum(1 for item in accepted if "posting_date" not in item),
            "missing_accounting_period": sum(1 for item in accepted
                                             if "accounting_period" not in item),
        },
        "policy": {
            "stock_and_gl_are_separate_streams": True,
            "valuation_is_not_inferred_from_document_rate": True,
            "ledger_rows_require_evidence_and_locator": True,
            "reversal_requires_exact_original_ledger_identity": True,
            "reversal_must_match_original_scope_and_opposite_effect": True,
            "posting_date_must_be_iso_date_when_present": True,
            "accounting_period_is_explicit_and_never_inferred": True,
            "period_boundaries_must_contain_posting_date_when_both_are_supplied": True,
            "validation_does_not_assess_business_invariants": True,
        },
    }
