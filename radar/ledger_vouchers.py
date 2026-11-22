"""Voucher-level general-ledger balancing with explicit extract completeness."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Iterable


class LedgerVoucherError(ValueError):
    """Malformed GL voucher or extraction-manifest contract."""


def _decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool):
        raise LedgerVoucherError("%s must be a finite decimal" % field)
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise LedgerVoucherError("%s must be a finite decimal" % field)
    if not result.is_finite():
        raise LedgerVoucherError("%s must be a finite decimal" % field)
    return result


def _text(record: dict[str, Any], field: str, where: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise LedgerVoucherError("%s.%s must be a non-empty string" % (where, field))
    return value.strip()


def _locator_is_precise(locator: Any) -> bool:
    if not isinstance(locator, dict) or not locator.get("path"):
        return False
    if locator.get("cell") and locator.get("sheet"):
        return True
    if (isinstance(locator.get("row"), int) and isinstance(locator.get("column"), int)
            and locator["row"] > 0 and locator["column"] > 0):
        return True
    return locator.get("line") is not None


def _voucher_key(record: dict[str, Any], where: str) -> tuple[str, ...]:
    return tuple(_text(record, field, where) for field in (
        "source_system", "company_id", "currency", "voucher_type",
        "voucher_id", "accounting_period"))


def validate_gl_vouchers(
        ledger_effects: Iterable[dict[str, Any]],
        extraction_manifests: Iterable[dict[str, Any]],
        evidence_records: Iterable[dict[str, Any]],
        tolerance: Any = "0") -> dict[str, Any]:
    """Balance complete GL vouchers only; incomplete extracts remain unresolved.

    A manifest proves the expected line identity set for one voucher. The
    validator compares that set with the supplied GL rows before summing debit
    and credit. It never interprets an absent line as zero.
    """
    allowed_tolerance = _decimal(tolerance, "tolerance")
    if allowed_tolerance < 0:
        raise LedgerVoucherError("tolerance cannot be negative")

    evidence_by_id = {}
    for evidence in evidence_records:
        if isinstance(evidence, dict) and isinstance(evidence.get("id"), str):
            evidence_by_id[evidence["id"]] = evidence

    rows_by_key: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    unresolved = []
    for index, row in enumerate(ledger_effects):
        if not isinstance(row, dict):
            raise LedgerVoucherError("ledger_effects[%d] must be an object" % index)
        if row.get("ledger_kind") != "general_ledger":
            continue
        where = "ledger_effects[%d]" % index
        if not isinstance(row.get("accounting_period"), str) or not row["accounting_period"].strip():
            unresolved.append({
                "status": "unresolved", "reason": "missing_accounting_period",
                "ledger_entry_id": row.get("ledger_entry_id")})
            continue
        key = _voucher_key(row, where)
        entry_id = _text(row, "ledger_entry_id", where)
        debit = _decimal(row.get("debit_amount"), where + ".debit_amount")
        credit = _decimal(row.get("credit_amount"), where + ".credit_amount")
        if debit < 0 or credit < 0 or (debit and credit):
            raise LedgerVoucherError("%s must contain one non-negative debit or credit side" % where)
        normalized = dict(row)
        normalized["_entry_id"] = entry_id
        normalized["_debit"] = debit
        normalized["_credit"] = credit
        rows_by_key.setdefault(key, []).append(normalized)

    manifests_by_key: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for index, manifest in enumerate(extraction_manifests):
        if not isinstance(manifest, dict):
            raise LedgerVoucherError("extraction_manifests[%d] must be an object" % index)
        where = "extraction_manifests[%d]" % index
        manifest_id = _text(manifest, "id", where)
        key = _voucher_key(manifest, where)
        expected = manifest.get("expected_ledger_entry_ids")
        if (not isinstance(expected, list) or not expected
                or any(not isinstance(item, str) or not item.strip() for item in expected)
                or len(set(expected)) != len(expected)):
            raise LedgerVoucherError(
                "%s.expected_ledger_entry_ids must be a non-empty unique string list" % where)
        evidence_id = _text(manifest, "evidence_id", where)
        asset_id = _text(manifest, "asset_id", where)
        locator = manifest.get("locator")
        evidence = evidence_by_id.get(evidence_id)
        if evidence is None or evidence.get("asset_id") != asset_id:
            raise LedgerVoucherError("%s requires manifest Evidence belonging to its Asset" % where)
        if (not _locator_is_precise(locator) or locator != evidence.get("locator")):
            raise LedgerVoucherError("%s locator must exactly match precise manifest Evidence" % where)
        manifests_by_key.setdefault(key, []).append({
            "id": manifest_id, "expected_ids": sorted(item.strip() for item in expected),
            "evidence_id": evidence_id})

    results = []
    for key in sorted(set(rows_by_key) | set(manifests_by_key)):
        rows = rows_by_key.get(key, [])
        manifests = manifests_by_key.get(key, [])
        scope = dict(zip(("source_system", "company_id", "currency", "voucher_type",
                          "voucher_id", "accounting_period"), key))
        if len(manifests) > 1:
            unresolved.append({
                "status": "unresolved", "scope": scope,
                "reason": "conflicting_voucher_extraction_manifests",
                "manifest_ids": sorted(item["id"] for item in manifests)})
            continue
        if not manifests:
            unresolved.append({
                "status": "unresolved", "scope": scope,
                "reason": "missing_voucher_extraction_manifest",
                "ledger_entry_ids": sorted(item["_entry_id"] for item in rows)})
            continue
        manifest = manifests[0]
        actual_ids = [item["_entry_id"] for item in rows]
        if len(set(actual_ids)) != len(actual_ids):
            unresolved.append({
                "status": "unresolved", "scope": scope,
                "reason": "duplicate_ledger_entry_in_voucher_extract",
                "manifest_id": manifest["id"]})
            continue
        expected_ids = set(manifest["expected_ids"])
        actual_set = set(actual_ids)
        if expected_ids != actual_set:
            unresolved.append({
                "status": "unresolved", "scope": scope,
                "reason": "incomplete_voucher_extract",
                "manifest_id": manifest["id"],
                "missing_ledger_entry_ids": sorted(expected_ids - actual_set),
                "unexpected_ledger_entry_ids": sorted(actual_set - expected_ids)})
            continue
        debit_total = sum((item["_debit"] for item in rows), Decimal("0"))
        credit_total = sum((item["_credit"] for item in rows), Decimal("0"))
        difference = debit_total - credit_total
        results.append({
            "scope": scope,
            "manifest_id": manifest["id"],
            "status": "balanced" if abs(difference) <= allowed_tolerance else "unbalanced",
            "debit_total": str(debit_total),
            "credit_total": str(credit_total),
            "difference": str(difference),
            "tolerance": str(allowed_tolerance),
            "ledger_entry_ids": sorted(actual_ids),
            "evidence_ids": sorted({manifest["evidence_id"]} |
                                   {item["evidence_id"] for item in rows
                                    if isinstance(item.get("evidence_id"), str)}),
        })

    results.sort(key=lambda item: tuple(item["scope"].values()))
    unresolved.sort(key=lambda item: (
        tuple(item.get("scope", {}).values()), item.get("reason", ""),
        item.get("ledger_entry_id", "")))
    return {
        "schema_version": 1,
        "results": results,
        "unresolved": unresolved,
        "summary": {
            "balanced": sum(1 for item in results if item["status"] == "balanced"),
            "unbalanced": sum(1 for item in results if item["status"] == "unbalanced"),
            "unresolved": len(unresolved),
        },
        "policy": {
            "requires_explicit_voucher_extraction_manifest": True,
            "manifest_must_match_exact_ledger_entry_identity_set": True,
            "incomplete_extract_is_not_assessed_as_unbalanced": True,
            "debit_credit_balance_is_voucher_scoped": True,
            "tolerance_is_explicit": True,
            "result_is_not_an_automatic_business_assessment": True,
        },
    }
