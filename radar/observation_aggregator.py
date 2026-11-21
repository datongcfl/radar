"""Deterministic cross-asset aggregation for provenance-backed observations.

Aggregation is driven only by explicit Pack declarations. Every contribution
retains its source observation, asset, scope and field-level Evidence.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any, Iterable


class ObservationAggregationError(ValueError):
    """Raised when aggregation input or its declaration is ambiguous."""


def _number(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise ObservationAggregationError("boolean is not an aggregatable number")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ObservationAggregationError("contribution value must be numeric")
    if not result.is_finite():
        raise ObservationAggregationError("contribution value must be finite")
    return result


def _locator_identity(locator: Any) -> tuple:
    if not isinstance(locator, dict):
        return ()
    if locator.get("cell"):
        return ("xlsx", str(locator.get("path", "")), str(locator.get("sheet", "")),
                str(locator.get("cell", "")).upper())
    if "row" in locator and "column" in locator:
        return ("csv", str(locator.get("path", "")), int(locator["row"]), int(locator["column"]))
    return ()


def aggregate_observations(rule: dict[str, Any],
                           observations: Iterable[dict[str, Any]],
                           evidence_records: Iterable[dict[str, Any]] = ()) -> dict[str, Any]:
    """Aggregate one declared numeric field by exact business scope keys.

    rule keys: id, source_invariant_id, source_field, group_by, operation
    (currently only 'sum'), and optional output_field.
    """
    required = ("id", "source_invariant_id", "source_field", "group_by", "operation")
    for key in required:
        if key not in rule:
            raise ObservationAggregationError("aggregation rule missing %s" % key)
    if not isinstance(rule["id"], str) or not rule["id"].strip():
        raise ObservationAggregationError("aggregation id must be non-empty")
    if rule["operation"] != "sum":
        raise ObservationAggregationError("unsupported aggregation operation")
    group_by = rule["group_by"]
    if (not isinstance(group_by, list) or not group_by
            or any(not isinstance(item, str) or not item for item in group_by)
            or len(set(group_by)) != len(group_by)):
        raise ObservationAggregationError("group_by must contain unique non-empty field names")

    evidence_by_id = {item.get("id"): item for item in evidence_records if isinstance(item, dict)}
    grouped = {}
    seen_observation_ids = set()
    skipped = []
    for row in observations:
        if row.get("invariant_id") != rule["source_invariant_id"]:
            continue
        row_id = row.get("id")
        if not isinstance(row_id, str) or not row_id:
            raise ObservationAggregationError("source observation requires id")
        if row_id in seen_observation_ids:
            raise ObservationAggregationError("duplicate source observation id: %s" % row_id)
        seen_observation_ids.add(row_id)
        scope = row.get("business_scope")
        if not isinstance(scope, dict) or any(
                not isinstance(scope.get(field), str) or not scope[field].strip()
                for field in group_by):
            skipped.append({"observation_id": row_id, "reason": "missing_group_key"})
            continue
        values = row.get("values")
        provenance = row.get("field_provenance")
        field = rule["source_field"]
        if not isinstance(values, dict) or field not in values:
            skipped.append({"observation_id": row_id, "reason": "missing_source_value"})
            continue
        if not isinstance(provenance, dict) or not isinstance(provenance.get(field), dict):
            skipped.append({"observation_id": row_id, "reason": "missing_field_provenance"})
            continue
        evidence_id = provenance[field].get("evidence_id")
        asset_id = row.get("asset_id")
        source_evidence = evidence_by_id.get(evidence_id)
        source_locator = _locator_identity(provenance[field].get("locator"))
        if (not isinstance(evidence_id, str) or not evidence_id
                or not isinstance(asset_id, str) or not asset_id
                or source_evidence is None
                or source_evidence.get("asset_id") != asset_id
                or not source_locator
                or _locator_identity(source_evidence.get("locator")) != source_locator):
            skipped.append({"observation_id": row_id, "reason": "unverified_source_field_provenance"})
            continue
        scope_provenance = row.get("scope_provenance")
        verified_scope_provenance = {}
        scope_invalid = False
        for name in group_by:
            item = scope_provenance.get(name) if isinstance(scope_provenance, dict) else None
            scope_evidence_id = item.get("evidence_id") if isinstance(item, dict) else None
            scope_evidence = evidence_by_id.get(scope_evidence_id)
            scope_locator = _locator_identity(item.get("locator")) if isinstance(item, dict) else ()
            if (not isinstance(scope_evidence_id, str) or not scope_evidence_id
                    or scope_evidence is None
                    or scope_evidence.get("asset_id") != asset_id
                    or not scope_locator
                    or _locator_identity(scope_evidence.get("locator")) != scope_locator):
                scope_invalid = True
                break
            verified_scope_provenance[name] = {
                "evidence_id": scope_evidence_id, "locator": item["locator"]}
        if scope_invalid:
            skipped.append({"observation_id": row_id, "reason": "unverified_group_key_provenance"})
            continue
        key_values = {name: scope[name] for name in group_by}
        key = tuple(key_values[name] for name in group_by)
        grouped.setdefault(key, []).append({
            "observation_id": row_id, "asset_id": asset_id,
            "evidence_id": evidence_id, "value": _number(values[field]),
            "field_provenance": provenance[field], "business_scope": key_values,
            "scope_provenance": verified_scope_provenance,
        })

    results = []
    duplicate_evidence = []
    output_field = rule.get("output_field", "aggregated_value")
    for key in sorted(grouped):
        contributions = grouped[key]
        by_evidence = {}
        for item in contributions:
            previous = by_evidence.get(item["evidence_id"])
            if previous is not None:
                duplicate_evidence.append({
                    "evidence_id": item["evidence_id"],
                    "observation_ids": [previous["observation_id"], item["observation_id"]],
                    "reason": "duplicate_evidence_not_counted_twice",
                })
                continue
            by_evidence[item["evidence_id"]] = item
        unique = list(by_evidence.values())
        total = sum((item["value"] for item in unique), Decimal("0"))
        scope = unique[0]["business_scope"]
        scope_key = "|".join("%s=%s" % (name, scope[name]) for name in group_by)
        digest = sha256((rule["id"] + "|" + scope_key).encode("utf-8")).hexdigest()[:20]
        results.append({
            "id": "agg_" + digest, "aggregation_id": rule["id"],
            "scope_key": scope_key, "business_scope": scope,
            "values": {output_field: str(total)},
            "contributions": [{
                "observation_id": item["observation_id"],
                "asset_id": item["asset_id"], "evidence_id": item["evidence_id"],
                "value": str(item["value"]),
                "field_provenance": item["field_provenance"],
                "scope_provenance": item["scope_provenance"],
            } for item in unique],
            "contribution_count": len(unique),
            "evidence_ids": sorted(by_evidence),
        })
    results.sort(key=lambda item: (item["scope_key"], item["id"]))
    return {
        "schema_version": 1, "aggregation_id": rule["id"],
        "results": results, "skipped": skipped,
        "duplicate_evidence": duplicate_evidence,
        "summary": {"groups": len(results),
                    "contributions": sum(item["contribution_count"] for item in results),
                    "skipped": len(skipped),
                    "duplicate_evidence": len(duplicate_evidence)},
        "policy": {"exact_scope_match_required": True,
                   "duplicate_evidence_counted_once": True,
                   "all_contributions_retain_provenance": True},
    }
