"""Pack-driven business graph projection; derived views, not core domain records."""
from __future__ import annotations
from hashlib import sha256
import json
from typing import Any, Iterable, Optional

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
                         discovery_runs: Iterable[dict[str, Any]] = ()) -> dict[str, Any]:
    """Build a deterministic, provenance-carrying projection from Pack + discovered records."""
    validate_business_model(model, pack)
    requirements, assets, evidence = list(requirements), list(assets), list(evidence)
    discovery_runs = list(discovery_runs)
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
    asset_nodes = {}
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
            asset_id=ev.get("asset_id"))
        asset_node = asset_nodes.get(ev.get("asset_id"))
        if asset_node:
            _add_edge(edges, enode, asset_node, "located_in", "CORE.EVIDENCE_ASSET",
                {"source":"discovery_record","evidence_id":eid,"asset_id":ev.get("asset_id"),
                 "locator":ev.get("locator", {})}, "source_backed", 1.0, [eid])
        asset = assets_by_id.get(ev.get("asset_id"), {})
        haystack = " ".join(str(x or "") for x in
            (ev.get("statement"), ev.get("excerpt"), asset.get("title"), asset.get("uri")))
        for entity in model["entities"]:
            terms = entity["evidence_terms"] + entity["aliases"] + [entity["name"]]
            matched = [term for term in terms if _contains(haystack, term)]
            if matched:
                _add_edge(edges, enode, entity_nodes[entity["id"]], "candidate_mention",
                    "ENTITY.TERM_MATCH", {"source":"evidence_text","evidence_id":eid,
                    "asset_id":ev.get("asset_id"),"locator":ev.get("locator",{}),
                    "matching_policy":"casefold_substring"}, "candidate_only", 0.5, [eid], matched)
        for exception in model["exceptions"]:
            terms = exception["evidence_terms"] + exception["aliases"] + [exception["name"]]
            matched = [term for term in terms if _contains(haystack, term)]
            if matched:
                _add_edge(edges, enode, exception_nodes[exception["id"]],
                    "candidate_exception_mention", "EXCEPTION.TERM_MATCH",
                    {"source":"evidence_text","evidence_id":eid,"asset_id":ev.get("asset_id"),
                     "locator":ev.get("locator",{}),"matching_policy":"casefold_substring"},
                    "candidate_only", 0.5, [eid], matched)
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
            criterion_text = criterion["description"]
            for entity in model["entities"]:
                terms = entity["aliases"] + [entity["name"]] + entity["evidence_terms"]
                matched = [term for term in terms if _contains(criterion_text, term)]
                if matched:
                    _add_edge(edges, cid, entity_nodes[entity["id"]], "candidate_requires",
                        "CRITERION.ENTITY_TERM_MATCH",
                        {"source":"acceptance_criterion","requirement_id":requirement["id"],
                         "criterion_id":criterion["id"],"matching_policy":"casefold_substring"},
                        "candidate_only", 0.5, [], matched)
    nodes.sort(key=lambda item: (item["kind"], item["id"]))
    edges.sort(key=lambda item: item["id"])
    return {"schema_version":1,"projection_type":"pack_driven_business_graph",
        "pack":model["pack"],"pack_version":str(model["pack_version"]),
        "workspace_id":workspace_id,
        "discovery_run_ids":sorted(run["id"] for run in discovery_runs),
        "business_model_version":model["version"],"business_model_sha256":model_digest,
        "inference_policy":{"term_match_is_candidate_only":True,
            "declared_transition_is_not_implementation_evidence":True,
            "no_evidence_does_not_mean_not_implemented":True},
        "counts":{"entities":len(model["entities"]),"processes":len(model["processes"]),
            "exceptions":len(model["exceptions"]),"assets":len(asset_nodes),"evidence":len(evidence),
            "nodes":len(nodes),"edges":len(edges),
            "candidate_entity_mentions":sum(1 for e in edges if e["relation"]=="candidate_mention"),
            "candidate_exception_mentions":sum(1 for e in edges if e["relation"]=="candidate_exception_mention")},
        "nodes":nodes,"edges":edges}
