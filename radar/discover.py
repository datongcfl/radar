"""Minimal requirement-driven discovery orchestration (v1)."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
import json

from . import __version__
from .discovery import new_record, new_requirement_revision, validate_record
from .discovery_store import JsonWorkspaceStore, StorageError
from .legacy import convert_legacy_sources, read_legacy_sources
from .model import load_json, load_pack, sha256_file


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _append_idempotent(store: JsonWorkspaceStore, record: dict[str, Any]) -> None:
    kind = record["object_type"]
    existing = store.get(kind, record["id"])
    if existing is None:
        store.append(record)
    elif kind in ("source", "asset", "relationship"):
        old = dict(existing)
        new = dict(record)
        old.pop("created_at", None)
        new.pop("created_at", None)
        if old != new:
            raise StorageError("existing %s record differs from deterministic import: %s" % (kind, record["id"]))
    elif existing != record:
        raise StorageError("existing %s record differs from deterministic import: %s" % (kind, record["id"]))


def _requirement_record(spec: dict[str, Any], workspace_id: str,
                        store: JsonWorkspaceStore, valid_pack_units: set[str]) -> dict[str, Any]:
    key = str(spec.get("key") or "").strip()
    if not key:
        raise ValueError("requirement.key is required")
    version = spec.get("version", 1)
    if not isinstance(version, int) or version < 1:
        raise ValueError("requirement.version must be a positive integer")
    pack_unit_ids = list(spec.get("pack_unit_ids") or [])
    unknown = sorted(set(pack_unit_ids) - valid_pack_units)
    if unknown:
        raise ValueError("requirement %s references unknown Pack units: %s" % (key, ", ".join(unknown)))
    fields = {
        "workspace_id": workspace_id, "key": key, "title": spec.get("title", key),
        "description": spec.get("description", ""), "version": version,
        "status": spec.get("status", "active"), "priority": spec.get("priority", "normal"),
        "terms": spec.get("terms", {}), "acceptance_criteria": spec.get("acceptance_criteria", []),
        "pack_unit_ids": pack_unit_ids,
    }
    history = store.find_requirement_history(key)
    existing = next((row for row in history if row.get("version") == version), None)
    if existing:
        comparable = ("workspace_id", "key", "version", "title", "description", "status",
                      "priority", "terms", "acceptance_criteria", "pack_unit_ids")
        if any(existing.get(k) != fields.get(k) for k in comparable):
            raise StorageError("requirement %s v%s already exists with different content" % (key, version))
        return existing
    if not history:
        if version != 1:
            raise ValueError("first version of requirement %s must be v1" % key)
        return new_record("requirement", **fields).to_dict()
    latest = history[-1]
    if version != latest["version"] + 1:
        raise ValueError("requirement %s must append version %s, not %s" %
                         (key, latest["version"] + 1, version))
    changes = {k: v for k, v in fields.items()
               if k not in ("workspace_id", "key", "version")}
    return new_requirement_revision(latest, **changes).to_dict()


def _mention_relationship(from_type: str, from_id: str, to_type: str, to_id: str) -> dict[str, Any]:
    stable_key = json.dumps([from_type, from_id, "mentions", to_type, to_id], separators=(",", ":"))
    rel = new_record("relationship",
        **{"from": {"object_type": from_type, "id": from_id},
           "to": {"object_type": to_type, "id": to_id},
           "relation_type": "mentions", "confidence": 0.5,
           "evidence_ids": [], "status": "active", "created_by": "radar"}).to_dict()
    rel["id"] = "rel_" + sha256(stable_key.encode("utf-8")).hexdigest()[:32]
    return validate_record(rel, "relationship")


def run_discovery(workspace_id: str, requirements_path: str, pack_path: str,
                  seeds_path: str, workspace_root: str = ".") -> dict[str, Any]:
    """Run the first offline discover loop from requirements + existing Seeds."""
    started_at = _now()
    spec = load_json(requirements_path)
    if not isinstance(spec, dict) or spec.get("schema_version") != 1:
        raise ValueError("requirements file schema_version must be 1")
    requirement_specs = spec.get("requirements")
    if not isinstance(requirement_specs, list) or not requirement_specs:
        raise ValueError("requirements file must contain a non-empty requirements array")

    pack = load_pack(pack_path)
    seeds = read_legacy_sources(seeds_path, pack)
    pack_digest = sha256_file(pack_path)
    pack_refs = [{"pack": pack["pack"], "version": str(pack.get("version", "unknown")),
                  "digest": pack_digest}]
    workspace_spec = spec.get("workspace") or {}
    workspace = new_record(
        "workspace", name=workspace_spec.get("name", workspace_id),
        description=workspace_spec.get("description", ""),
        status="active", pack_refs=pack_refs,
        settings={"radar_version": __version__, "discovery_schema_version": 1},
    ).to_dict()
    # Workspace identity is supplied by the caller and remains stable across Runs.
    workspace["id"] = workspace_id
    workspace = validate_record(workspace, "workspace")
    store = JsonWorkspaceStore(workspace_root, workspace_id)
    store.initialize(workspace)

    valid_units = {item["id"] for item in pack["modules"] + pack["subsystems"]}
    requirements = []
    for item in requirement_specs:
        record = _requirement_record(item, workspace_id, store, valid_units)
        _append_idempotent(store, record)
        requirements.append(record)

    converted = convert_legacy_sources(seeds, workspace_id, captured_at=started_at)
    for kind in ("sources", "assets", "relationships", "evidence"):
        object_type = {"sources": "source", "assets": "asset",
                       "relationships": "relationship", "evidence": "evidence"}[kind]
        for record in converted[kind]:
            _append_idempotent(store, record)
    for quote in converted["pending_quotes"]:
        store.append_pending_quote(quote)

    requirements_by_unit: dict[str, list[dict[str, Any]]] = {}
    for requirement in requirements:
        for unit_id in requirement.get("pack_unit_ids", []):
            requirements_by_unit.setdefault(unit_id, []).append(requirement)

    candidate_assets: dict[str, set[str]] = {r["id"]: set() for r in requirements}
    candidate_evidence: dict[str, set[str]] = {r["id"]: set() for r in requirements}
    new_relationships = []
    for asset in converted["assets"]:
        covers = set(asset.get("metadata", {}).get("legacy_covers", []))
        matched = {req["id"]: req for unit in covers
                   for req in requirements_by_unit.get(unit, [])}
        for req_id, requirement in matched.items():
            candidate_assets[req_id].add(asset["id"])
            relation = _mention_relationship("asset", asset["id"], "requirement", req_id)
            _append_idempotent(store, relation)
            new_relationships.append(relation)
    for evidence in converted["evidence"]:
        for req_id, asset_ids in candidate_assets.items():
            if evidence["asset_id"] in asset_ids:
                candidate_evidence[req_id].add(evidence["id"])
                relation = _mention_relationship("evidence", evidence["id"], "requirement", req_id)
                _append_idempotent(store, relation)
                new_relationships.append(relation)

    run = new_record("discovery_run", workspace_id=workspace_id, status="partial"
                     if converted["pending_quotes"] else "succeeded",
        requirement_refs=[{"requirement_id": r["id"], "version": r["version"]} for r in requirements],
        pack_refs=pack_refs, source_scope=[r["id"] for r in converted["sources"]],
        started_at=started_at, finished_at=_now(),
        stages=[
            {"name": "load_requirements", "status": "succeeded"},
            {"name": "load_legacy_seeds", "status": "succeeded"},
            {"name": "convert_assets", "status": "succeeded"},
            {"name": "persist_records", "status": "succeeded"},
            {"name": "map_candidates", "status": "succeeded"},
            {"name": "assess_requirements", "status": "succeeded"},
            {"name": "locate_legacy_quotes", "status": "partial" if converted["pending_quotes"] else "succeeded",
             "errors": ["legacy quote lacks precise locator"] if converted["pending_quotes"] else []},
        ],
        counts={"sources": len(converted["sources"]), "assets": len(converted["assets"]),
                "evidence": len(converted["evidence"]), "relationships": len(converted["relationships"]) + len(new_relationships),
                "pending_quotes": len(converted["pending_quotes"]), "requirements": len(requirements)},
        errors=[], parameters={"pack_path": str(pack_path), "seeds_path": str(seeds_path),
                               "requirements_path": str(requirements_path)},
        radar_version=__version__).to_dict()

    assessments = []
    for requirement in requirements:
        evidence_ids = sorted(candidate_evidence[requirement["id"]])
        status = "not_assessed" if evidence_ids else "no_evidence"
        criterion_results = [{
            "criterion_id": criterion["id"], "status": status,
            "evidence_ids": evidence_ids,
            "gap": None if evidence_ids else "No locatable evidence found in the selected assets",
        } for criterion in requirement.get("acceptance_criteria", [])]
        assessment = new_record("assessment", workspace_id=workspace_id,
            requirement_id=requirement["id"], requirement_version=requirement["version"],
            discovery_run_id=run["id"], overall_status=status,
            criterion_results=criterion_results, evidence_ids=evidence_ids,
            gaps=[] if evidence_ids else [{"kind": "evidence_gap", "message": "No locatable evidence found"}],
            risks=[], pack_refs=pack_refs, ruleset_version="discovery-v1",
            assessed_at=_now()).to_dict()
        store.append(assessment)
        assessments.append(assessment)

    store.append(run)
    return {
        "workspace_id": workspace_id, "workspace_path": str(store.root),
        "run_id": run["id"], "run_status": run["status"],
        "counts": run["counts"],
        "assessments": [{"requirement_key": r["key"], "status": a["overall_status"],
                         "candidate_assets": len(candidate_assets[r["id"]]),
                         "evidence": len(a["evidence_ids"])}
                        for r, a in zip(requirements, assessments)],
    }
