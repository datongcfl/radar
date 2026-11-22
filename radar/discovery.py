"""Versioned, stdlib-only domain records for requirement-driven discovery."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from copy import deepcopy
import re
import uuid
from typing import Any, Mapping, Optional
from types import MappingProxyType

SCHEMA_VERSION = 1
PREFIXES = {
    "workspace": "ws", "requirement": "req", "source": "src", "asset": "ast",
    "evidence": "evd", "relationship": "rel", "assessment": "asm",
    "discovery_run": "run", "ledger_effect": "lef", "ledger_manifest": "lmn", "ledger_aggregation_rule": "lar",
}
REQUIRED = {
    "workspace": ("name", "status", "pack_refs"),
    "requirement": ("workspace_id", "key", "version", "title", "description",
                    "status", "priority", "acceptance_criteria"),
    "source": ("provider", "uri", "name", "access_status"),
    "asset": ("source_id", "asset_type", "uri", "title", "status"),
    "evidence": ("workspace_id", "asset_id", "evidence_kind", "statement",
                 "locator", "captured_at", "verification_status"),
    "relationship": ("from", "to", "relation_type", "confidence", "evidence_ids",
                     "status", "created_by"),
    "assessment": ("workspace_id", "requirement_id", "requirement_version",
                   "discovery_run_id", "overall_status", "criterion_results",
                   "evidence_ids", "pack_refs", "assessed_at"),
    "discovery_run": ("workspace_id", "status", "requirement_refs", "pack_refs",
                      "source_scope", "started_at", "stages", "counts", "errors",
                      "parameters", "radar_version"),
    "ledger_effect": ("workspace_id", "source_system", "ledger_entry_id", "asset_id",
                      "evidence_id", "locator", "effect"),
    "ledger_manifest": ("workspace_id", "source_system", "asset_id", "evidence_id",
                        "locator", "manifest"),
    "ledger_aggregation_rule": ("workspace_id", "rule_id", "rule"),
}
ENUMS = {
    ("workspace", "status"): {"active", "archived"},
    ("requirement", "status"): {"draft", "active", "superseded", "archived"},
    ("requirement", "priority"): {"low", "normal", "high", "critical"},
    ("source", "provider"): {"github", "gitee", "web", "filesystem",
                             "enterprise", "package_registry", "other"},
    ("source", "access_status"): {"public", "api_limited", "login_required",
                                  "paywalled", "proprietary", "blocked",
                                  "deleted", "unreachable", "unknown"},
    ("asset", "asset_type"): {"repository", "file", "directory", "issue",
                              "pull_request", "document", "web_page", "package",
                              "release", "dataset", "other"},
    ("asset", "status"): {"active", "deleted", "inaccessible", "superseded", "unknown"},
    ("evidence", "evidence_kind"): {"code", "test", "documentation", "standard",
                                    "issue", "pull_request", "configuration", "data",
                                    "observation", "other"},
    ("evidence", "verification_status"): {"unverified", "source_confirmed",
                                          "reproduced", "rejected"},
    ("relationship", "relation_type"): {"contains", "derived_from", "supports",
        "contradicts", "tests", "fixes", "supersedes", "depends_on",
        "implements", "mentions", "same_as"},
    ("relationship", "status"): {"active", "disputed", "superseded", "rejected"},
    ("relationship", "created_by"): {"radar", "agent", "human", "import"},
    ("assessment", "overall_status"): {"supported", "partially_supported",
        "contradicted", "no_evidence", "not_applicable", "not_assessed"},
    ("discovery_run", "status"): {"pending", "running", "partial", "succeeded",
                                  "failed", "cancelled"},
}
CRITERION_STATUSES = {"supported", "partially_supported", "contradicted",
                      "no_evidence", "not_applicable", "not_assessed"}


class DiscoveryValidationError(ValueError):
    """A discovery record violates the v1 domain contract."""


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [_thaw(item) for item in value]
    return deepcopy(value)


@dataclass(frozen=True)
class DomainRecord:
    """Immutable in-memory envelope; payload is copied at construction."""
    object_type: str
    id: str
    schema_version: int
    created_at: str
    payload: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        result = _thaw(self.payload)
        result.update({
            "object_type": self.object_type,
            "id": self.id,
            "schema_version": self.schema_version,
            "created_at": self.created_at,
        })
        return result


def _timestamp(value: Any, field: str) -> None:
    if not isinstance(value, str):
        raise DiscoveryValidationError("%s must be an ISO-8601 string" % field)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DiscoveryValidationError("%s must be an ISO-8601 timestamp" % field) from exc
    if parsed.tzinfo is None:
        raise DiscoveryValidationError("%s must include a timezone" % field)


def _nonempty(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DiscoveryValidationError("%s must be a non-empty string" % field)


def validate_record(record: Mapping[str, Any], expected_type: Optional[str] = None) -> dict[str, Any]:
    """Validate the core v1 invariants without third-party JSON Schema packages."""
    if not isinstance(record, Mapping):
        raise DiscoveryValidationError("record must be an object")
    data = dict(record)
    kind = data.get("object_type")
    if kind not in PREFIXES or (expected_type and kind != expected_type):
        raise DiscoveryValidationError("unknown or unexpected object_type: %r" % kind)
    if data.get("schema_version") != SCHEMA_VERSION:
        raise DiscoveryValidationError("schema_version must be 1")
    _nonempty(data.get("id"), "id")
    if not re.match(r"^%s_[A-Za-z0-9][A-Za-z0-9._-]{1,127}$" % PREFIXES[kind], data["id"]):
        raise DiscoveryValidationError("id prefix/format does not match %s" % kind)
    _timestamp(data.get("created_at"), "created_at")
    missing = [key for key in REQUIRED[kind] if key not in data]
    if missing:
        raise DiscoveryValidationError("%s missing required fields: %s" % (kind, ", ".join(missing)))
    if "updated_at" in data:
        _timestamp(data["updated_at"], "updated_at")

    for (obj, field), allowed in ENUMS.items():
        if obj == kind and data.get(field) not in allowed:
            raise DiscoveryValidationError("%s.%s has invalid value" % (kind, field))

    if kind == "workspace":
        if not isinstance(data["pack_refs"], list):
            raise DiscoveryValidationError("workspace.pack_refs must be an array")
    elif kind == "requirement":
        if not isinstance(data["version"], int) or data["version"] < 1:
            raise DiscoveryValidationError("requirement.version must be >= 1")
        if not isinstance(data["acceptance_criteria"], list):
            raise DiscoveryValidationError("requirement.acceptance_criteria must be an array")
        if "pack_unit_ids" in data and (not isinstance(data["pack_unit_ids"], list)
                or any(not isinstance(item, str) or not item for item in data["pack_unit_ids"])):
            raise DiscoveryValidationError("requirement.pack_unit_ids must be an array of non-empty strings")
        criterion_ids = []
        for item in data["acceptance_criteria"]:
            if not isinstance(item, dict):
                raise DiscoveryValidationError("acceptance criterion must be an object")
            for field in ("id", "description", "required"):
                if field not in item:
                    raise DiscoveryValidationError("acceptance criterion missing %s" % field)
            _nonempty(item["id"], "acceptance_criterion.id")
            _nonempty(item["description"], "acceptance_criterion.description")
            if not isinstance(item["required"], bool):
                raise DiscoveryValidationError("acceptance_criterion.required must be boolean")
            criterion_ids.append(item["id"])
        if len(criterion_ids) != len(set(criterion_ids)):
            raise DiscoveryValidationError("acceptance criterion ids must be unique")
    elif kind == "source":
        _nonempty(data["name"], "source.name")
        _nonempty(data["uri"], "source.uri")
        if not data["uri"].startswith(("http://", "https://", "file://")):
            raise DiscoveryValidationError("source.uri must be an absolute supported URI")
    elif kind == "asset":
        _nonempty(data["source_id"], "asset.source_id")
        _nonempty(data["uri"], "asset.uri")
        _nonempty(data["title"], "asset.title")
    elif kind == "evidence":
        _nonempty(data["statement"], "evidence.statement")
        if not isinstance(data["locator"], dict) or not data["locator"] or not any(
                value not in (None, "") for value in data["locator"].values()):
            raise DiscoveryValidationError("evidence.locator must identify a location")
        _timestamp(data["captured_at"], "captured_at")
        excerpt = data.get("excerpt")
        if excerpt is not None and (not isinstance(excerpt, str) or len(excerpt) > 2000):
            raise DiscoveryValidationError("evidence.excerpt must be text of at most 2000 characters")
    elif kind == "relationship":
        for endpoint in ("from", "to"):
            ref = data[endpoint]
            if (not isinstance(ref, dict) or not {"object_type", "id"} <= set(ref)
                    or ref.get("object_type") not in PREFIXES):
                raise DiscoveryValidationError("relationship.%s must be a typed object reference" % endpoint)
            _nonempty(ref.get("id"), "relationship.%s.id" % endpoint)
        confidence = data["confidence"]
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise DiscoveryValidationError("relationship.confidence must be between 0 and 1")
        if not isinstance(data["evidence_ids"], list):
            raise DiscoveryValidationError("relationship.evidence_ids must be an array")
    elif kind == "assessment":
        if not isinstance(data["requirement_version"], int) or data["requirement_version"] < 1:
            raise DiscoveryValidationError("assessment.requirement_version must be >= 1")
        if data["overall_status"] not in CRITERION_STATUSES:
            raise DiscoveryValidationError("assessment.overall_status is invalid")
        _timestamp(data["assessed_at"], "assessed_at")
        if not isinstance(data["criterion_results"], list) or not isinstance(data["evidence_ids"], list):
            raise DiscoveryValidationError("assessment results/evidence_ids must be arrays")
        for result in data["criterion_results"]:
            if not isinstance(result, dict) or result.get("status") not in CRITERION_STATUSES:
                raise DiscoveryValidationError("assessment criterion result has invalid status")
            if not isinstance(result.get("evidence_ids"), list):
                raise DiscoveryValidationError("criterion result evidence_ids must be an array")
    elif kind == "ledger_effect":
        for field in ("workspace_id", "source_system", "ledger_entry_id", "asset_id", "evidence_id"):
            _nonempty(data[field], "ledger_effect." + field)
        if not isinstance(data["locator"], dict) or not data["locator"]:
            raise DiscoveryValidationError("ledger_effect.locator must be a precise locator object")
        if not isinstance(data["effect"], dict):
            raise DiscoveryValidationError("ledger_effect.effect must be an object")
        if data["effect"].get("ledger_entry_id") != data["ledger_entry_id"] or data["effect"].get("source_system") != data["source_system"]:
            raise DiscoveryValidationError("ledger_effect envelope identity must match effect payload")
        if data["effect"].get("asset_id") != data["asset_id"] or data["effect"].get("evidence_id") != data["evidence_id"] or data["effect"].get("locator") != data["locator"]:
            raise DiscoveryValidationError("ledger_effect provenance must match effect payload")
    elif kind == "ledger_manifest":
        for field in ("workspace_id", "source_system", "asset_id", "evidence_id"):
            _nonempty(data[field], "ledger_manifest." + field)
        if not isinstance(data["locator"], dict) or not data["locator"] or not isinstance(data["manifest"], dict):
            raise DiscoveryValidationError("ledger_manifest requires locator and manifest objects")
        if data["manifest"].get("source_system") != data["source_system"]:
            raise DiscoveryValidationError("ledger_manifest source_system mismatch")
    elif kind == "ledger_aggregation_rule":
        _nonempty(data["workspace_id"], "ledger_aggregation_rule.workspace_id")
        _nonempty(data["rule_id"], "ledger_aggregation_rule.rule_id")
        if not isinstance(data["rule"], dict) or data["rule"].get("rule_id") != data["rule_id"]:
            raise DiscoveryValidationError("ledger_aggregation_rule rule identity mismatch")
    elif kind == "discovery_run":
        _timestamp(data["started_at"], "started_at")
        if data.get("finished_at") is not None:
            _timestamp(data["finished_at"], "finished_at")
        for field in ("requirement_refs", "pack_refs", "source_scope", "stages", "errors"):
            if not isinstance(data[field], list):
                raise DiscoveryValidationError("discovery_run.%s must be an array" % field)
        if not isinstance(data["counts"], dict) or not isinstance(data["parameters"], dict):
            raise DiscoveryValidationError("discovery_run counts/parameters must be objects")
    return data


def new_record(object_type: str, **fields: Any) -> DomainRecord:
    """Create and validate a new v1 record with a prefixed UUID and UTC timestamp."""
    if object_type not in PREFIXES:
        raise DiscoveryValidationError("unknown object_type: %r" % object_type)
    reserved = {"object_type", "id", "schema_version", "created_at"}
    overlap = reserved.intersection(fields)
    if overlap:
        raise DiscoveryValidationError("reserved fields cannot be overridden: %s" % sorted(overlap))
    record = {
        "object_type": object_type,
        "id": "%s_%s" % (PREFIXES[object_type], uuid.uuid4().hex),
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        **fields,
    }
    validate_record(record, object_type)
    return DomainRecord(object_type, record["id"], SCHEMA_VERSION,
                        record["created_at"], _freeze(fields))


def validate_evidence_unchanged(original: Mapping[str, Any], candidate: Mapping[str, Any]) -> None:
    """Reject in-place evidence edits; changed evidence must be appended as a new record."""
    old = validate_record(original, "evidence")
    new = validate_record(candidate, "evidence")
    if old != new:
        raise DiscoveryValidationError("Evidence is immutable; create a new evidence record")


def new_requirement_revision(previous: Mapping[str, Any], **changes: Any) -> DomainRecord:
    """Append a new requirement version; preserve its business key and link its predecessor."""
    old = validate_record(previous, "requirement")
    managed = {"workspace_id", "key", "version", "supersedes_requirement_id"}
    if managed.intersection(changes):
        raise DiscoveryValidationError("workspace_id/key/version/supersedes are managed by revisioning")
    fields = {key: value for key, value in old.items()
              if key not in {"object_type", "id", "schema_version", "created_at", "updated_at"}}
    fields.update(changes)
    fields["version"] = old["version"] + 1
    fields["supersedes_requirement_id"] = old["id"]
    return new_record("requirement", **fields)
