"""Requirement-driven GitHub discovery for files, Issues, and pull requests.

The adapter is opt-in and requires GITHUB_TOKEN. Search results are candidates,
not proof that a requirement is implemented.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Optional
from urllib.parse import quote, urlencode, urlsplit
import json
import os

from .adapters import _curl_json
from .discovery import new_record, validate_record


API = "https://api.github.com"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _stable_id(prefix: str, key: str) -> str:
    return prefix + "_" + sha256(key.encode("utf-8")).hexdigest()[:32]


def _record(kind: str, stable_key: str, **fields: Any) -> dict[str, Any]:
    item = new_record(kind, **fields).to_dict()
    item["id"] = _stable_id({"source": "src", "asset": "ast", "evidence": "evd"}[kind], stable_key)
    return validate_record(item, kind)


def _api_json(path: str, token: str, timeout: int) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    url = API + path
    data, error = _curl_json(url, token=token, accept="application/vnd.github+json")
    if error:
        return None, error
    if not isinstance(data, dict):
        return None, "GitHub API returned a non-object response"
    if data.get("message") and "items" not in data:
        return None, str(data.get("message"))[:240]
    return data, None


def _search(query: str, kind: str, token: str, limit: int, timeout: int):
    qualifier = "in:file" if kind == "code" else ("is:issue" if kind == "issue" else "is:pr")
    path = "/search/%s?%s" % (
        "code" if kind == "code" else "issues",
        urlencode({"q": query + " " + qualifier, "per_page": max(1, min(limit, 10)),
                   "sort": "updated", "order": "desc"}),
    )
    return _api_json(path, token, timeout)


def _requirement_terms(requirement: dict[str, Any], pack: dict[str, Any]) -> list[str]:
    terms = requirement.get("terms") or {}
    candidates = []
    for field in ("canonical", "aliases"):
        candidates.extend(terms.get(field) or [])
    candidates.extend([requirement.get("title", ""), requirement.get("description", "")])
    unit_ids = set(requirement.get("pack_unit_ids") or [])
    for unit in pack.get("modules", []) + pack.get("subsystems", []):
        if unit.get("id") in unit_ids:
            candidates.append(unit.get("name", ""))
            candidates.extend(unit.get("keywords") or [])
    result, seen = [], set()
    for raw in candidates:
        term = " ".join(str(raw or "").split()).strip()
        if len(term) < 2 or term.lower() in seen:
            continue
        seen.add(term.lower())
        result.append(term)
    # Keep requests bounded; canonical and aliases occur before broad descriptions.
    return result[:4]


def _repo_source(repo: dict[str, Any], sources: dict[str, dict[str, Any]]) -> str:
    key = "github|https://github.com"
    source_id = _stable_id("src", key)
    if source_id not in sources:
        sources[source_id] = _record(
            "source", key, provider="github", uri="https://github.com",
            name="github.com", access_status="public",
            metadata={"imported_from": "legacy_seeds"},
        )
    return source_id


def _repository_info(item: dict[str, Any]) -> dict[str, Any]:
    repo = item.get("repository")
    if isinstance(repo, dict) and repo.get("full_name"):
        return repo
    repo_url = str(item.get("repository_url") or "")
    parts = [part for part in urlsplit(repo_url).path.split("/") if part]
    if len(parts) >= 3 and parts[0] == "repos":
        return {"full_name": parts[1] + "/" + parts[2]}
    html = [part for part in urlsplit(str(item.get("html_url") or "")).path.split("/") if part]
    if len(html) >= 2:
        return {"full_name": html[0] + "/" + html[1]}
    return {}


def _asset(source_id: str, kind: str, uri: str, title: str,
           metadata: dict[str, Any]) -> dict[str, Any]:
    key = kind + "|" + uri
    return _record("asset", key, source_id=source_id, asset_type=kind,
                   uri=uri, title=title, version_ref=metadata.get("version_ref"),
                   status="active", metadata=metadata)


def _evidence(workspace_id: str, asset_id: str, kind: str, statement: str,
              locator: dict[str, Any], version_ref: Optional[str], captured_at: str):
    key = json.dumps([asset_id, locator, statement, captured_at], sort_keys=True, ensure_ascii=False)
    return _record(
        "evidence", key, workspace_id=workspace_id, asset_id=asset_id,
        requirement_id=None, criterion_id=None, evidence_kind=kind,
        statement=statement[:2000], excerpt=statement[:2000], locator=locator,
        asset_version_ref=version_ref, captured_at=captured_at,
        extractor={"name": "github-discovery", "version": "1"},
        verification_status="source_confirmed", license_status="unknown",
    )


def discover_github(requirements: list[dict[str, Any]], pack: dict[str, Any],
                    workspace_id: str, token: Optional[str] = None,
                    limit_per_query: int = 5, timeout: int = 25) -> dict[str, Any]:
    """Discover candidate GitHub files, Issues, and PRs for supplied requirements."""
    token = token or os.environ.get("GITHUB_TOKEN")
    if not token:
        return {"sources": [], "assets": [], "evidence": [], "matches": {},
                "warnings": ["GitHub discovery skipped: GITHUB_TOKEN is not configured"],
                "counts": {"code": 0, "issues": 0, "pull_requests": 0}}
    sources: dict[str, dict[str, Any]] = {}
    assets: dict[str, dict[str, Any]] = {}
    evidence: dict[str, dict[str, Any]] = {}
    matches: dict[str, set[str]] = {item["id"]: set() for item in requirements}
    warnings: list[str] = []
    counts = {"code": 0, "issues": 0, "pull_requests": 0}
    counted_assets: dict[str, str] = {}
    repo_heads: dict[str, str] = {}
    captured_at = _now()

    for requirement in requirements:
        for term in _requirement_terms(requirement, pack):
            for kind in ("code", "issue", "pull_request"):
                response, error = _search(term, kind, token, limit_per_query, timeout)
                if error:
                    warnings.append("%s %s search failed: %s" % (requirement["key"], kind, error))
                    continue
                items = response.get("items") or []
                for item in items:
                    repo = _repository_info(item)
                    full_name = str(repo.get("full_name") or "")
                    path = str(item.get("path") or "")
                    html_url = str(item.get("html_url") or "")
                    if not full_name or not html_url:
                        continue
                    source_id = _repo_source(repo, sources)
                    if kind == "code":
                        branch = str(repo.get("default_branch") or "HEAD")
                        uri = html_url
                        asset_kind = "file"
                        title = path or html_url
                        version_ref = str(repo_heads.get(full_name) or "")
                        if not version_ref:
                            head_data, head_error = _api_json(
                                "/repos/%s/commits/%s" % (full_name, quote(branch, safe="")),
                                token, timeout)
                            if head_error:
                                warnings.append("could not resolve repository HEAD for %s: %s" %
                                                (full_name, head_error[:160]))
                                version_ref = branch
                            else:
                                version_ref = str(head_data.get("sha") or branch)
                            repo_heads[full_name] = version_ref
                        asset_metadata = {"path": path, "repository": full_name,
                                          "default_branch": branch, "version_ref": version_ref,
                                          "matched_requirement_keys": [requirement["key"]]}
                        asset = _asset(source_id, asset_kind, uri, title, asset_metadata)
                        existing_asset = assets.get(asset["id"])
                        if existing_asset:
                            keys = set(existing_asset.get("metadata", {}).get("matched_requirement_keys", []))
                            keys.add(requirement["key"])
                            existing_asset["metadata"]["matched_requirement_keys"] = sorted(keys)
                        else:
                            assets[asset["id"]] = asset
                            counted_assets[asset["id"]] = "code"
                            counts["code"] += 1
                        matches[requirement["id"]].add(asset["id"])

                        # Search result text_matches are excerpts, not reliable line locators.
                        # Fetch the current file and calculate actual line positions.
                        if path and version_ref:
                            content_path = "/repos/%s/contents/%s?ref=%s" % (
                                full_name, quote(path, safe="/"), quote(version_ref, safe=""))
                            raw_url = API + content_path
                            from .verify import _curl_text
                            body, status, fetch_error = _curl_text(
                                raw_url, headers=["Accept: application/vnd.github.raw",
                                                  "Authorization: Bearer %s" % token],
                                timeout=timeout)
                            if fetch_error:
                                warnings.append("file content fetch failed for %s: %s" %
                                                (html_url, fetch_error[:160]))
                            else:
                                query_terms = [term.lower()]
                                lines = (body or "").splitlines()
                                hit_lines = []
                                for line_no, line in enumerate(lines, 1):
                                    if any(q in line.lower() for q in query_terms):
                                        hit_lines.append((line_no, line.strip()))
                                    if len(hit_lines) >= 5:
                                        break
                                for line_no, line in hit_lines:
                                    if not line:
                                        continue
                                    ev = _evidence(
                                        workspace_id, asset["id"], "code", line,
                                        {"path": path, "line_start": line_no,
                                         "line_end": line_no, "ref": version_ref},
                                        version_ref, captured_at)
                                    evidence[ev["id"]] = ev
                    else:
                        number = item.get("number")
                        if not isinstance(number, int):
                            continue
                        is_pr = kind == "pull_request" or bool(item.get("pull_request"))
                        asset_kind = "pull_request" if is_pr else "issue"
                        uri = html_url
                        title = str(item.get("title") or "%s #%s" % (full_name, number))
                        version_ref = str(item.get("updated_at") or "")
                        body = str(item.get("body") or "")
                        asset_metadata = {
                            "repository": full_name, "number": number,
                            "state": item.get("state"), "created_at": item.get("created_at"),
                            "updated_at": item.get("updated_at"),
                            "matched_requirement_keys": [requirement["key"]],
                            "labels": [x.get("name") for x in item.get("labels") or []],
                        }
                        asset = _asset(source_id, asset_kind, uri, title, asset_metadata)
                        existing_asset = assets.get(asset["id"])
                        if existing_asset:
                            keys = set(existing_asset.get("metadata", {}).get("matched_requirement_keys", []))
                            keys.add(requirement["key"])
                            existing_asset["metadata"]["matched_requirement_keys"] = sorted(keys)
                        else:
                            assets[asset["id"]] = asset
                            counted_assets[asset["id"]] = "pull_requests" if is_pr else "issues"
                            counts[counted_assets[asset["id"]]] += 1
                        matches[requirement["id"]].add(asset["id"])
                        text = (title + "\n" + body).strip()
                        if text:
                            locator = {"url": html_url, "field": "title+body",
                                       "updated_at": version_ref}
                            ev = _evidence(workspace_id, asset["id"],
                                           "pull_request" if is_pr else "issue",
                                           text, locator, version_ref, captured_at)
                            evidence[ev["id"]] = ev

    return {
        "sources": list(sources.values()), "assets": list(assets.values()),
        "evidence": list(evidence.values()),
        "matches": {key: sorted(value) for key, value in matches.items()},
        "warnings": warnings, "counts": counts,
    }
