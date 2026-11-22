"""Conservative inventory-to-GL reconciliation over explicit ledger aggregates."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Iterable


class LedgerReconciliationError(ValueError):
    """Invalid reconciliation inputs or policy."""


def _amount(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise LedgerReconciliationError("amount must be a finite decimal")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise LedgerReconciliationError("amount must be a finite decimal")
    if not result.is_finite():
        raise LedgerReconciliationError("amount must be a finite decimal")
    return result


def reconcile_inventory_gl(stock_groups: Iterable[dict[str, Any]],
                           gl_groups: Iterable[dict[str, Any]],
                           tolerance: Any = "0.01") -> dict[str, Any]:
    """Compare stock value changes with mapped inventory GL accounts per period.

    Many item/warehouse stock groups and many inventory GL account groups are
    rolled up to company/currency/period. Missing scope, mapping or counterpart
    is unresolved; it is never treated as a zero balance.
    """
    allowed_tolerance = _amount(tolerance)
    if allowed_tolerance < 0:
        raise LedgerReconciliationError("tolerance cannot be negative")
    dimensions = ("company_id", "currency", "accounting_period")

    def collect(groups, side):
        indexed = {}
        unresolved = []
        for group in groups:
            scope = group.get("business_scope", {}) if isinstance(group, dict) else {}
            if not isinstance(scope, dict) or any(
                    not isinstance(scope.get(key), str) or not scope[key].strip()
                    for key in dimensions):
                unresolved.append({
                    "side": side, "aggregate_id": group.get("id") if isinstance(group, dict) else None,
                    "reason": "missing_company_currency_or_accounting_period"})
                continue
            key = tuple(scope[name] for name in dimensions)
            indexed.setdefault(key, []).append(group)
        return indexed, unresolved

    stock_index, unresolved = collect(list(stock_groups), "stock")
    gl_candidates = []
    for group in gl_groups:
        if (group.get("account_mapping_status") != "mapped"
                or group.get("account_role") != "inventory_asset"):
            unresolved.append({"side": "general_ledger", "aggregate_id": group.get("id"),
                               "reason": "inventory_account_mapping_missing_or_not_inventory_asset"})
            continue
        gl_candidates.append(group)
    gl_index, gl_unresolved = collect(gl_candidates, "general_ledger")
    unresolved.extend(gl_unresolved)

    results = []
    for key in sorted(set(stock_index) | set(gl_index)):
        stocks, gls = stock_index.get(key, []), gl_index.get(key, [])
        scope = dict(zip(dimensions, key))
        if not stocks or not gls:
            results.append({
                "scope": scope, "status": "unresolved",
                "reason": "missing_stock_or_inventory_gl_aggregate",
                "stock_aggregate_ids": sorted(item["id"] for item in stocks),
                "gl_aggregate_ids": sorted(item["id"] for item in gls),
                "evidence_ids": sorted(
                    {ev for item in stocks + gls for ev in item.get("evidence_ids", [])}),
            })
            continue
        def total(groups):
            values = []
            for group in groups:
                output = group.get("values", {})
                if not isinstance(output, dict) or len(output) != 1:
                    raise LedgerReconciliationError(
                        "each aggregate must expose exactly one output value")
                values.append(_amount(next(iter(output.values()))))
            return sum(values, Decimal("0"))
        stock_value, gl_value = total(stocks), total(gls)
        difference = stock_value - gl_value
        results.append({
            "scope": scope,
            "status": "matched" if abs(difference) <= allowed_tolerance else "mismatch",
            "stock_value": str(stock_value), "general_ledger_value": str(gl_value),
            "difference": str(difference), "tolerance": str(allowed_tolerance),
            "stock_aggregate_ids": sorted(item["id"] for item in stocks),
            "gl_aggregate_ids": sorted(item["id"] for item in gls),
            "evidence_ids": sorted(
                {ev for item in stocks + gls for ev in item.get("evidence_ids", [])}),
        })
    return {
        "schema_version": 1, "results": results,
        "unresolved": sorted(unresolved, key=lambda item: (
            item.get("side", ""), item.get("aggregate_id") or "", item["reason"])),
        "summary": {
            "matched": sum(1 for item in results if item["status"] == "matched"),
            "mismatched": sum(1 for item in results if item["status"] == "mismatch"),
            "unresolved": sum(1 for item in results if item["status"] == "unresolved") + len(unresolved),
        },
        "policy": {
            "requires_explicit_account_role_mapping": True,
            "requires_company_currency_and_accounting_period": True,
            "rolls_up_item_warehouse_and_account_groups_to_period": True,
            "missing_counterpart_is_not_zero": True,
            "tolerance_is_explicit": True,
            "result_is_not_an_automatic_business_assessment": True,
        },
    }
