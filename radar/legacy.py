"""Read and convert legacy Seeds/Quote records without mutating their originals."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Optional
from urllib.parse import urlsplit
import json

from .discovery import PREFIXES, new_record, validate_record
from .model import canonical_url, load_seeds


def read_legacy_sources(path: str, pack: dict[str, Any], strict: bool = False) -> list[dict[str, Any]]:
    """Read the v1 Seeds ledger through the existing compatibility loader."""
    return load_seeds(path, pack, strict=strict)


def _stable_id(object_type: str, key: str) -> str:
    digest = sha256(key.encode("utf-8")).hexdigest()[:32]
    return "%s_%s" % (PREFIXES[object_type], digest)


def _stable_record(object_type: str, stable_key: str, **fields: Any) -> dict[str, Any]:
    record = new_record(object_type, **fields).to_dict()
    record["id"] = _stable_id(object_type, stable_key)
    return validate_record(record, object_type)


def _provider(platform: str) -> str:
    if platform in ("github", "gitee"):
        return platform
    if platform in ("npm", "pypi", "maven"):
        return "package_registry"
    return "web"


def _asset_type(platform: str, artifact_type: str, url: str) -> str:
    if platform in ("github", "gitee"):
        return "repository"
    if platform in ("npm", "pypi", "maven"):
        return "package"
    path = urlsplit(url).path.lower()
    if path.endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")):
        return "document"
    if artifact_type in ("manual", "prd", "quote_sheet", "subsystem_list", "docs"):
        return "document"
    return "web_page"


def _verification_status(source: dict[str, Any]) -> str:
    value = source.get("quote_verified", "unknown")
    if value is False:
        value = "false"
    if value is True:
        value = "true"
    if value == "false":
        return "rejected"
    if value == "true" and source.get("quote_verified_by") == "web":
        return "source_confirmed"
    return "unverified"


def convert_legacy_sources(
    sources: list[dict[str, Any]],
    workspace_id: str,
    captured_at: Optional[str] = None,
) -> dict[str, list[dict[str, Any]]]:
    """Convert conflated legacy Source rows into Source + Asset + locatable Evidence.

    Plain-text legacy quotes without a concrete locator are retained in
    pending_quotes and are deliberately not promoted to Evidence.
    """
    if captured_at is None:
        captured_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    source_records: dict[str, dict[str, Any]] = {}
    asset_records: dict[str, dict[str, Any]] = {}
    relationships: dict[str, dict[str, Any]] = {}
    evidence_records: dict[str, dict[str, Any]] = {}
    pending_quotes: list[dict[str, Any]] = []

    for legacy in sources:
        url = str(legacy.get("url") or "")
        normalized = canonical_url(url)
        if not normalized:
            pending_quotes.append({"legacy_source_id": legacy.get("id"), "reason": "missing_url"})
            continue
        parts = urlsplit(normalized)
        provider = _provider(str(legacy.get("platform") or "web"))
        origin = "%s://%s" % (parts.scheme or "https", parts.netloc)
        source_key = provider + "|" + origin
        source_id = _stable_id("source", source_key)
        if source_id not in source_records:
            source_records[source_id] = _stable_record(
                "source", source_key, provider=provider, uri=origin,
                name=parts.netloc or provider, access_status="public",
                metadata={"imported_from": "legacy_seeds"},
            )

        asset_id = _stable_id("asset", normalized)
        legacy_access = legacy.get("access_status", "public")
        asset_status = "deleted" if legacy_access == "deleted" else (
            "inaccessible" if legacy_access in ("blocked", "unreachable") else "active")
        metadata = {
            "legacy_source_ids": [legacy.get("id")],
            "legacy_covers": list(legacy.get("covers") or []),
            "legacy_evidence_level": legacy.get("evidence_level"),
            "legacy_license": legacy.get("license"),
            "legacy_license_status": legacy.get("license_status"),
            "legacy_status": legacy.get("status"),
            "legacy_access_status": legacy_access,
        }
        if asset_id not in asset_records:
            asset_records[asset_id] = _stable_record(
                "asset", normalized, source_id=source_id,
                asset_type=_asset_type(str(legacy.get("platform") or "web"),
                                       str(legacy.get("artifact_type") or "article"), url),
                uri=normalized, title=str(legacy.get("title") or url),
                version_ref=None, status=asset_status, metadata=metadata,
            )
        else:
            current = asset_records[asset_id]
            current["metadata"]["legacy_source_ids"].append(legacy.get("id"))
            current["metadata"]["legacy_covers"] = sorted(set(
                current["metadata"]["legacy_covers"] + list(legacy.get("covers") or [])))
        relation_key = source_id + "->" + asset_id
        relation_id = _stable_id("relationship", relation_key)
        if relation_id not in relationships:
            relationships[relation_id] = _stable_record(
                "relationship", relation_key,
                **{"from": {"object_type": "source", "id": source_id},
                   "to": {"object_type": "asset", "id": asset_id},
                   "relation_type": "contains", "confidence": 1.0,
                   "evidence_ids": [], "status": "active", "created_by": "import"},
            )

        for index, quote in enumerate(legacy.get("quotes") or []):
            if isinstance(quote, dict):
                quote_text = quote.get("text") or quote.get("quote")
                locator = quote.get("locator")
            else:
                quote_text, locator = str(quote), None
            if not quote_text or not isinstance(locator, dict) or not locator or not any(
                    value not in (None, "") for value in locator.values()):
                pending_quotes.append({
                    "legacy_source_id": legacy.get("id"), "asset_id": asset_id,
                    "quote": quote_text, "reason": "missing_precise_locator",
                })
                continue
            evidence_key = json.dumps(
                [asset_id, index, quote_text, locator], ensure_ascii=False, sort_keys=True)
            artifact = str(legacy.get("artifact_type") or "")
            evidence_kind = "code" if artifact == "code" else (
                "documentation" if artifact in ("readme", "docs", "manual", "prd") else "observation")
            evidence = _stable_record(
                "evidence", evidence_key, workspace_id=workspace_id, asset_id=asset_id,
                requirement_id=None, criterion_id=None, evidence_kind=evidence_kind,
                statement=str(quote_text), excerpt=str(quote_text)[:2000],
                locator=locator, asset_version_ref=None, captured_at=captured_at,
                extractor={"name": "legacy-import", "version": "1"},
                verification_status=_verification_status(legacy),
                license_status=legacy.get("license_status", "unknown")
                    if legacy.get("license_status") in ("clear", "needs_review", "restricted", "unknown")
                    else "unknown",
            )
            evidence_records[evidence["id"]] = evidence

    return {
        "sources": list(source_records.values()),
        "assets": list(asset_records.values()),
        "relationships": list(relationships.values()),
        "evidence": list(evidence_records.values()),
        "pending_quotes": pending_quotes,
    }
