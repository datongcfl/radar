"""Explicit, provenance-backed aggregation of stock and GL ledger effects."""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
from typing import Any, Iterable

from .ledger_effects import LedgerEffectError, validate_ledger_effects


class LedgerAggregationError(ValueError):
    """Invalid ledger aggregation declaration or input."""


def aggregate_ledger_effects(ledger_effects: Iterable[dict[str, Any]],
                             evidence_records: Iterable[dict[str, Any]],
                             rules: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate only explicitly declared dimensions; never infer valuation or account roles."""
    evidence = list(evidence_records)
    validated = validate_ledger_effects(ledger_effects, evidence)
    rows = validated["ledger_effects"]
    outputs = []
    for rule in rules:
        if not isinstance(rule, dict):
            raise LedgerAggregationError("ledger aggregation rule must be an object")
        for field in ("id", "ledger_kind", "group_by", "metric", "output_field"):
            if field not in rule:
                raise LedgerAggregationError("ledger aggregation rule missing %s" % field)
        if not isinstance(rule["id"], str) or not rule["id"].strip():
            raise LedgerAggregationError("aggregation id must be non-empty")
        kind, metric, group_by = rule["ledger_kind"], rule["metric"], rule["group_by"]
        if kind not in ("stock", "general_ledger"):
            raise LedgerAggregationError("unsupported ledger_kind")
        allowed_metrics = ({"quantity_delta", "stock_value_delta"} if kind == "stock"
                           else {"signed_amount"})
        if metric not in allowed_metrics:
            raise LedgerAggregationError("unsupported metric for ledger_kind")
        if (not isinstance(group_by, list) or not group_by or
                any(not isinstance(field, str) or not field for field in group_by) or
                len(set(group_by)) != len(group_by)):
            raise LedgerAggregationError("group_by must contain unique non-empty fields")
        required = ({"company_id", "currency", "item_id", "warehouse_id", "quantity_uom"}
                    if kind == "stock" else {"company_id", "currency", "account_id"})
        if not required.issubset(set(group_by)):
            raise LedgerAggregationError("group_by omits mandatory ledger dimensions")
        mapping = rule.get("account_mapping", {})
        if kind == "stock" and mapping:
            raise LedgerAggregationError("stock aggregation cannot declare account_mapping")
        if kind == "general_ledger" and not isinstance(mapping, dict):
            raise LedgerAggregationError("account_mapping must be an object")
        grouped = {}
        skipped = list(validated["skipped"])
        for row in rows:
            if row["ledger_kind"] != kind:
                continue
            if any(not isinstance(row.get(field), str) or not row[field].strip()
                   for field in group_by):
                skipped.append({"ledger_entry_id": row["ledger_entry_id"],
                                "reason": "missing_ledger_group_dimension"})
                continue
            scope = {field: row[field] for field in group_by}
            key = tuple(scope[field] for field in group_by)
            if kind == "stock":
                value = Decimal(row[metric])
            else:
                value = Decimal(row["debit_amount"]) - Decimal(row["credit_amount"])
            contribution = {
                "ledger_entry_id": row["ledger_entry_id"], "asset_id": row["asset_id"],
                "evidence_id": row["evidence_id"], "locator": row["locator"],
                "source_document_ref": row["source_document_ref"], "value": str(value),
            }
            grouped.setdefault(key, []).append((scope, contribution))
        results = []
        for key in sorted(grouped):
            contributions = grouped[key]
            # Evidence identity is the minimum deduplication unit; duplicate ledger rows
            # have already been normalized by source-system ledger identity.
            by_ledger_id = {}
            for scope, contribution in contributions:
                by_ledger_id[contribution["ledger_entry_id"]] = contribution
            unique = list(by_ledger_id.values())
            total = sum((Decimal(item["value"]) for item in unique), Decimal("0"))
            scope = contributions[0][0]
            scope_key = "|".join("%s=%s" % (name, scope[name]) for name in group_by)
            digest = sha256((rule["id"] + "|" + scope_key).encode("utf-8")).hexdigest()[:20]
            account_role = mapping.get(scope.get("account_id")) if kind == "general_ledger" else None
            results.append({
                "id": "ledger_agg_" + digest, "aggregation_id": rule["id"],
                "ledger_kind": kind, "metric": metric, "scope_key": scope_key,
                "business_scope": scope, "values": {rule["output_field"]: str(total)},
                "contributions": unique, "contribution_count": len(unique),
                "evidence_ids": sorted({item["evidence_id"] for item in unique}),
                "account_mapping_status": ("mapped" if account_role else "unmapped")
                    if kind == "general_ledger" else None,
                "account_role": account_role,
                "verification_status": "computed_not_assessed",
            })
        results.sort(key=lambda item: (item["scope_key"], item["id"]))
        outputs.append({
            "schema_version": 1, "aggregation_id": rule["id"], "ledger_kind": kind,
            "results": results, "skipped": skipped,
            "summary": {"groups": len(results),
                        "contributions": sum(item["contribution_count"] for item in results),
                        "skipped": len(skipped)},
            "validation_summary": validated["summary"],
            "policy": {"stock_and_general_ledger_are_never_combined": True,
                       "currency_and_business_dimensions_are_explicit": True,
                       "stock_value_uses_source_ledger_delta": True,
                       "general_ledger_signed_amount_is_debit_minus_credit": True,
                       "unmapped_accounts_are_not_assessed": True,
                       "aggregation_does_not_assess_business_invariants": True},
        })
    return outputs
