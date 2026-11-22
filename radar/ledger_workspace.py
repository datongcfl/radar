"""Workspace persistence boundary for provenance-backed ledger bundles."""
from __future__ import annotations

from typing import Any
from .discovery import new_record, validate_record
from .discovery_store import JsonWorkspaceStore, StorageError
from .ledger_control_pipeline import run_ledger_control_pipeline
import json


def import_ledger_bundle(store: JsonWorkspaceStore, bundle: dict[str, Any]) -> dict[str, int]:
    """Append ledger rows, manifests and rules after checking Workspace provenance.

    Evidence and Assets are deliberately not synthesized from the import file:
    they must already exist in this Workspace. The full bundle is preflighted
    before the first append so ordinary contract/identity failures do not leave
    a partially imported batch.
    """
    if not isinstance(bundle, dict):
        raise StorageError("ledger import must be a JSON object")
    required = ("ledger_effects", "evidence_records", "extraction_manifests", "aggregation_rules")
    missing = [key for key in required if key not in bundle]
    if missing:
        raise StorageError("ledger import missing fields: %s" % ", ".join(missing))
    if not all(isinstance(bundle[key], list) for key in required):
        raise StorageError("ledger import bundle fields must be arrays")

    workspace_evidence = {item["id"]: item for item in store.list_records("evidence")}
    supplied_evidence = {item.get("id"): item for item in bundle["evidence_records"]
                         if isinstance(item, dict)}
    if len(supplied_evidence) != len(bundle["evidence_records"]):
        raise StorageError("evidence_records must contain unique identified objects")
    for evidence_id, supplied in supplied_evidence.items():
        existing = workspace_evidence.get(evidence_id)
        if existing is None or existing != supplied:
            raise StorageError("Evidence %s is not an exact record in this Workspace" % evidence_id)

    records = []
    for effect in bundle["ledger_effects"]:
        if not isinstance(effect, dict):
            raise StorageError("ledger effect must be an object")
        evidence_id = effect.get("evidence_id")
        evidence = workspace_evidence.get(evidence_id)
        if evidence is None:
            raise StorageError("ledger effect references Evidence outside this Workspace: %s" % evidence_id)
        if evidence.get("asset_id") != effect.get("asset_id") or evidence.get("locator") != effect.get("locator"):
            raise StorageError("ledger effect Asset/locator does not match Workspace Evidence")
        records.append(new_record("ledger_effect", workspace_id=store.workspace_id,
            source_system=effect.get("source_system"), ledger_entry_id=effect.get("ledger_entry_id"),
            asset_id=effect.get("asset_id"), evidence_id=evidence_id,
            locator=effect.get("locator"), effect=effect).to_dict())

    for manifest in bundle["extraction_manifests"]:
        if not isinstance(manifest, dict):
            raise StorageError("extraction manifest must be an object")
        evidence_id = manifest.get("evidence_id")
        evidence = workspace_evidence.get(evidence_id)
        if evidence is None:
            raise StorageError("manifest references Evidence outside this Workspace: %s" % evidence_id)
        if evidence.get("asset_id") != manifest.get("asset_id") or evidence.get("locator") != manifest.get("locator"):
            raise StorageError("manifest Asset/locator does not match Workspace Evidence")
        records.append(new_record("ledger_manifest", workspace_id=store.workspace_id,
            source_system=manifest.get("source_system"), asset_id=manifest.get("asset_id"),
            evidence_id=evidence_id, locator=manifest.get("locator"), manifest=manifest).to_dict())

    for rule in bundle["aggregation_rules"]:
        if not isinstance(rule, dict) or not isinstance(rule.get("rule_id"), str):
            raise StorageError("aggregation rule requires rule_id")
        records.append(new_record("ledger_aggregation_rule", workspace_id=store.workspace_id,
            rule_id=rule["rule_id"], rule=rule).to_dict())

    # Preflight all IDs and source identities before mutating append-only storage.
    existing_effects = {(item["source_system"], item["ledger_entry_id"])
                        for item in store.list_records("ledger_effect")}
    batch_effects = set()
    existing_rule_ids = {item["rule_id"] for item in store.list_records("ledger_aggregation_rule")}
    batch_rule_ids = set()
    existing_manifest_ids = {item["manifest"].get("id")
                             for item in store.list_records("ledger_manifest")}
    batch_manifest_ids = set()
    for record in records:
        validate_record(record)
        if record["object_type"] == "ledger_effect":
            identity = (record["source_system"], record["ledger_entry_id"])
            if identity in existing_effects or identity in batch_effects:
                raise StorageError("duplicate ledger identity: %s/%s" % identity)
            batch_effects.add(identity)
        elif record["object_type"] == "ledger_manifest":
            manifest_id = record["manifest"].get("id")
            if not isinstance(manifest_id, str) or not manifest_id.strip():
                raise StorageError("extraction manifest requires a stable id")
            if manifest_id in existing_manifest_ids or manifest_id in batch_manifest_ids:
                raise StorageError("duplicate extraction manifest id: %s" % manifest_id)
            batch_manifest_ids.add(manifest_id)
        elif record["object_type"] == "ledger_aggregation_rule":
            rule_id = record["rule_id"]
            if rule_id in existing_rule_ids or rule_id in batch_rule_ids:
                raise StorageError("duplicate ledger aggregation rule: %s" % rule_id)
            batch_rule_ids.add(rule_id)

    for record in records:
        store.append(record)
    return {"ledger_effects": len(bundle["ledger_effects"]),
            "extraction_manifests": len(bundle["extraction_manifests"]),
            "aggregation_rules": len(bundle["aggregation_rules"])}



