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
    semantics = rule.get("transaction_semantics", {})
    if semantics and not isinstance(semantics, dict):
        raise ObservationAggregationError("transaction_semantics must be an object")
    grouped = {}
    seen_observation_ids = set()
    seen_transactions = {}
    conflicted_transactions = set()
    skipped = []
    duplicate_transactions = []
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
        amount = _number(values[field])
        transaction = row.get("transaction", {})
        transaction_provenance = row.get("transaction_provenance", {})
        transaction_identity = {}
        signed_value = amount
        if semantics:
            status_field = semantics.get("status_field")
            return_field = semantics.get("return_flag_field")
            return_reference_field = semantics.get("return_reference_field")
            required_transaction_fields = [status_field, return_field]
            if any(not isinstance(name, str) or not name for name in required_transaction_fields):
                raise ObservationAggregationError("transaction semantics require status and return fields")
            transaction_invalid = False
            for name in required_transaction_fields:
                item = transaction_provenance.get(name) if isinstance(transaction_provenance, dict) else None
                tx_evidence_id = item.get("evidence_id") if isinstance(item, dict) else None
                tx_evidence = evidence_by_id.get(tx_evidence_id)
                tx_locator = _locator_identity(item.get("locator")) if isinstance(item, dict) else ()
                if (not isinstance(transaction, dict) or not isinstance(transaction.get(name), str)
                        or not isinstance(tx_evidence_id, str) or not tx_evidence_id
                        or tx_evidence is None or tx_evidence.get("asset_id") != asset_id
                        or not tx_locator or _locator_identity(tx_evidence.get("locator")) != tx_locator):
                    transaction_invalid = True
                    break
            if transaction_invalid:
                skipped.append({"observation_id": row_id, "reason": "unverified_transaction_metadata"})
                continue
            state = transaction[status_field].strip().casefold()
            posted_values = {str(value).strip().casefold() for value in semantics.get("posted_values", [])}
            non_posted_values = {str(value).strip().casefold() for value in semantics.get("non_posted_values", [])}
            if state not in posted_values:
                reason = "non_posted_transaction_state" if state in non_posted_values else "unrecognized_transaction_state"
                skipped.append({"observation_id": row_id, "reason": reason, "state": transaction[status_field]})
                continue
            return_value = transaction[return_field].strip().casefold()
            return_values = {str(value).strip().casefold() for value in semantics.get("return_values", [])}
            normal_values = {str(value).strip().casefold() for value in semantics.get("normal_values", [])}
            if return_value in return_values:
                reference = transaction.get(return_reference_field) if isinstance(return_reference_field, str) else None
                ref_item = transaction_provenance.get(return_reference_field) if isinstance(transaction_provenance, dict) else None
                ref_id = ref_item.get("evidence_id") if isinstance(ref_item, dict) else None
                ref_evidence = evidence_by_id.get(ref_id)
                ref_locator = _locator_identity(ref_item.get("locator")) if isinstance(ref_item, dict) else ()
                if (not isinstance(reference, str) or not reference.strip()
                        or not isinstance(ref_id, str) or not ref_id
                        or ref_evidence is None or ref_evidence.get("asset_id") != asset_id
                        or not ref_locator or _locator_identity(ref_evidence.get("locator")) != ref_locator):
                    skipped.append({"observation_id": row_id, "reason": "unresolved_return_reference"})
                    continue
                signed_value = -abs(amount)
            elif return_value in normal_values:
                if amount < 0:
                    skipped.append({"observation_id": row_id, "reason": "negative_value_without_return_semantics"})
                    continue
            else:
                skipped.append({"observation_id": row_id, "reason": "unrecognized_return_flag"})
                continue
            deduplicate_by = semantics.get("deduplicate_by", [])
            if not isinstance(deduplicate_by, list) or not deduplicate_by:
                raise ObservationAggregationError("transaction semantics require deduplicate_by fields")
            identity_invalid = False
            for name in deduplicate_by:
                item = scope_provenance.get(name) if isinstance(scope_provenance, dict) else None
                identity_evidence_id = item.get("evidence_id") if isinstance(item, dict) else None
                identity_evidence = evidence_by_id.get(identity_evidence_id)
                identity_locator = _locator_identity(item.get("locator")) if isinstance(item, dict) else ()
                if (not isinstance(scope.get(name), str) or not scope[name].strip()
                        or identity_evidence is None or identity_evidence.get("asset_id") != asset_id
                        or not identity_locator
                        or _locator_identity(identity_evidence.get("locator")) != identity_locator):
                    identity_invalid = True
                    break
                transaction_identity[name] = scope[name]
            if identity_invalid:
                skipped.append({"observation_id": row_id, "reason": "unverified_transaction_identity"})
                continue
            identity_key = tuple(transaction_identity[name] for name in deduplicate_by)
            if identity_key in conflicted_transactions:
                skipped.append({"observation_id": row_id, "reason": "conflicting_duplicate_transaction"})
                continue
            previous = seen_transactions.get(identity_key)
            if previous is not None:
                if previous["value"] == signed_value and previous["group_key"] == key:
                    duplicate_transactions.append({
                        "identity": transaction_identity,
                        "observation_ids": [previous["observation_id"], row_id],
                        "reason": "duplicate_transaction_not_counted_twice"})
                    skipped.append({"observation_id": row_id, "reason": "duplicate_transaction_not_counted_twice"})
                    continue
                prior_group = grouped.get(previous["group_key"], [])
                grouped[previous["group_key"]] = [
                    item for item in prior_group if item["observation_id"] != previous["observation_id"]]
                conflicted_transactions.add(identity_key)
                seen_transactions.pop(identity_key, None)
                skipped.append({"observation_id": previous["observation_id"], "reason": "conflicting_duplicate_transaction"})
                skipped.append({"observation_id": row_id, "reason": "conflicting_duplicate_transaction"})
                continue
            seen_transactions[identity_key] = {
                "observation_id": row_id, "value": signed_value, "group_key": key}
        grouped.setdefault(key, []).append({
            "observation_id": row_id, "asset_id": asset_id,
            "evidence_id": evidence_id, "value": signed_value,
            "field_provenance": provenance[field], "business_scope": key_values,
            "scope_provenance": verified_scope_provenance,
            "transaction_identity": transaction_identity,
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
        "duplicate_transactions": duplicate_transactions,
        "summary": {"groups": len(results),
                    "contributions": sum(item["contribution_count"] for item in results),
                    "skipped": len(skipped),
                    "duplicate_evidence": len(duplicate_evidence),
                    "duplicate_transactions": len(duplicate_transactions)},
        "policy": {"exact_scope_match_required": True,
                   "duplicate_evidence_counted_once": True,
                   "all_contributions_retain_provenance": True,
                   "transaction_states_must_be_explicit": True,
                   "returns_require_original_reference": True,
                   "duplicate_transactions_counted_once": True},
    }
