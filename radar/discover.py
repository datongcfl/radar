"""Minimal requirement-driven discovery orchestration (v1)."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Optional
import json

from . import __version__
from .discovery import new_record, new_requirement_revision, validate_record
from .discovery_store import JsonWorkspaceStore, StorageError
from .legacy import convert_legacy_sources, read_legacy_sources
from .model import load_json, load_pack, sha256_file
from .github_discovery import discover_github
from .business_graph import validate_business_model
from .business_invariants import validate_observation_bundle, evaluate_business_invariants
from .business_observation_extractor import extract_table_observations


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
                  seeds_path: str, workspace_root: str = ".",
                  github: bool = False, github_limit: int = 5,
                  business_model_path: Optional[str] = None) -> dict[str, Any]:
    """Run requirement discovery from existing Seeds and optional GitHub search."""
    started_at = _now()
    spec = load_json(requirements_path)
    if not isinstance(spec, dict) or spec.get("schema_version") != 1:
        raise ValueError("requirements file schema_version must be 1")
    requirement_specs = spec.get("requirements")
    if not isinstance(requirement_specs, list) or not requirement_specs:
        raise ValueError("requirements file must contain a non-empty requirements array")

    pack = load_pack(pack_path)
    if business_model_path is None:
        candidate_model = Path(pack_path).with_name("business-model.json")
        business_model_path = str(candidate_model) if candidate_model.is_file() else None
    business_model = None
    if business_model_path:
        business_model = validate_business_model(load_json(business_model_path), pack)
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
    persisted_workspace = store.list_records("workspace")[0]
    if persisted_workspace.get("pack_refs") != pack_refs:
        raise StorageError("Workspace Pack version lock differs; create a new Workspace or explicitly migrate it")

    valid_units = {item["id"] for item in pack["modules"] + pack["subsystems"]}
    requirements = []
    for item in requirement_specs:
        record = _requirement_record(item, workspace_id, store, valid_units)
        _append_idempotent(store, record)
        requirements.append(record)

    converted = convert_legacy_sources(seeds, workspace_id, captured_at=started_at)
    github_result = (discover_github(requirements, pack, workspace_id,
                                     limit_per_query=github_limit,
                                     business_model=business_model)
                     if github else {"sources": [], "assets": [], "evidence": [],
                                     "relationships": [], "matches": {}, "warnings": [],
                                     "counts": {"code": 0, "issues": 0, "pull_requests": 0,
                                                "pr_files": 0, "documents": 0, "unsupported_documents": 0}})
    all_sources = converted["sources"] + github_result["sources"]
    all_assets = converted["assets"] + github_result["assets"]
    all_evidence = converted["evidence"] + github_result["evidence"]
    all_relationships = converted["relationships"] + github_result["relationships"]
    for kind in ("sources", "assets", "relationships", "evidence"):
        object_type = {"sources": "source", "assets": "asset",
                       "relationships": "relationship", "evidence": "evidence"}[kind]
        rows = {"sources": all_sources, "assets": all_assets,
                "relationships": all_relationships,
                "evidence": all_evidence}[kind]
        for record in rows:
            _append_idempotent(store, record)
    for quote in converted["pending_quotes"]:
        store.append_pending_quote(quote)

    requirements_by_unit: dict[str, list[dict[str, Any]]] = {}
    for requirement in requirements:
        for unit_id in requirement.get("pack_unit_ids", []):
            requirements_by_unit.setdefault(unit_id, []).append(requirement)

    candidate_assets: dict[str, set[str]] = {r["id"]: set() for r in requirements}
    candidate_evidence: dict[str, set[str]] = {r["id"]: set() for r in requirements}
    for requirement_id, asset_ids in github_result["matches"].items():
        if requirement_id in candidate_assets:
            candidate_assets[requirement_id].update(asset_ids)
    new_relationships = []
    for asset in all_assets:
        covers = set(asset.get("metadata", {}).get("legacy_covers", []))
        matched = {req["id"]: req for unit in covers
                   for req in requirements_by_unit.get(unit, [])}
        for req_id, requirement in matched.items():
            candidate_assets[req_id].add(asset["id"])
            relation = _mention_relationship("asset", asset["id"], "requirement", req_id)
            _append_idempotent(store, relation)
            new_relationships.append(relation)
    for requirement_id, asset_ids in github_result["matches"].items():
        for asset_id in asset_ids:
            relation = _mention_relationship("asset", asset_id, "requirement", requirement_id)
            _append_idempotent(store, relation)
            new_relationships.append(relation)
    for evidence in all_evidence:
        for req_id, asset_ids in candidate_assets.items():
            if evidence["asset_id"] in asset_ids:
                candidate_evidence[req_id].add(evidence["id"])
                relation = _mention_relationship("evidence", evidence["id"], "requirement", req_id)
                _append_idempotent(store, relation)
                new_relationships.append(relation)

    observation_bundle = None
    observation_bundle_path = None
    observation_summary = {"observations": 0, "skipped_rows": 0,
                           "invariants_with_aliases": 0}
    if business_model and github and github_result.get("table_chunks"):
        observation_rows = []
        skipped_rows = []
        for asset_id, chunks in sorted(github_result["table_chunks"].items()):
            asset_evidence = [item for item in all_evidence
                              if item.get("asset_id") == asset_id]
            extracted = extract_table_observations(
                business_model.get("invariants", []), chunks,
                asset_evidence, asset_id, origin="static_source")
            observation_rows.extend(extracted["observations"])
            skipped_rows.extend(extracted["skipped"])
        observation_rows.sort(key=lambda item: (item["invariant_id"], item["scope_key"]))
        observation_bundle = {"schema_version": 1,
                              "observations": observation_rows,
                              "skipped": skipped_rows,
                              "summary": {
                                  "observations": len(observation_rows),
                                  "skipped_rows": len(skipped_rows),
                                  "invariants_with_aliases": len(set(
                                      item["invariant_id"] for item in observation_rows)),
                              }}
        validate_observation_bundle(
            observation_bundle, business_model.get("invariants", []), all_evidence)
        invariant_evaluations = evaluate_business_invariants(
            business_model.get("invariants", []), observation_bundle, all_evidence)
        observation_bundle["invariant_evaluations"] = invariant_evaluations
        evaluation_rows = invariant_evaluations["evaluations"]
        observation_bundle["summary"]["invariant_evaluations"] = len(evaluation_rows)
        observation_bundle["summary"]["invariant_passes"] = sum(
            1 for item in evaluation_rows if item["outcome"] == "pass")
        observation_bundle["summary"]["invariant_failures"] = sum(
            1 for item in evaluation_rows if item["outcome"] == "fail")
        observation_summary = observation_bundle["summary"]

    run = new_record("discovery_run", workspace_id=workspace_id, status="partial"
                     if converted["pending_quotes"] or github_result["warnings"] else "succeeded",
        requirement_refs=[{"requirement_id": r["id"], "version": r["version"]} for r in requirements],
        pack_refs=pack_refs, source_scope=[r["id"] for r in all_sources],
        started_at=started_at, finished_at=_now(),
        stages=[
            {"name": "load_requirements", "status": "succeeded"},
            {"name": "load_legacy_seeds", "status": "succeeded"},
            {"name": "github_code_issue_pr_and_tree_document_discovery",
             "status": ("partial" if github_result["warnings"] else "succeeded") if github else "skipped",
             "errors": github_result["warnings"]},
            {"name": "convert_assets", "status": "succeeded"},
            {"name": "persist_records", "status": "succeeded"},
            {"name": "map_candidates", "status": "succeeded"},
            {"name": "extract_business_observations",
             "status": "succeeded" if observation_bundle is not None else ("skipped" if not business_model or not github else "no_matching_tables"),
             "errors": []},
            {"name": "assess_requirements", "status": "succeeded"},
            {"name": "locate_legacy_quotes", "status": "partial" if converted["pending_quotes"] else "succeeded",
             "errors": ["legacy quote lacks precise locator"] if converted["pending_quotes"] else []},
        ],
        counts={"sources": len(all_sources), "assets": len(all_assets),
                "evidence": len(all_evidence), "relationships": len(all_relationships) + len(new_relationships),
                "pending_quotes": len(converted["pending_quotes"]), "requirements": len(requirements),
                "github_code": github_result["counts"]["code"],
                "github_issues": github_result["counts"]["issues"],
                "github_pull_requests": github_result["counts"]["pull_requests"],
                "github_pr_files": github_result["counts"]["pr_files"],
                "github_documents": github_result["counts"].get("documents", 0),
                "github_unsupported_documents": github_result["counts"].get("unsupported_documents", 0),
                "business_observations": observation_summary["observations"],
                "business_observation_skipped_rows": observation_summary["skipped_rows"],
                "business_invariant_evaluations": observation_summary.get("invariant_evaluations", 0),
                "business_invariant_passes": observation_summary.get("invariant_passes", 0),
                "business_invariant_failures": observation_summary.get("invariant_failures", 0)},
        errors=list(github_result["warnings"]), parameters={"pack_path": str(pack_path), "pack_sha256": pack_digest,
                               "seeds_path": str(seeds_path), "seeds_sha256": sha256_file(seeds_path),
                               "requirements_path": str(requirements_path),
                               "requirements_sha256": sha256_file(requirements_path),
                               "github_enabled": bool(github), "github_limit": github_limit},
        radar_version=__version__).to_dict()

    if observation_bundle is not None:
        observation_dir = store.root / "observations"
        observation_dir.mkdir(parents=True, exist_ok=True)
        observation_bundle_path = observation_dir / (run["id"] + ".json")
        temporary_path = observation_bundle_path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(observation_bundle, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8")
        temporary_path.replace(observation_bundle_path)

    assessments = []
    for requirement in requirements:
        evidence_ids = sorted(candidate_evidence[requirement["id"]])
        status = "not_assessed" if evidence_ids else "no_evidence"
        criterion_results = [{
            "criterion_id": criterion["id"], "status": status,
            "evidence_ids": [],
            "notes": "Candidate evidence requires Agent/human assessment" if evidence_ids else "",
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
        "counts": run["counts"], "warnings": github_result["warnings"],
        "business_observations_path": str(observation_bundle_path) if observation_bundle_path else None,
        "business_observations": observation_summary,
        "assessments": [{"requirement_key": r["key"], "status": a["overall_status"],
                         "candidate_assets": len(candidate_assets[r["id"]]),
                         "evidence": len(a["evidence_ids"])}
                        for r, a in zip(requirements, assessments)],
    }
