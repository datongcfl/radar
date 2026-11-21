"""Pack-driven business graph projection; derived views, not core domain records."""
from __future__ import annotations
from hashlib import sha256
import math
import json
from typing import Any, Iterable, Optional

from .business_invariants import evaluate_business_invariants
from .observation_aggregator import aggregate_observations, ObservationAggregationError

class BusinessModelError(ValueError):
    """Invalid declarative business model."""

def _strings(value: Any, field: str, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise BusinessModelError("%s must be a %sarray" % (field, "non-empty " if not allow_empty else ""))
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise BusinessModelError("%s must contain non-empty strings" % field)
    return value

def validate_business_model(data: dict[str, Any], pack: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate a safe, data-only model. No executable expressions are accepted."""
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise BusinessModelError("business model schema_version must be 1")
    for collection in ("entities", "processes", "exceptions"):
        if not isinstance(data.get(collection), list) or not data[collection]:
            raise BusinessModelError("business model %s must be a non-empty array" % collection)
    for field in ("pack", "pack_version", "version", "entities", "processes", "exceptions"):
        if field not in data:
            raise BusinessModelError("business model missing %s" % field)
    if pack and (data["pack"] != pack["pack"] or str(data["pack_version"]) != str(pack["version"])):
        raise BusinessModelError("business model pack identity/version does not match Pack")
    if not all(isinstance(data[k], str) and data[k].strip() for k in ("pack", "pack_version", "version")):
        raise BusinessModelError("business model pack/version fields must be non-empty strings")
    entity_ids: set[str] = set()
    for i, entity in enumerate(data["entities"]):
        where = "entities[%d]" % i
        if not isinstance(entity, dict):
            raise BusinessModelError("%s must be an object" % where)
        for key in ("id", "name", "aliases", "description", "key_fields", "evidence_terms", "risk_notes"):
            if key not in entity: raise BusinessModelError("%s missing %s" % (where, key))
        _strings([entity["id"], entity["name"], entity["description"]], where)
        _strings(entity["aliases"], where + ".aliases")
        _strings(entity["key_fields"], where + ".key_fields", allow_empty=True)
        _strings(entity["evidence_terms"], where + ".evidence_terms")
        _strings(entity["risk_notes"], where + ".risk_notes", allow_empty=True)
        if entity["id"] in entity_ids: raise BusinessModelError("duplicate entity id: %s" % entity["id"])
        entity_ids.add(entity["id"])
    process_ids: set[str] = set()
    for i, process in enumerate(data["processes"]):
        where = "processes[%d]" % i
        if not isinstance(process, dict): raise BusinessModelError("%s must be an object" % where)
        for key in ("id", "name", "description", "steps", "transitions"):
            if key not in process: raise BusinessModelError("%s missing %s" % (where, key))
        _strings([process["id"], process["name"], process["description"]], where)
        _strings(process["steps"], where + ".steps")
        if not isinstance(process["transitions"], list) or not process["transitions"]:
            raise BusinessModelError("%s.transitions must be a non-empty array" % where)
        if process["id"] in process_ids: raise BusinessModelError("duplicate process id: %s" % process["id"])
        process_ids.add(process["id"])
        if any(step not in entity_ids for step in process["steps"]):
            raise BusinessModelError("%s.steps references an unknown entity" % where)
        for j, transition in enumerate(process["transitions"]):
            tw = "%s.transitions[%d]" % (where, j)
            if not isinstance(transition, dict): raise BusinessModelError("%s must be an object" % tw)
            for key in ("from", "to", "condition", "required_evidence"):
                if key not in transition: raise BusinessModelError("%s missing %s" % (tw, key))
            if transition["from"] not in entity_ids or transition["to"] not in entity_ids:
                raise BusinessModelError("%s references an unknown entity" % tw)
            _strings([transition["condition"]], tw)
            _strings(transition["required_evidence"], tw + ".required_evidence")
    exception_ids: set[str] = set()
    for i, exception in enumerate(data["exceptions"]):
        where = "exceptions[%d]" % i
        if not isinstance(exception, dict): raise BusinessModelError("%s must be an object" % where)
        for key in ("id", "name", "description", "aliases", "evidence_terms", "related_entities", "expected_evidence", "risk"):
            if key not in exception: raise BusinessModelError("%s missing %s" % (where, key))
        _strings([exception["id"], exception["name"], exception["description"], exception["risk"]], where)
        for key in ("aliases", "evidence_terms", "related_entities", "expected_evidence"):
            _strings(exception[key], where + "." + key)
        if exception["id"] in exception_ids: raise BusinessModelError("duplicate exception id: %s" % exception["id"])
        exception_ids.add(exception["id"])
        unknown = sorted(set(exception["related_entities"]) - entity_ids)
        if unknown: raise BusinessModelError("%s references unknown entities: %s" % (where, ", ".join(unknown)))
    invariants = data.get("invariants", [])
    if not isinstance(invariants, list):
        raise BusinessModelError("business model invariants must be an array")
    invariant_ids: set[str] = set()
    allowed_operators = {"sum_equals", "less_than_or_equal", "multiplication_equals",
                         "equal_with_tolerance", "separate_fields"}
    for i, invariant in enumerate(invariants):
        where = "invariants[%d]" % i
        if not isinstance(invariant, dict):
            raise BusinessModelError("%s must be an object" % where)
        for key in ("id", "name", "description", "operator", "scope", "fields",
                    "related_entities", "required_evidence", "risk"):
            if key not in invariant:
                raise BusinessModelError("%s missing %s" % (where, key))
        _strings([invariant["id"], invariant["name"], invariant["description"],
                  invariant["scope"], invariant["risk"]], where)
        if invariant["operator"] not in allowed_operators:
            raise BusinessModelError("%s has unsupported operator" % where)
        _strings(invariant["fields"], where + ".fields")
        _strings(invariant["related_entities"], where + ".related_entities")
        _strings(invariant["required_evidence"], where + ".required_evidence")
        if invariant["id"] in invariant_ids:
            raise BusinessModelError("duplicate invariant id: %s" % invariant["id"])
        invariant_ids.add(invariant["id"])
        unknown = sorted(set(invariant["related_entities"]) - entity_ids)
        if unknown:
            raise BusinessModelError("%s references unknown entities: %s" % (where, ", ".join(unknown)))
        if "tolerance" in invariant and (
                isinstance(invariant["tolerance"], bool)
                or not isinstance(invariant["tolerance"], (int, float))
                or not math.isfinite(invariant["tolerance"])
                or invariant["tolerance"] < 0):
            raise BusinessModelError("%s.tolerance must be a finite non-negative number" % where)
        if len(set(invariant["fields"])) != len(invariant["fields"]):
            raise BusinessModelError("%s.fields must be unique" % where)
        aliases = invariant.get("field_aliases")
        normalized_aliases = {}
        if aliases is not None:
            if not isinstance(aliases, dict):
                raise BusinessModelError("%s.field_aliases must be an object" % where)
            allowed_alias_fields = set(invariant["fields"])
            if invariant.get("target_field"):
                allowed_alias_fields.add(invariant["target_field"])
            if set(aliases) - allowed_alias_fields:
                raise BusinessModelError("%s.field_aliases references undeclared fields" % where)
            for alias_field, alias_values in aliases.items():
                if not isinstance(alias_values, list) or not alias_values:
                    raise BusinessModelError("%s.field_aliases.%s must be a non-empty array" %
                                             (where, alias_field))
                _strings(alias_values, where + ".field_aliases." + alias_field)
                for alias in alias_values:
                    normalized = "".join(char.casefold() for char in alias
                                         if char.isalnum())
                    if (not normalized or
                            (normalized in normalized_aliases and normalized_aliases[normalized] != alias_field)):
                        raise BusinessModelError("%s.field_aliases contains empty or ambiguous aliases" % where)
                    normalized_aliases[normalized] = alias_field
        scope_fields = invariant.get("scope_fields", [])
        if not isinstance(scope_fields, list):
            raise BusinessModelError("%s.scope_fields must be an array" % where)
        _strings(scope_fields, where + ".scope_fields", allow_empty=True)
        if len(set(scope_fields)) != len(scope_fields):
            raise BusinessModelError("%s.scope_fields must be unique" % where)
        transaction_fields = invariant.get("transaction_fields", {})
        if not isinstance(transaction_fields, dict):
            raise BusinessModelError("%s.transaction_fields must be an object" % where)
        for transaction_field, aliases_for_transaction in transaction_fields.items():
            if not isinstance(transaction_field, str) or not transaction_field:
                raise BusinessModelError("%s has invalid transaction field" % where)
            if not isinstance(aliases_for_transaction, list) or not aliases_for_transaction:
                raise BusinessModelError("%s.transaction_fields.%s must be a non-empty array" %
                                         (where, transaction_field))
            _strings(aliases_for_transaction, where + ".transaction_fields." + transaction_field)
            for alias in aliases_for_transaction:
                normalized = "".join(char.casefold() for char in alias if char.isalnum())
                if (not normalized or
                        (normalized in normalized_aliases and normalized_aliases[normalized] != transaction_field)):
                    raise BusinessModelError("%s transaction aliases are ambiguous" % where)
                normalized_aliases[normalized] = transaction_field
        scope_aliases = invariant.get("scope_aliases", {})
        if not isinstance(scope_aliases, dict):
            raise BusinessModelError("%s.scope_aliases must be an object" % where)
        if set(scope_aliases) - set(scope_fields):
            raise BusinessModelError("%s.scope_aliases references undeclared scope fields" % where)
        for alias_field, alias_values in scope_aliases.items():
            if not isinstance(alias_values, list) or not alias_values:
                raise BusinessModelError("%s.scope_aliases.%s must be a non-empty array" %
                                         (where, alias_field))
            _strings(alias_values, where + ".scope_aliases." + alias_field)
            for alias in alias_values:
                normalized = "".join(char.casefold() for char in alias if char.isalnum())
                if (not normalized or
                        (normalized in normalized_aliases and normalized_aliases[normalized] != alias_field)):
                    raise BusinessModelError("%s field and scope aliases are ambiguous" % where)
                normalized_aliases[normalized] = alias_field
        if invariant.get("target_field") is not None and (
                not isinstance(invariant["target_field"], str) or not invariant["target_field"].strip()):
            raise BusinessModelError("%s.target_field must be a non-empty string" % where)
        operator = invariant["operator"]
        field_count = len(invariant["fields"])
        expected_counts = {"less_than_or_equal": (2, 2), "equal_with_tolerance": (2, 2),
                           "separate_fields": (2, 1000)}
        if operator in expected_counts:
            low, high = expected_counts[operator]
            if not low <= field_count <= high:
                raise BusinessModelError("%s.fields has invalid length for %s" % (where, operator))
        if operator in ("sum_equals", "multiplication_equals"):
            if not invariant.get("target_field"):
                raise BusinessModelError("%s.target_field is required for this operator" % where)
            operands = [field for field in invariant["fields"]
                        if field != invariant["target_field"]]
            minimum = 1 if operator == "sum_equals" else 2
            if len(operands) < minimum:
                raise BusinessModelError("%s.fields must declare at least %d operands" %
                                         (where, minimum))
    aggregations = data.get("aggregations", [])
    if not isinstance(aggregations, list):
        raise BusinessModelError("business model aggregations must be an array")
    aggregation_ids: set[str] = set()
    invariant_map = {item["id"]: item for item in invariants}
    for i, rule in enumerate(aggregations):
        where = "aggregations[%d]" % i
        if not isinstance(rule, dict):
            raise BusinessModelError("%s must be an object" % where)
        for key in ("id", "source_invariant_id", "source_field", "group_by", "operation", "output_field"):
            if key not in rule:
                raise BusinessModelError("%s missing %s" % (where, key))
        _strings([rule["id"], rule["source_invariant_id"], rule["source_field"],
                  rule["operation"], rule["output_field"]], where)
        if rule["id"] in aggregation_ids:
            raise BusinessModelError("duplicate aggregation id: %s" % rule["id"])
        aggregation_ids.add(rule["id"])
        if rule["operation"] != "sum":
            raise BusinessModelError("%s has unsupported operation" % where)
        _strings(rule["group_by"], where + ".group_by")
        if len(set(rule["group_by"])) != len(rule["group_by"]):
            raise BusinessModelError("%s.group_by must be unique" % where)
        source = invariant_map.get(rule["source_invariant_id"])
        if source is None:
            raise BusinessModelError("%s references unknown source invariant" % where)
        valid_fields = set(source["fields"])
        if source.get("target_field"):
            valid_fields.add(source["target_field"])
        if rule["source_field"] not in valid_fields:
            raise BusinessModelError("%s.source_field is not declared by source invariant" % where)
        declared_scope = set(source.get("scope_fields", []))
        if set(rule["group_by"]) - declared_scope:
            raise BusinessModelError("%s.group_by references undeclared source scope fields" % where)
        semantics = rule.get("transaction_semantics")
        if semantics is not None:
            if not isinstance(semantics, dict):
                raise BusinessModelError("%s.transaction_semantics must be an object" % where)
            for key in ("status_field", "posted_values", "non_posted_values",
                        "return_flag_field", "return_values", "normal_values",
                        "return_reference_field", "deduplicate_by"):
                if key not in semantics:
                    raise BusinessModelError("%s.transaction_semantics missing %s" % (where, key))
            transaction_fields = set(source.get("transaction_fields", {}))
            for key in ("status_field", "return_flag_field", "return_reference_field"):
                if semantics[key] not in transaction_fields:
                    raise BusinessModelError("%s transaction semantics references undeclared transaction field" % where)
            for key in ("posted_values", "non_posted_values", "return_values", "normal_values"):
                _strings(semantics[key], where + ".transaction_semantics." + key)
                if not semantics[key]:
                    raise BusinessModelError("%s.transaction_semantics.%s cannot be empty" % (where, key))
            _strings(semantics["deduplicate_by"], where + ".transaction_semantics.deduplicate_by")
            if not semantics["deduplicate_by"] or set(semantics["deduplicate_by"]) - declared_scope:
                raise BusinessModelError("%s deduplicate_by must reference declared scope fields" % where)
    return data

def _node_id(kind: str, key: str) -> str:
    return "%s_%s" % (kind, sha256(key.encode("utf-8")).hexdigest()[:20])

def _edge_id(edge: dict[str, Any]) -> str:
    raw = json.dumps(edge, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "edge_" + sha256(raw.encode("utf-8")).hexdigest()[:24]

def _add_edge(edges: list[dict[str, Any]], source: str, target: str, relation: str,
              rule_id: str, provenance: dict[str, Any], status: str,
              confidence: float, evidence_ids: Optional[list[str]] = None,
              matched_terms: Optional[list[str]] = None) -> None:
    edge = {"source": source, "target": target, "relation": relation, "rule_id": rule_id,
            "status": status, "confidence": confidence, "evidence_ids": sorted(evidence_ids or []),
            "matched_terms": sorted(set(matched_terms or [])), "provenance": provenance}
    edge["id"] = _edge_id(edge)
    edges.append(edge)

def _contains(text: str, term: str) -> bool:
    return term.casefold() in text.casefold()

def build_business_graph(model: dict[str, Any], pack: dict[str, Any],
                         requirements: Iterable[dict[str, Any]] = (),
                         assets: Iterable[dict[str, Any]] = (),
                         evidence: Iterable[dict[str, Any]] = (),
                         model_digest: Optional[str] = None,
                         workspace_id: Optional[str] = None,
                         discovery_runs: Iterable[dict[str, Any]] = (),
                         relationships: Iterable[dict[str, Any]] = (),
                         observations: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Build a deterministic, provenance-carrying projection from Pack + discovered records."""
    validate_business_model(model, pack)
    requirements, assets, evidence = list(requirements), list(assets), list(evidence)
    discovery_runs = list(discovery_runs)
    relationships = list(relationships)
    invariant_results = evaluate_business_invariants(
        model.get("invariants", []), observations, evidence_records=evidence)
    aggregation_results = []
    try:
        if observations is not None:
            for rule in model.get("aggregations", []):
                aggregation_results.append(aggregate_observations(
                    rule, observations.get("observations", []), evidence_records=evidence))
    except ObservationAggregationError as exc:
        raise BusinessModelError("observation aggregation failed: %s" % exc)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    entity_nodes: dict[str, str] = {}
    def node(kind: str, stable_key: str, **fields: Any) -> str:
        nid = _node_id(kind, stable_key)
        nodes.append({"id": nid, "kind": kind, **fields})
        return nid
    for entity in model["entities"]:
        entity_nodes[entity["id"]] = node("business_entity", entity["id"], business_id=entity["id"],
            name=entity["name"], aliases=entity["aliases"], key_fields=entity["key_fields"],
            risk_notes=entity["risk_notes"])
    for process in model["processes"]:
        pid = node("business_process", process["id"], business_id=process["id"],
                   name=process["name"], description=process["description"])
        for step_index, entity_id in enumerate(process["steps"]):
            _add_edge(edges, pid, entity_nodes[entity_id], "has_step",
                "%s.S%02d" % (process["id"], step_index + 1),
                {"source":"industry_pack","pack":model["pack"],
                 "business_model_version":model["version"],"process_id":process["id"],
                 "step_order":step_index + 1},
                "declared_not_verified", 1.0)
        for index, transition in enumerate(process["transitions"]):
            _add_edge(edges, entity_nodes[transition["from"]], entity_nodes[transition["to"]],
                "declared_transition", "%s.T%02d" % (process["id"], index + 1),
                {"source":"industry_pack","pack":model["pack"],"business_model_version":model["version"],
                 "process_id":process["id"],"process_node_id":pid,"condition":transition["condition"],
                 "required_evidence":transition["required_evidence"]},
                "declared_not_verified", 1.0)
    exception_nodes = {}
    for exception in model["exceptions"]:
        xid = node("business_exception", exception["id"], business_id=exception["id"],
            name=exception["name"], description=exception["description"],
            expected_evidence=exception["expected_evidence"], risk=exception["risk"])
        exception_nodes[exception["id"]] = xid
        for entity_id in exception["related_entities"]:
            _add_edge(edges, xid, entity_nodes[entity_id], "affects_entity", exception["id"] + ".REL",
                {"source":"industry_pack","pack":model["pack"],"business_model_version":model["version"]},
                "declared_not_verified", 1.0)
    invariant_nodes = {}
    for invariant in model.get("invariants", []):
        iid = node("business_invariant", invariant["id"], business_id=invariant["id"],
            name=invariant["name"], description=invariant["description"],
            operator=invariant["operator"], scope=invariant["scope"],
            fields=invariant["fields"], target_field=invariant.get("target_field"),
            tolerance=invariant.get("tolerance"),
            required_evidence=invariant["required_evidence"], risk=invariant["risk"],
            verification_status="declared_not_verified")
        invariant_nodes[invariant["id"]] = iid
        for entity_id in invariant["related_entities"]:
            _add_edge(edges, iid, entity_nodes[entity_id], "constrains_entity",
                "INVARIANT.ENTITY_SCOPE",
                {"source":"industry_pack","pack":model["pack"],
                 "business_model_version":model["version"],"invariant_id":invariant["id"]},
                "declared_not_verified", 1.0)

    asset_nodes = {}
    evidence_entities: dict[str, set[str]] = {}
    evidence_exceptions: dict[str, set[str]] = {}
    evidence_by_asset: dict[str, set[str]] = {}
    assets_by_id = {item["id"]: item for item in assets}
    for asset in assets:
        aid = asset["id"]
        asset_nodes[aid] = node("asset", aid, record_id=aid, title=asset.get("title", ""),
            asset_type=asset.get("asset_type", "other"), uri=asset.get("uri", ""),
            version_ref=asset.get("version_ref"))
    for ev in evidence:
        eid = ev["id"]
        enode = node("evidence", eid, record_id=eid, statement=ev.get("statement", ""),
            locator=ev.get("locator", {}), verification_status=ev.get("verification_status", "unverified"),
            verification_level=(ev.get("metadata") or {}).get("verification", {}).get("level", "unknown"),
            runtime_observed=(ev.get("metadata") or {}).get("verification", {}).get("runtime_observed", False),
            asset_id=ev.get("asset_id"))
        asset_node = asset_nodes.get(ev.get("asset_id"))
        if asset_node:
            _add_edge(edges, enode, asset_node, "located_in", "CORE.EVIDENCE_ASSET",
                {"source":"discovery_record","evidence_id":eid,"asset_id":ev.get("asset_id"),
                 "locator":ev.get("locator", {})}, "source_backed", 1.0, [eid])
        analysis = (ev.get("metadata") or {}).get("code_analysis") or {}
        if analysis.get("kind") == "state_transition_candidate":
            state_node = node("code_state_transition", eid, evidence_id=eid,
                from_state=analysis.get("from_state"), to_state=analysis.get("to_state"),
                scope=analysis.get("scope", []), target=analysis.get("target"),
                inference_status="candidate_only", locator=ev.get("locator", {}))
            _add_edge(edges, enode, state_node, "observes_candidate_state_transition",
                "PYTHON.AST.GUARDED_STATUS_ASSIGNMENT",
                {"source":"stdlib_python_ast","evidence_id":eid,
                 "guard_line":analysis.get("guard_line"),
                 "assignment_line":analysis.get("assignment_line")},
                "candidate_only", 0.75, [eid])
        asset = assets_by_id.get(ev.get("asset_id"), {})
        evidence_by_asset.setdefault(ev.get("asset_id"), set()).add(eid)
        evidence_entities[eid] = set()
        evidence_exceptions[eid] = set()
        haystack = " ".join(str(x or "") for x in
            (ev.get("statement"), ev.get("excerpt"), asset.get("title"), asset.get("uri")))
        for entity in model["entities"]:
            terms = entity["evidence_terms"] + entity["aliases"] + [entity["name"]]
            matched = [term for term in terms if _contains(haystack, term)]
            if matched:
                evidence_entities[eid].add(entity["id"])
                _add_edge(edges, enode, entity_nodes[entity["id"]], "candidate_mention",
                    "ENTITY.TERM_MATCH", {"source":"evidence_text","evidence_id":eid,
                    "asset_id":ev.get("asset_id"),"locator":ev.get("locator",{}),
                    "matching_policy":"casefold_substring"}, "candidate_only", 0.5, [eid], matched)
        for exception in model["exceptions"]:
            terms = exception["evidence_terms"] + exception["aliases"] + [exception["name"]]
            matched = [term for term in terms if _contains(haystack, term)]
            if matched:
                evidence_exceptions[eid].add(exception["id"])
                _add_edge(edges, enode, exception_nodes[exception["id"]],
                    "candidate_exception_mention", "EXCEPTION.TERM_MATCH",
                    {"source":"evidence_text","evidence_id":eid,"asset_id":ev.get("asset_id"),
                     "locator":ev.get("locator",{}),"matching_policy":"casefold_substring"},
                    "candidate_only", 0.5, [eid], matched)
    invariant_evaluation_nodes = {}
    for evaluation in invariant_results["evaluations"]:
        evaluation_node = node("invariant_evaluation", evaluation["id"],
            record_id=evaluation["id"], invariant_id=evaluation["invariant_id"],
            scope_key=evaluation["scope_key"], outcome=evaluation["outcome"],
            verification_level=evaluation["verification_level"], origin=evaluation["origin"],
            computed=evaluation["computed"], delta=evaluation["delta"],
            tolerance=evaluation["tolerance"], evidence_ids=evaluation["evidence_ids"])
        invariant_evaluation_nodes[evaluation["id"]] = evaluation_node
        _add_edge(edges, evaluation_node, invariant_nodes[evaluation["invariant_id"]],
            "evaluates_invariant", "INVARIANT.EVALUATION",
            {"source":"structured_observation","observation_id":evaluation["id"],
             "verification_level":evaluation["verification_level"]},
            "computed_not_assessed", 1.0, evaluation["evidence_ids"])
        evidence_ids = {item["id"] for item in evidence}
        for evidence_id in evaluation["evidence_ids"]:
            if evidence_id in evidence_ids:
                _add_edge(edges, evaluation_node, _node_id("evidence", evidence_id),
                    "derived_from_observation", "INVARIANT.OBSERVATION_EVIDENCE",
                    {"source":"observation_field_provenance","observation_id":evaluation["id"],
                     "evidence_id":evidence_id,
                     "field_provenance":evaluation["field_provenance"]},
                    "source_backed", 1.0, [evidence_id])

    aggregation_node_ids = {}
    for result in aggregation_results:
        rule_id = result["aggregation_id"]
        rule = next(item for item in model.get("aggregations", []) if item["id"] == rule_id)
        for aggregate in result["results"]:
            aid = node("business_aggregation", aggregate["id"],
                record_id=aggregate["id"], aggregation_id=rule_id,
                source_invariant_id=rule["source_invariant_id"],
                operation=rule["operation"], scope_key=aggregate["scope_key"],
                business_scope=aggregate["business_scope"], values=aggregate["values"],
                contribution_count=aggregate["contribution_count"],
                evidence_ids=aggregate["evidence_ids"],
                verification_status="computed_not_assessed")
            aggregation_node_ids[aggregate["id"]] = aid
            for contribution in aggregate["contributions"]:
                evidence_id = contribution["evidence_id"]
                if evidence_id in {item["id"] for item in evidence}:
                    _add_edge(edges, aid, _node_id("evidence", evidence_id),
                        "aggregated_from_evidence", "AGGREGATION.EVIDENCE_PROVENANCE",
                        {"source":"observation_aggregation",
                         "aggregation_id":rule_id,
                         "observation_id":contribution["observation_id"],
                         "asset_id":contribution["asset_id"],
                         "field_provenance":contribution["field_provenance"]},
                        "source_backed", 1.0, [evidence_id])
                for scope_field, scope_source in contribution["scope_provenance"].items():
                    scope_evidence_id = scope_source["evidence_id"]
                    if scope_evidence_id in {item["id"] for item in evidence}:
                        _add_edge(edges, aid, _node_id("evidence", scope_evidence_id),
                            "grouped_by_evidence", "AGGREGATION.SCOPE_PROVENANCE",
                            {"source":"observation_aggregation",
                             "aggregation_id":rule_id,
                             "observation_id":contribution["observation_id"],
                             "asset_id":contribution["asset_id"],
                             "scope_field":scope_field,
                             "locator":scope_source["locator"]},
                            "source_backed", 1.0, [scope_evidence_id])
                for transaction_field, tx_source in contribution.get("transaction_provenance", {}).items():
                    tx_evidence_id = tx_source["evidence_id"]
                    if tx_evidence_id in {item["id"] for item in evidence}:
                        _add_edge(edges, aid, _node_id("evidence", tx_evidence_id),
                            "transaction_metadata_evidence", "AGGREGATION.TRANSACTION_PROVENANCE",
                            {"source":"observation_aggregation",
                             "aggregation_id":rule_id,
                             "observation_id":contribution["observation_id"],
                             "asset_id":contribution["asset_id"],
                             "transaction_field":transaction_field,
                             "transaction_value":contribution["transaction"].get(transaction_field),
                             "locator":tx_source["locator"]},
                            "source_backed", 1.0, [tx_evidence_id])
                if contribution["asset_id"] in asset_nodes:
                    _add_edge(edges, aid, asset_nodes[contribution["asset_id"]],
                        "aggregated_from_asset", "AGGREGATION.ASSET_PROVENANCE",
                        {"source":"observation_aggregation",
                         "aggregation_id":rule_id,
                         "observation_id":contribution["observation_id"]},
                        "source_backed", 1.0, [evidence_id])

    # Reconstruct only candidate cross-file transitions when a typed Asset relationship
    # connects evidence-bearing assets that mention the declared source/target entities.
    transition_rows = [(p, t) for p in model["processes"] for t in p["transitions"]]
    allowed_asset_relations = {"depends_on", "derived_from", "tests", "fixes", "implements", "supports"}
    for relation in relationships:
        left, right = relation.get("from", {}), relation.get("to", {})
        if (left.get("object_type") != "asset" or right.get("object_type") != "asset"
                or relation.get("relation_type") not in allowed_asset_relations
                or relation.get("status", "active") != "active"):
            continue
        left_id, right_id = left.get("id"), right.get("id")
        if left_id not in assets_by_id or right_id not in assets_by_id:
            continue
        left_evidence = evidence_by_asset.get(left_id, set())
        right_evidence = evidence_by_asset.get(right_id, set())
        for process, transition in transition_rows:
            source_ids = sorted(eid for eid in left_evidence
                                if transition["from"] in evidence_entities.get(eid, set()))
            target_ids = sorted(eid for eid in right_evidence
                                if transition["to"] in evidence_entities.get(eid, set()))
            if source_ids and target_ids:
                used_evidence = sorted(set(source_ids + target_ids))
                _add_edge(edges, entity_nodes[transition["from"]], entity_nodes[transition["to"]],
                    "candidate_transition", "CROSS_FILE.DECLARED_TRANSITION",
                    {"source":"asset_relationship_and_evidence_mentions",
                     "relationship_id":relation.get("id"),"relationship_type":relation.get("relation_type"),
                     "source_asset_id":left_id,"target_asset_id":right_id,
                     "process_id":process["id"],"matching_policy":"typed_asset_link_plus_entity_terms"},
                    "candidate_only", 0.6, used_evidence)

    criterion_summaries = []
    for requirement in requirements:
        rid = node("requirement", requirement["id"], record_id=requirement["id"],
            key=requirement.get("key"), version=requirement.get("version"), title=requirement.get("title"))
        for criterion in requirement.get("acceptance_criteria", []):
            cid = node("acceptance_criterion", requirement["id"] + ":" + criterion["id"],
                requirement_id=requirement["id"], criterion_id=criterion["id"],
                description=criterion["description"], required=criterion["required"])
            _add_edge(edges, rid, cid, "has_criterion", "CORE.REQUIREMENT_CRITERION",
                {"source":"requirement_record","requirement_id":requirement["id"]},
                "source_backed", 1.0)
            explicit_invariant_ids = criterion.get("invariant_ids", [])
            if (not isinstance(explicit_invariant_ids, list)
                    or any(not isinstance(item, str) or not item.strip()
                           for item in explicit_invariant_ids)
                    or len(set(explicit_invariant_ids)) != len(explicit_invariant_ids)):
                raise BusinessModelError("criterion %s invariant_ids must be unique non-empty strings" %
                                         criterion["id"])
            unknown_invariants = sorted(set(explicit_invariant_ids) - set(invariant_nodes))
            if unknown_invariants:
                raise BusinessModelError("criterion %s references unknown invariants: %s" %
                                         (criterion["id"], ", ".join(unknown_invariants)))
            criterion_evaluation_ids = []
            criterion_invariant_evidence_ids = set()
            criterion_invariant_outcomes = []
            for invariant_id in explicit_invariant_ids:
                _add_edge(edges, cid, invariant_nodes[invariant_id], "requires_invariant",
                    "CRITERION.EXPLICIT_INVARIANT",
                    {"source":"requirement_acceptance_criterion","requirement_id":requirement["id"],
                     "criterion_id":criterion["id"],"invariant_id":invariant_id},
                    "requirement_declared", 1.0)
                for evaluation in invariant_results["evaluations"]:
                    if evaluation["invariant_id"] != invariant_id:
                        continue
                    criterion_evaluation_ids.append(evaluation["id"])
                    criterion_invariant_evidence_ids.update(evaluation["evidence_ids"])
                    criterion_invariant_outcomes.append(evaluation["outcome"])
                    _add_edge(edges, cid, invariant_evaluation_nodes[evaluation["id"]],
                        "has_invariant_evaluation", "CRITERION.INVARIANT_EVALUATION",
                        {"source":"explicit_requirement_invariant_mapping",
                         "requirement_id":requirement["id"],"criterion_id":criterion["id"],
                         "invariant_id":invariant_id,
                         "verification_level":evaluation["verification_level"]},
                        "computed_not_assessed", 1.0, evaluation["evidence_ids"])
            if not explicit_invariant_ids:
                invariant_status = "not_mapped"
            elif not criterion_evaluation_ids:
                invariant_status = "no_observation"
            elif set(criterion_invariant_outcomes) == {"pass"}:
                invariant_status = "computed_pass"
            elif set(criterion_invariant_outcomes) == {"fail"}:
                invariant_status = "computed_fail"
            else:
                invariant_status = "mixed"
            criterion_text = criterion["description"]
            criterion_entity_ids = set()
            criterion_exception_ids = set()
            for entity in model["entities"]:
                terms = entity["aliases"] + [entity["name"]] + entity["evidence_terms"]
                matched = [term for term in terms if _contains(criterion_text, term)]
                if matched:
                    criterion_entity_ids.add(entity["id"])
                    _add_edge(edges, cid, entity_nodes[entity["id"]], "candidate_requires",
                        "CRITERION.ENTITY_TERM_MATCH",
                        {"source":"acceptance_criterion","requirement_id":requirement["id"],
                         "criterion_id":criterion["id"],"matching_policy":"casefold_substring"},
                        "candidate_only", 0.5, [], matched)
            for exception in model["exceptions"]:
                terms = exception["aliases"] + [exception["name"]] + exception["evidence_terms"]
                matched = [term for term in terms if _contains(criterion_text, term)]
                if matched:
                    criterion_exception_ids.add(exception["id"])
                    _add_edge(edges, cid, exception_nodes[exception["id"]], "candidate_requires_exception",
                        "CRITERION.EXCEPTION_TERM_MATCH",
                        {"source":"acceptance_criterion","requirement_id":requirement["id"],
                         "criterion_id":criterion["id"],"matching_policy":"casefold_substring"},
                        "candidate_only", 0.5, [], matched)
            candidate_evidence_ids = []
            for ev in evidence:
                entity_hit = bool(criterion_entity_ids.intersection(evidence_entities.get(ev["id"], set())))
                exception_hit = bool(criterion_exception_ids.intersection(evidence_exceptions.get(ev["id"], set())))
                if entity_hit or exception_hit:
                    candidate_evidence_ids.append(ev["id"])
                    matched_entities = sorted(criterion_entity_ids.intersection(evidence_entities.get(ev["id"], set())))
                    matched_exceptions = sorted(criterion_exception_ids.intersection(evidence_exceptions.get(ev["id"], set())))
                    _add_edge(edges, cid, _node_id("evidence", ev["id"]), "candidate_evidence_for",
                        "CRITERION.EVIDENCE_CANDIDATE",
                        {"source":"criterion_to_evidence_candidate_projection",
                         "requirement_id":requirement["id"],"criterion_id":criterion["id"],
                         "matched_entity_ids":matched_entities,"matched_exception_ids":matched_exceptions,
                         "evidence_asset_id":ev.get("asset_id"),"evidence_locator":ev.get("locator", {})},
                        "candidate_only", 0.5, [ev["id"]])
            criterion_status = "candidate_evidence" if candidate_evidence_ids else "no_evidence"
            criterion_summaries.append({"requirement_id":requirement["id"],"criterion_id":criterion["id"],
                "required":criterion["required"],"status":criterion_status,
                "candidate_evidence_ids":sorted(candidate_evidence_ids),
                "candidate_entity_ids":sorted(criterion_entity_ids),
                "candidate_exception_ids":sorted(criterion_exception_ids),
                "invariant_ids":sorted(explicit_invariant_ids),
                "invariant_status":invariant_status,
                "invariant_evaluation_ids":sorted(criterion_evaluation_ids),
                "invariant_evidence_ids":sorted(criterion_invariant_evidence_ids),
                "invariant_outcomes":sorted(criterion_invariant_outcomes)})
    nodes.sort(key=lambda item: (item["kind"], item["id"]))
    edges.sort(key=lambda item: item["id"])
    return {"schema_version":1,"projection_type":"pack_driven_business_graph",
        "pack":model["pack"],"pack_version":str(model["pack_version"]),
        "workspace_id":workspace_id,
        "discovery_run_ids":sorted(run["id"] for run in discovery_runs),
        "business_model_version":model["version"],"business_model_sha256":model_digest,
        "inference_policy":{"term_match_is_candidate_only":True,
            "declared_transition_is_not_implementation_evidence":True,
            "declared_invariant_is_not_validation":True,
            "ci_result_is_not_runtime_observation":True,
            "no_evidence_does_not_mean_not_implemented":True},
        "counts":{"entities":len(model["entities"]),"processes":len(model["processes"]),
            "exceptions":len(model["exceptions"]),"invariants":len(model.get("invariants", [])),
            "aggregation_rules":len(model.get("aggregations", [])),
            "aggregation_groups":sum(item["summary"]["groups"] for item in aggregation_results),
            "aggregation_contributions":sum(item["summary"]["contributions"] for item in aggregation_results),
            "aggregation_skipped":sum(item["summary"]["skipped"] for item in aggregation_results),
            "assets":len(asset_nodes),"evidence":len(evidence),
            "nodes":len(nodes),"edges":len(edges),
            "candidate_entity_mentions":sum(1 for e in edges if e["relation"]=="candidate_mention"),
            "candidate_exception_mentions":sum(1 for e in edges if e["relation"]=="candidate_exception_mention"),
            "candidate_transition_links":sum(1 for e in edges if e["relation"]=="candidate_transition"),
            "candidate_code_state_transitions":sum(1 for n in nodes if n["kind"]=="code_state_transition"),
            "invariant_evaluations":len(invariant_results["evaluations"]),
            "invariants_passed":sum(1 for item in invariant_results["summary"] if item["status"]=="passed"),
            "invariants_failed":sum(1 for item in invariant_results["summary"] if item["status"]=="failed"),
            "invariants_without_observations":sum(1 for item in invariant_results["summary"] if item["status"]=="no_observation"),
            "criteria_with_invariant_mappings":sum(1 for item in criterion_summaries if item["invariant_ids"]),
            "criteria_with_computed_invariant_pass":sum(1 for item in criterion_summaries if item["invariant_status"]=="computed_pass"),
            "criteria_with_computed_invariant_fail":sum(1 for item in criterion_summaries if item["invariant_status"]=="computed_fail"),
            "criterion_candidate_evidence_links":sum(1 for e in edges if e["relation"]=="candidate_evidence_for"),
            "criteria_no_evidence":sum(1 for item in criterion_summaries if item["status"]=="no_evidence"),
            "criteria_with_candidates":sum(1 for item in criterion_summaries if item["status"]=="candidate_evidence")},
        "criterion_evidence_matrix":sorted(criterion_summaries,key=lambda item:(item["requirement_id"],item["criterion_id"])),
        "invariant_evaluations":invariant_results,
        "observation_aggregations":{"schema_version":1,"results":aggregation_results},
        "nodes":nodes,"edges":edges}
