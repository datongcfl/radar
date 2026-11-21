"""Deterministic evaluation of Pack-declared business invariants.

Observations are explicit, provenance-backed inputs. This module never mines
runtime values from source text and never upgrades evidence verification state.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Optional


class ObservationError(ValueError):
    """Raised when an observation bundle is malformed or untraceable."""


_ORIGINS = {"runtime", "test", "static_source", "manual"}


def _decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ObservationError("%s must be a finite numeric value" % field)
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ObservationError("%s must be a finite numeric value" % field)
    if not result.is_finite():
        raise ObservationError("%s must be a finite numeric value" % field)
    return result


def validate_observation_bundle(data: dict[str, Any], invariants: Iterable[dict[str, Any]],
                                evidence_records: Optional[Iterable[dict[str, Any]]] = None) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ObservationError("observation bundle schema_version must be 1")
    rows = data.get("observations")
    if not isinstance(rows, list):
        raise ObservationError("observations must be an array")
    invariant_map = {item["id"]: item for item in invariants}
    evidence_map = None if evidence_records is None else {item["id"]: item for item in evidence_records}
    seen = set()
    for index, row in enumerate(rows):
        where = "observations[%d]" % index
        if not isinstance(row, dict):
            raise ObservationError("%s must be an object" % where)
        for key in ("id", "invariant_id", "scope_key", "origin", "values", "field_provenance"):
            if key not in row:
                raise ObservationError("%s missing %s" % (where, key))
        for key in ("id", "invariant_id", "scope_key"):
            if not isinstance(row[key], str) or not row[key].strip():
                raise ObservationError("%s.%s must be a non-empty string" % (where, key))
        if row["id"] in seen:
            raise ObservationError("duplicate observation id: %s" % row["id"])
        seen.add(row["id"])
        invariant = invariant_map.get(row["invariant_id"])
        if invariant is None:
            raise ObservationError("%s references unknown invariant %s" % (where, row["invariant_id"]))
        if not isinstance(row["origin"], str) or row["origin"] not in _ORIGINS:
            raise ObservationError("%s.origin must be one of %s" % (where, ", ".join(sorted(_ORIGINS))))
        values, provenance = row["values"], row["field_provenance"]
        if not isinstance(values, dict) or not isinstance(provenance, dict):
            raise ObservationError("%s values and field_provenance must be objects" % where)
        required_fields = list(invariant["fields"])
        target = invariant.get("target_field")
        if target and target not in required_fields:
            required_fields.append(target)
        missing = sorted(set(required_fields) - set(values))
        if missing:
            raise ObservationError("%s missing values: %s" % (where, ", ".join(missing)))
        missing_provenance = sorted(set(required_fields) - set(provenance))
        if missing_provenance:
            raise ObservationError("%s missing field provenance: %s" %
                                   (where, ", ".join(missing_provenance)))
        if set(values) - set(required_fields):
            raise ObservationError("%s contains undeclared value fields" % where)
        for field in required_fields:
            item = provenance[field]
            if (not isinstance(item, dict) or not isinstance(item.get("evidence_id"), str)
                    or not item.get("evidence_id").strip()):
                raise ObservationError("%s.%s requires evidence_id provenance" % (where, field))
            locator = item.get("locator")
            locator_keys = {"path", "url", "field", "cell", "page", "sheet", "slide",
                            "line_start", "row", "paragraph", "table"}
            if not isinstance(locator, dict) or not locator_keys.intersection(locator):
                raise ObservationError("%s.%s requires a precise locator" % (where, field))
            if evidence_map is not None:
                source = evidence_map.get(item["evidence_id"])
                if source is None:
                    raise ObservationError("%s.%s references unknown Evidence %s" %
                                           (where, field, item["evidence_id"]))
                source_verification = (source.get("metadata") or {}).get("verification", {})
                declared_runtime = bool(item.get("runtime_observed", False))
                actual_runtime = bool(source_verification.get("runtime_observed", False))
                if declared_runtime != actual_runtime:
                    raise ObservationError("%s.%s runtime flag conflicts with Evidence" % (where, field))
                level = item.get("verification_level")
                actual_level = source_verification.get("level", "unknown")
                if level is not None and level != actual_level:
                    raise ObservationError("%s.%s verification level conflicts with Evidence" %
                                           (where, field))
            else:
                declared_runtime = bool(item.get("runtime_observed", False))
            if row["origin"] == "runtime" and (
                    not declared_runtime or item.get("verification_level") not in
                    ("runtime_observation", "runtime_verified")):
                raise ObservationError("%s runtime observation requires runtime-backed Evidence" % where)
            if row["origin"] != "runtime" and declared_runtime:
                raise ObservationError("%s non-runtime observation cannot claim runtime Evidence" % where)
            if row["origin"] == "test" and item.get("verification_level") not in (
                    "ci_check_success", "commit_status_success", "test_result", "test_fixture"):
                raise ObservationError("%s test observation requires test-backed Evidence" % where)
        if row["origin"] == "static_source":
            for field in required_fields:
                level = provenance[field].get("verification_level", "")
                if level and level not in ("static_source", "document_text", "unknown"):
                    raise ObservationError("%s static_source has incompatible verification level" % where)
    return rows


def _evaluate_one(invariant: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    operator = invariant["operator"]
    fields = list(invariant["fields"])
    values = row["values"]
    tolerance = _decimal(invariant.get("tolerance", 0), "tolerance")
    computed = None
    delta = None
    if operator in ("sum_equals", "multiplication_equals", "less_than_or_equal",
                    "equal_with_tolerance"):
        operand_fields = fields
        if operator in ("sum_equals", "multiplication_equals") and invariant.get("target_field") in fields:
            operand_fields = [field for field in fields if field != invariant["target_field"]]
        numbers = {field: _decimal(values[field], field) for field in operand_fields}
        if operator == "sum_equals":
            actual = sum(numbers.values(), Decimal("0"))
            expected = _decimal(values[invariant["target_field"]], invariant["target_field"])
            delta = actual - expected
            passed = abs(delta) <= tolerance
            computed = {"calculated": str(actual), "expected": str(expected)}
        elif operator == "multiplication_equals":
            actual = Decimal("1")
            for number in numbers.values():
                actual *= number
            expected = _decimal(values[invariant["target_field"]], invariant["target_field"])
            delta = actual - expected
            passed = abs(delta) <= tolerance
            computed = {"calculated": str(actual), "expected": str(expected)}
        elif operator == "less_than_or_equal":
            left, right = numbers[fields[0]], numbers[fields[1]]
            passed = left <= right
            delta = left - right
            computed = {"left": str(left), "right": str(right)}
        else:
            left, right = numbers[fields[0]], numbers[fields[1]]
            delta = left - right
            passed = abs(delta) <= tolerance
            computed = {"left": str(left), "right": str(right)}
    elif operator == "separate_fields":
        names = [values[field] for field in fields]
        if not all(isinstance(value, str) and value.strip() for value in names):
            raise ObservationError("separate_fields values must be non-empty field paths")
        passed = len(set(names)) == len(names)
        computed = {"field_paths": names, "distinct": passed}
    else:
        raise ObservationError("unsupported invariant operator: %s" % operator)

    origin_levels = {"runtime": "runtime_observed", "test": "test_fixture",
                     "static_source": "static_candidate", "manual": "manual_unverified"}
    return {
        "id": row["id"], "invariant_id": invariant["id"], "scope_key": row["scope_key"],
        "outcome": "pass" if passed else "fail",
        "verification_level": origin_levels[row["origin"]],
        "origin": row["origin"], "computed": computed,
        "delta": str(delta) if delta is not None else None,
        "tolerance": str(tolerance),
        "field_provenance": row["field_provenance"],
        "evidence_ids": sorted(set(item["evidence_id"] for item in row["field_provenance"].values())),
        "captured_at": row.get("captured_at"),
    }


def evaluate_business_invariants(invariants: Iterable[dict[str, Any]],
                                 observation_bundle: Optional[dict[str, Any]],
                                 evidence_records: Optional[Iterable[dict[str, Any]]] = None) -> dict[str, Any]:
    invariant_rows = list(invariants)
    if observation_bundle is None:
        rows = []
    else:
        rows = validate_observation_bundle(observation_bundle, invariant_rows, evidence_records)
    by_id = {item["id"]: item for item in invariant_rows}
    evaluations = []
    for row in rows:
        evaluations.append(_evaluate_one(by_id[row["invariant_id"]], row))
    summaries = []
    for invariant in invariant_rows:
        matches = [item for item in evaluations if item["invariant_id"] == invariant["id"]]
        outcomes = {item["outcome"] for item in matches}
        status = ("no_observation" if not matches else
                  "mixed" if len(outcomes) > 1 else
                  "passed" if outcomes == {"pass"} else "failed")
        summaries.append({"invariant_id": invariant["id"], "status": status,
                          "observation_count": len(matches),
                          "pass_count": sum(1 for item in matches if item["outcome"] == "pass"),
                          "fail_count": sum(1 for item in matches if item["outcome"] == "fail")})
    evaluations.sort(key=lambda item: (item["invariant_id"], item["scope_key"], item["id"]))
    summaries.sort(key=lambda item: item["invariant_id"])
    return {"schema_version": 1, "evaluations": evaluations, "summary": summaries,
            "policy": {"observations_require_evidence_provenance": True,
                       "runtime_verification_requires_runtime_evidence": True,
                       "calculation_does_not_upgrade_evidence": True,
                       "no_observation_does_not_mean_pass_or_fail": True}}