def run_workspace_ledger_control(store: JsonWorkspaceStore,
                                 config: dict[str, Any] | None) -> dict[str, Any]:
    """Run controls during Discovery only when the Pack explicitly opts in."""
    if config is None:
        return {"status": "skipped", "reason": "pack_opt_in_absent"}
    if not isinstance(config, dict):
        raise StorageError("Pack ledger_control must be an object")
    enabled = config.get("enabled")
    run_on_discover = config.get("run_on_discover")
    if not isinstance(enabled, bool) or not isinstance(run_on_discover, bool):
        raise StorageError("Pack ledger_control requires boolean enabled and run_on_discover")
    if not enabled or not run_on_discover:
        return {"status": "skipped", "reason": "pack_opt_in_disabled"}
    has_records = any(store.list_records(kind) for kind in (
        "ledger_effect", "ledger_manifest", "ledger_aggregation_rule"))
    if not has_records:
        return {"status": "skipped", "reason": "no_workspace_ledger_records"}

    bundle = load_ledger_bundle(store)
    result = run_ledger_control_pipeline(
        bundle["ledger_effects"], bundle["evidence_records"],
        bundle["extraction_manifests"], bundle["aggregation_rules"],
        reconciliation_tolerance=config.get("reconciliation_tolerance", "0.01"),
        voucher_tolerance=config.get("voucher_tolerance", "0"))
    digest = store.save_snapshot(json.dumps(
        result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return {"status": "succeeded", "snapshot_sha256": digest,
            "summary": result["summary"]}


def load_ledger_bundle(store: JsonWorkspaceStore) -> dict[str, Any]:
    """Rehydrate the exact ledger pipeline inputs from immutable Workspace records."""
    evidence = {item["id"]: item for item in store.list_records("evidence")}
    effects = [item["effect"] for item in store.list_records("ledger_effect")]
    manifests = [item["manifest"] for item in store.list_records("ledger_manifest")]
    rules = [item["rule"] for item in store.list_records("ledger_aggregation_rule")]
    referenced = {item.get("evidence_id") for item in effects + manifests}
    missing = sorted(ref for ref in referenced if ref not in evidence)
    if missing:
        raise StorageError("persisted ledger records reference missing Workspace Evidence: %s" % ", ".join(missing))
    return {"ledger_effects": effects,
            "evidence_records": [evidence[key] for key in sorted(referenced)],
            "extraction_manifests": manifests,
            "aggregation_rules": rules}
