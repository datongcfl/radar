"""Requirement-driven GitHub discovery for files, Issues, and pull requests.

The adapter is opt-in and requires GITHUB_TOKEN. Search results are candidates,
not proof that a requirement is implemented.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Optional
from urllib.parse import quote, urlencode, urlsplit
import re
import json
import os

from .adapters import _curl_json
from .discovery import new_record, validate_record
from .verify import _curl_text
from .document_parser import extract_csv_document, extract_office_document
import base64


API = "https://api.github.com"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _stable_id(prefix: str, key: str) -> str:
    return prefix + "_" + sha256(key.encode("utf-8")).hexdigest()[:32]


def _record(kind: str, stable_key: str, **fields: Any) -> dict[str, Any]:
    item = new_record(kind, **fields).to_dict()
    item["id"] = _stable_id({"source": "src", "asset": "ast", "evidence": "evd",
                              "relationship": "rel"}[kind], stable_key)
    return validate_record(item, kind)


def _api_json(path: str, token: str, timeout: int) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    url = API + path
    data, error = _curl_json(url, token=token, accept="application/vnd.github+json", timeout=timeout)
    if error:
        return None, error
    if not isinstance(data, dict):
        return None, "GitHub API returned a non-object response"
    if data.get("message") and "items" not in data:
        return None, str(data.get("message"))[:240]
    return data, None


def _api_list(path: str, token: str, timeout: int) -> tuple[Optional[list[dict[str, Any]]], Optional[str]]:
    data, error = _curl_json(API + path, token=token,
                             accept="application/vnd.github+json", timeout=timeout)
    if error:
        return None, error
    if not isinstance(data, list):
        return None, "GitHub API returned a non-array response"
    return data, None


def _added_patch_lines(patch: str) -> list[tuple[int, str]]:
    """Return added lines with their new-file line numbers from a unified diff."""
    current_line = None
    found = []
    for line in (patch or "").splitlines():
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)(?:,\d+)?", line)
            current_line = int(match.group(1)) if match else None
        elif line.startswith(("+++", "---")):
            continue
        elif line.startswith("+"):
            if current_line is not None and line[1:].strip():
                found.append((current_line, line[1:].strip()))
            if current_line is not None:
                current_line += 1
        elif line.startswith("-"):
            continue
        elif current_line is not None and line.startswith(" "):
            current_line += 1
    return found[:20]


def _relationship(from_type: str, from_id: str, to_type: str, to_id: str) -> dict[str, Any]:
    key = json.dumps([from_type, from_id, "contains", to_type, to_id], separators=(",", ":"))
    return _record("relationship", key,
        **{"from": {"object_type": from_type, "id": from_id},
           "to": {"object_type": to_type, "id": to_id},
           "relation_type": "contains", "confidence": 1.0,
           "evidence_ids": [], "status": "active", "created_by": "radar"})


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


def _code_ref_from_url(url: str) -> Optional[str]:
    parts = [part for part in urlsplit(url).path.split("/") if part]
    if len(parts) >= 5 and parts[2] == "blob":
        return parts[3]
    return None


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
    version_ref = metadata.get("version_ref")
    key = kind + "|" + uri + "|" + str(version_ref or "current")
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



def _append_discussion_item(workspace_id: str, source_id: str, parent_asset: dict[str, Any],
                            repo: str, number: int, item: dict[str, Any],
                            item_kind: str, evidence_kind: str, captured_at: str,
                            assets: dict[str, dict[str, Any]],
                            evidence: dict[str, dict[str, Any]],
                            relationships: dict[str, dict[str, Any]]) -> bool:
    body = str(item.get("body") or "").strip()
    if not body:
        return False
    uri = str(item.get("html_url") or item.get("url") or parent_asset["uri"])
    title = "%s #%s %s" % (repo, number, item_kind.replace("_", " "))
    metadata = {
        "repository": repo, "parent_asset_id": parent_asset["id"],
        "discussion_type": item_kind, "comment_id": item.get("id"),
        "author": (item.get("user") or {}).get("login"),
        "created_at": item.get("created_at"), "updated_at": item.get("updated_at"),
    }
    child = _asset(source_id, "other", uri, title, metadata)
    assets[child["id"]] = child
    rel = _relationship("asset", parent_asset["id"], "asset", child["id"])
    relationships[rel["id"]] = rel
    locator = {"url": uri, "field": "body", "parent_url": parent_asset["uri"],
               "comment_id": item.get("id"), "discussion_type": item_kind}
    if item.get("path"):
        locator["path"] = item.get("path")
    if item.get("line") is not None:
        locator["line"] = item.get("line")
    if item.get("commit_id"):
        locator["commit_id"] = item.get("commit_id")
    if item.get("diff_hunk"):
        locator["diff_hunk"] = str(item.get("diff_hunk"))[:1000]
    version = str(item.get("updated_at") or item.get("created_at") or "") or None
    ev = _evidence(workspace_id, child["id"], evidence_kind, body, locator, version, captured_at)
    evidence[ev["id"]] = ev
    return True


def discover_github(requirements: list[dict[str, Any]], pack: dict[str, Any],
                    workspace_id: str, token: Optional[str] = None,
                    limit_per_query: int = 5, timeout: int = 25) -> dict[str, Any]:
    """Discover candidate GitHub files, Issues, PRs, and parseable documents for supplied requirements."""
    token = token or os.environ.get("GITHUB_TOKEN")
    if not token:
        return {"sources": [], "assets": [], "evidence": [], "matches": {},
                "warnings": ["GitHub discovery skipped: GITHUB_TOKEN is not configured"],
                "counts": {"code": 0, "issues": 0, "pull_requests": 0, "pr_files": 0, "documents": 0, "unsupported_documents": 0, "parsed_documents": 0, "parse_failures": 0, "issue_comments": 0, "pr_review_items": 0, "ci_checks": 0, "ci_statuses": 0},
                                     "relationships": []}
    sources: dict[str, dict[str, Any]] = {}
    assets: dict[str, dict[str, Any]] = {}
    evidence: dict[str, dict[str, Any]] = {}
    relationships: dict[str, dict[str, Any]] = {}
    matches: dict[str, set[str]] = {item["id"]: set() for item in requirements}
    warnings: list[str] = []
    counts = {"code": 0, "issues": 0, "pull_requests": 0, "pr_files": 0, "documents": 0, "unsupported_documents": 0, "parsed_documents": 0, "parse_failures": 0, "issue_comments": 0, "pr_review_items": 0, "ci_checks": 0, "ci_statuses": 0}
    counted_assets: dict[str, str] = {}
    repo_heads: dict[str, tuple[str, bool]] = {}
    discovered_repos: dict[str, dict[str, Any]] = {}
    captured_at = _now()

    if not 1 <= limit_per_query <= 10:
        raise ValueError("github limit_per_query must be between 1 and 10")

    for requirement in requirements:
        terms = _requirement_terms(requirement, pack)
        if not terms:
            warnings.append("%s has no searchable terms" % requirement.get("key", requirement["id"]))
            continue
        query = " OR ".join('"%s"' % term.replace('"', '\\"') for term in terms)
        for kind in ("code", "issue", "pull_request"):
            response, error = _search(query, kind, token, limit_per_query, timeout)
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
                discovered_repos.setdefault(full_name, repo)
                source_id = _repo_source(repo, sources)
                if kind == "code":
                    branch = str(repo.get("default_branch") or "HEAD")
                    cached_head = repo_heads.get(full_name)
                    if cached_head:
                        version_ref, immutable_ref = cached_head
                    else:
                        result_ref = _code_ref_from_url(html_url)
                        immutable_ref = bool(result_ref and re.fullmatch(r"[0-9a-fA-F]{40,64}", result_ref))
                        if immutable_ref:
                            version_ref = result_ref
                        else:
                            head_data, head_error = _api_json(
                                "/repos/%s/commits/%s" % (full_name, quote(branch, safe="")),
                                token, timeout)
                            immutable_ref = not head_error and bool(head_data.get("sha"))
                            if immutable_ref:
                                version_ref = str(head_data["sha"])
                            else:
                                version_ref = result_ref or branch
                                warnings.append("could not resolve immutable HEAD for %s: %s" %
                                                (full_name, (head_error or "missing commit SHA")[:160]))
                        repo_heads[full_name] = (version_ref, immutable_ref)
                    uri = "https://github.com/%s/blob/%s/%s" % (
                        full_name, version_ref, quote(path, safe="/"))
                    asset_kind = "file"
                    title = path or html_url
                    asset_metadata = {"path": path, "repository": full_name,
                                      "default_branch": branch, "version_ref": version_ref,
                                      "matched_by": "github_code_search"}
                    asset = _asset(source_id, asset_kind, uri, title, asset_metadata)
                    if asset["id"] not in assets:
                        assets[asset["id"]] = asset
                        counted_assets[asset["id"]] = "code"
                        counts["code"] += 1
                    matches[requirement["id"]].add(asset["id"])

                    # Search result text_matches are excerpts, not reliable line locators.
                    # Fetch the current file and calculate actual line positions.
                    if path and immutable_ref:
                        content_path = "/repos/%s/contents/%s?ref=%s" % (
                            full_name, quote(path, safe="/"), quote(version_ref, safe=""))
                        raw_url = API + content_path
                        body, status, fetch_error = _curl_text(
                            raw_url, headers=["Accept: application/vnd.github.raw",
                                              "Authorization: Bearer %s" % token],
                            timeout=timeout)
                        if fetch_error:
                            warnings.append("file content fetch failed for %s: %s" %
                                            (html_url, fetch_error[:160]))
                        else:
                            query_terms = [value.lower() for value in terms]
                            lines = (body or "").splitlines()
                            hit_lines = []
                            for line_no, line in enumerate(lines, 1):
                                if any(q in line.lower() for q in query_terms):
                                    hit_lines.append((line_no, line.strip()))
                                if len(hit_lines) >= 5:
                                    break
                            extension = path.rsplit(".", 1)[-1].lower() if "." in path else ""
                            evidence_kind = ("documentation" if extension in
                                             ("md", "rst", "txt", "adoc", "html", "yaml", "yml", "json")
                                             else "code")
                            for line_no, line in hit_lines:
                                if not line:
                                    continue
                                ev = _evidence(
                                    workspace_id, asset["id"], evidence_kind, line,
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
                        "matched_by": "github_issue_search",
                        "labels": [x.get("name") for x in item.get("labels") or []],
                    }
                    asset = _asset(source_id, asset_kind, uri, title, asset_metadata)
                    if asset["id"] not in assets:
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

                    # M9: collect bounded discussion evidence for both Issues and PRs.
                    issue_comments, comments_error = _api_list(
                        "/repos/%s/issues/%s/comments?per_page=20" % (full_name, number),
                        token, timeout)
                    if comments_error:
                        warnings.append("Issue comments fetch failed for %s: %s" %
                                        (html_url, comments_error[:160]))
                    else:
                        for comment in issue_comments or []:
                            if _append_discussion_item(
                                    workspace_id, source_id, asset, full_name, number,
                                    comment, "issue_comment",
                                    "pull_request" if is_pr else "issue",
                                    captured_at, assets, evidence, relationships):
                                counts["issue_comments"] += 1

                    if is_pr:
                        pr_data, pr_error = _api_json(
                            "/repos/%s/pulls/%s" % (full_name, number), token, timeout)
                        if pr_error:
                            warnings.append("PR details fetch failed for %s: %s" %
                                            (html_url, pr_error[:160]))
                            continue
                        head_sha = str((pr_data.get("head") or {}).get("sha") or "")
                        files, files_error = _api_list(
                            "/repos/%s/pulls/%s/files?per_page=10" % (full_name, number),
                            token, timeout)
                        if files_error:
                            warnings.append("PR files fetch failed for %s: %s" %
                                            (html_url, files_error[:160]))
                            continue
                        for changed in files or []:
                            filename = str(changed.get("filename") or "")
                            if not filename:
                                continue
                            file_uri = ("https://github.com/%s/blob/%s/%s" %
                                        (full_name, head_sha, quote(filename, safe="/"))
                                        if head_sha else str(changed.get("blob_url") or html_url))
                            file_metadata = {
                                "path": filename, "repository": full_name,
                                "version_ref": head_sha or None,
                                "derived_from_pull_request": number,
                                "change_status": changed.get("status"),
                                "additions": changed.get("additions", 0),
                                "deletions": changed.get("deletions", 0),
                            }
                            file_asset = _asset(source_id, "file", file_uri, filename, file_metadata)
                            if file_asset["id"] not in assets:
                                assets[file_asset["id"]] = file_asset
                                counts["pr_files"] += 1
                            matches[requirement["id"]].add(file_asset["id"])
                            rel = _relationship("asset", asset["id"], "asset", file_asset["id"])
                            relationships[rel["id"]] = rel
                            extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
                            evidence_kind = ("documentation" if extension in
                                             ("md", "rst", "txt", "adoc", "html", "yaml", "yml", "json")
                                             else "code")
                            for line_no, added_line in _added_patch_lines(changed.get("patch") or ""):
                                ev = _evidence(
                                    workspace_id, file_asset["id"], evidence_kind, added_line,
                                    {"path": filename, "line_start": line_no,
                                     "line_end": line_no, "ref": head_sha,
                                     "pull_request": number},
                                    head_sha or None, captured_at)
                                evidence[ev["id"]] = ev

                        # Inline review comments and submitted reviews are separate evidence.
                        review_comments, review_error = _api_list(
                            "/repos/%s/pulls/%s/comments?per_page=20" % (full_name, number),
                            token, timeout)
                        if review_error:
                            warnings.append("PR review comments fetch failed for %s: %s" %
                                            (html_url, review_error[:160]))
                        else:
                            for comment in review_comments or []:
                                if _append_discussion_item(
                                        workspace_id, source_id, asset, full_name, number,
                                        comment, "review_comment", "pull_request",
                                        captured_at, assets, evidence, relationships):
                                    counts["pr_review_items"] += 1
                        reviews, reviews_error = _api_list(
                            "/repos/%s/pulls/%s/reviews?per_page=20" % (full_name, number),
                            token, timeout)
                        if reviews_error:
                            warnings.append("PR reviews fetch failed for %s: %s" %
                                            (html_url, reviews_error[:160]))
                        else:
                            for review in reviews or []:
                                if _append_discussion_item(
                                        workspace_id, source_id, asset, full_name, number,
                                        review, "review", "pull_request",
                                        captured_at, assets, evidence, relationships):
                                    counts["pr_review_items"] += 1

                        # Associate CI checks with the immutable PR head commit.
                        if head_sha:
                            check_data, check_error = _api_json(
                                "/repos/%s/commits/%s/check-runs?per_page=20" %
                                (full_name, quote(head_sha, safe="")), token, timeout)
                            if check_error:
                                warnings.append("commit check-runs fetch failed for %s: %s" %
                                                (html_url, check_error[:160]))
                            else:
                                for check in check_data.get("check_runs") or []:
                                    output = check.get("output") or {}
                                    statement = "%s: status=%s; conclusion=%s" % (
                                        check.get("name") or "CI check",
                                        check.get("status") or "unknown",
                                        check.get("conclusion") or "pending")
                                    summary = str(output.get("summary") or output.get("text") or "").strip()
                                    if summary:
                                        statement += "\n" + summary
                                    check_uri = str(check.get("html_url") or check.get("details_url") or html_url)
                                    check_asset = _asset(source_id, "other", check_uri,
                                        str(check.get("name") or "CI check"),
                                        {"repository": full_name, "check_run_id": check.get("id"),
                                         "head_sha": head_sha, "check_status": check.get("status"),
                                         "conclusion": check.get("conclusion")})
                                    assets[check_asset["id"]] = check_asset
                                    rel = _relationship("asset", asset["id"], "asset", check_asset["id"])
                                    relationships[rel["id"]] = rel
                                    ev = _evidence(workspace_id, check_asset["id"], "test", statement,
                                        {"url": check_uri, "check_run_id": check.get("id"),
                                         "head_sha": head_sha, "field": "check_run"},
                                        head_sha, captured_at)
                                    evidence[ev["id"]] = ev
                                    counts["ci_checks"] += 1

                            status_data, status_error = _api_json(
                                "/repos/%s/commits/%s/status" %
                                (full_name, quote(head_sha, safe="")), token, timeout)
                            if status_error:
                                warnings.append("commit status fetch failed for %s: %s" %
                                                (html_url, status_error[:160]))
                            else:
                                for status_item in status_data.get("statuses") or []:
                                    state = str(status_item.get("state") or "unknown")
                                    context = str(status_item.get("context") or "status")
                                    description = str(status_item.get("description") or "")
                                    statement = "%s: %s%s" % (
                                        context, state, ("; " + description) if description else "")
                                    status_uri = str(status_item.get("target_url") or html_url)
                                    status_asset = _asset(source_id, "other", status_uri,
                                        context, {"repository": full_name, "head_sha": head_sha,
                                                  "status_state": state})
                                    assets[status_asset["id"]] = status_asset
                                    rel = _relationship("asset", asset["id"], "asset", status_asset["id"])
                                    relationships[rel["id"]] = rel
                                    ev = _evidence(workspace_id, status_asset["id"], "test", statement,
                                        {"url": status_uri, "head_sha": head_sha, "field": "commit_status"},
                                        head_sha, captured_at)
                                    evidence[ev["id"]] = ev
                                    counts["ci_statuses"] += 1


    # M7: recursively inspect repository trees so documentation discovery does
    # not depend on GitHub Code Search indexing or README-only repository metadata.
    document_extensions = {"md", "rst", "txt", "adoc", "html", "htm", "yaml", "yml", "csv"}
    binary_document_extensions = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx"}
    office_extensions = {"docx", "xlsx", "pptx"}
    for full_name, repo_hint in sorted(discovered_repos.items()):
        branch_name = str(repo_hint.get("default_branch") or "")
        if not branch_name:
            repo_data, repo_error = _api_json("/repos/%s" % full_name, token, timeout)
            if repo_error:
                warnings.append("repository metadata fetch failed for %s: %s" %
                                (full_name, repo_error[:160]))
                continue
            branch_name = str(repo_data.get("default_branch") or "HEAD")
        head_data, head_error = _api_json(
            "/repos/%s/commits/%s" % (full_name, quote(branch_name, safe="")), token, timeout)
        if head_error or not (head_data or {}).get("sha"):
            warnings.append("document tree skipped for %s: immutable revision unavailable" % full_name)
            continue
        tree_ref = str(head_data["sha"])
        tree_data, tree_error = _api_json(
            "/repos/%s/git/trees/%s?recursive=1" % (full_name, tree_ref), token, timeout)
        if tree_error:
            warnings.append("repository tree fetch failed for %s: %s" %
                            (full_name, tree_error[:160]))
            continue
        if tree_data.get("truncated"):
            warnings.append("repository tree is truncated for %s; document discovery is incomplete" % full_name)
        source_id = _repo_source(repo_hint, sources)
        doc_candidates = []
        for entry in tree_data.get("tree") or []:
            if entry.get("type") != "blob":
                continue
            path = str(entry.get("path") or "")
            ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
            if ext not in document_extensions | binary_document_extensions:
                continue
            lowered = path.lower()
            if any(part in lowered.split("/") for part in
                   (".git", "node_modules", "vendor", "dist", "build", "__pycache__")):
                continue
            if int(entry.get("size") or 0) > 2_000_000:
                continue
            doc_candidates.append((path, ext, entry))
        doc_candidates.sort(key=lambda row: (
            0 if row[1] in document_extensions else 1,
            0 if any(token in row[0].lower() for token in
                     ("design", "architecture", "requirement", "workflow", "process", "manual", "spec")) else 1,
            row[0].lower()))
        for path, ext, entry in doc_candidates[:max(10, limit_per_query * 4)]:
            uri = "https://github.com/%s/blob/%s/%s" % (
                full_name, tree_ref, quote(path, safe="/"))
            is_text_doc = ext in document_extensions
            is_csv_doc = ext == "csv"
            is_office_doc = ext in office_extensions
            metadata = {
                "path": path, "repository": full_name, "version_ref": tree_ref,
                "blob_sha": entry.get("sha"), "size": entry.get("size", 0),
                "matched_by": "github_recursive_tree",
                "document_format": ext,
                "content_extraction": "pending" if is_office_doc else ("text" if is_text_doc else "unsupported_binary"),
            }
            asset = _asset(source_id, "file", uri, path, metadata)
            if asset["id"] not in assets:
                assets[asset["id"]] = asset
                counts["documents" if (is_text_doc or is_office_doc) else "unsupported_documents"] += 1
            if is_text_doc:
                raw_url = "https://raw.githubusercontent.com/%s/%s/%s" % (
                    full_name, tree_ref, quote(path, safe="/"))
                body, status, fetch_error = _curl_text(
                    raw_url, headers=["Authorization: Bearer %s" % token], timeout=timeout)
                if fetch_error:
                    warnings.append("document fetch failed for %s: %s" % (uri, fetch_error[:160]))
                    continue
                if is_csv_doc:
                    parsed = extract_csv_document(body or "")
                    asset["metadata"]["content_extraction"] = parsed["status"]
                    asset["metadata"]["parser"] = "stdlib-csv"
                    if parsed["status"] != "parsed":
                        counts["parse_failures"] += 1
                        warnings.append("CSV parsing failed for %s: %s" %
                                        (uri, parsed.get("reason") or "no reason"))
                        continue
                    counts["parsed_documents"] += 1
                    chunks = parsed["chunks"]
                else:
                    chunks = [{"text": line.strip(), "locator": {
                        "line_start": line_no, "line_end": line_no, "block": "line"}}
                        for line_no, line in enumerate((body or "").splitlines(), 1) if line.strip()]
                    asset["metadata"]["content_extraction"] = "text"
            elif is_office_doc:
                blob_data, blob_error = _api_json(
                    "/repos/%s/git/blobs/%s" % (full_name, entry.get("sha")), token, timeout)
                if blob_error or not (blob_data or {}).get("content"):
                    counts["parse_failures"] += 1
                    asset["metadata"]["content_extraction"] = "failed"
                    warnings.append("Office document blob fetch failed for %s: %s" %
                                    (uri, (blob_error or "missing blob content")[:160]))
                    continue
                try:
                    raw_bytes = base64.b64decode(blob_data["content"])
                except (ValueError, TypeError) as exc:
                    counts["parse_failures"] += 1
                    asset["metadata"]["content_extraction"] = "failed"
                    warnings.append("Office document base64 decode failed for %s: %s" %
                                    (uri, str(exc)[:120]))
                    continue
                parsed = extract_office_document(raw_bytes, ext)
                asset["metadata"]["content_extraction"] = parsed["status"]
                asset["metadata"]["parser"] = "stdlib-office-xml"
                if parsed["status"] != "parsed":
                    counts["parse_failures"] += 1
                    warnings.append("Office document parsing %s for %s: %s" %
                                    (parsed["status"], uri, parsed.get("reason") or "no reason"))
                    continue
                counts["parsed_documents"] += 1
                chunks = parsed["chunks"]
            else:
                continue

            for requirement in requirements:
                terms = _requirement_terms(requirement, pack)
                hits = [chunk for chunk in chunks if any(
                    term.lower() in chunk["text"].lower() for term in terms)]
                if not hits:
                    continue
                matches[requirement["id"]].add(asset["id"])
                for chunk in hits[:10]:
                    locator = dict(chunk["locator"])
                    locator.update({"path": path, "ref": tree_ref,
                                    "blob_sha": entry.get("sha")})
                    ev = _evidence(
                        workspace_id, asset["id"], "documentation", chunk["text"],
                        locator, tree_ref, captured_at)
                    ev["extractor"] = {"name": "stdlib-office-xml" if is_office_doc else ("stdlib-csv" if is_csv_doc else "github-text"), "version": "1"}
                    evidence[ev["id"]] = ev

    return {
        "sources": list(sources.values()), "assets": list(assets.values()),
        "evidence": list(evidence.values()), "relationships": list(relationships.values()),
        "matches": {key: sorted(value) for key, value in matches.items()},
        "warnings": warnings, "counts": counts,
    }
