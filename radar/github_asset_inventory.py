"""Bounded GitHub repository tree inventory as source-native Asset candidates.

This capability inventories immutable Git objects only. It does not fetch file
bodies, create Evidence, or infer that a discovered file supports a requirement.
"""
from __future__ import annotations

import json
import re
import subprocess
import urllib.parse
from typing import Any, Mapping

from .capabilities import CapabilityContext, CapabilityDescriptor, CapabilityResult

_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
_IGNORED_SEGMENTS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", "dist", "build",
    "__pycache__", ".venv", "venv", ".tox", ".mypy_cache", ".pytest_cache",
}
_DOCUMENT_TYPES = {
    ".md": ("document", "text/markdown", "text"),
    ".markdown": ("document", "text/markdown", "text"),
    ".rst": ("document", "text/x-rst", "text"),
    ".txt": ("document", "text/plain", "text"),
    ".adoc": ("document", "text/asciidoc", "text"),
    ".asciidoc": ("document", "text/asciidoc", "text"),
    ".html": ("document", "text/html", "text"),
    ".htm": ("document", "text/html", "text"),
    ".pdf": ("document", "application/pdf", "pdf"),
    ".docx": ("document", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
    ".xlsx": ("document", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
    ".pptx": ("document", "application/vnd.openxmlformats-officedocument.presentationml.presentation", "pptx"),
    ".csv": ("document", "text/csv", "text"),
}
_SOURCE_TYPES = {
    ".py", ".pyi", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx",
    ".java", ".go", ".rs", ".c", ".h", ".cpp", ".hpp", ".cs", ".rb",
    ".php", ".sh", ".bash", ".zsh", ".sql", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".xml", ".css", ".scss", ".java", ".kt", ".swift",
    ".gradle", ".properties", ".proto", ".graphql",
}


def _request_json(url: str, token: str | None) -> tuple[Any, str | None, int]:
    command = [
        "curl", "-sS", "--max-time", "25",
        "-H", "User-Agent: radar-asset-inventory",
        "-H", "Accept: application/vnd.github+json",
        "-w", "\\n%{http_code}",
    ]
    if token:
        command += ["-H", "Authorization: Bearer " + token]
    command.append(url)
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=30,
        )
    except Exception as exc:
        return None, type(exc).__name__, 0
    if result.returncode:
        return None, "network_error", 0
    body, _, status_text = result.stdout.rpartition("\\n")
    try:
        status = int(status_text.strip())
    except ValueError:
        return None, "invalid_http_response", 0
    try:
        data = json.loads(body)
    except (TypeError, ValueError):
        return None, "invalid_json_response", status
    if status < 200 or status >= 300:
        return None, "github_http_%d" % status, status
    return data, None, status


def _classify(path: str) -> tuple[str, str, str] | None:
    name = path.rsplit("/", 1)[-1]
    dot = name.rfind(".")
    extension = name[dot:].lower() if dot >= 0 else ""
    if extension in _DOCUMENT_TYPES:
        return _DOCUMENT_TYPES[extension]
    if extension in _SOURCE_TYPES:
        return "file", "text/plain", "text"
    if name.lower() in ("readme", "license", "copying", "notice", "changelog", "makefile", "dockerfile"):
        return "document", "text/plain", "text"
    return None


def _safe_path(path: Any) -> bool:
    if not isinstance(path, str) or not path or path.startswith("/"):
        return False
    parts = path.split("/")
    return all(part not in ("", ".", "..") for part in parts)


class GithubRepositoryAssetInventoryCapability:
    """Discover bounded file Asset candidates from one immutable repository tree."""

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="github-assets",
            kind="source",
            version="1.0.0",
            description="Bounded GitHub repository file and document asset inventory",
        )

    def execute(self, context: CapabilityContext) -> CapabilityResult:
        if context.operation != "inventory":
            return CapabilityResult(status="failed", error={"code": "unsupported_operation"})
        repository = context.inputs.get("repository")
        if not isinstance(repository, str) or not _REPOSITORY.fullmatch(repository):
            return CapabilityResult(status="failed", error={"code": "invalid_repository"})
        token = context.parameters.get("token")
        if token is not None and (not isinstance(token, str) or not token.strip()):
            return CapabilityResult(status="failed", error={"code": "invalid_token"})
        ref = context.parameters.get("ref")
        if ref is not None and (not isinstance(ref, str) or not ref.strip() or len(ref) > 250):
            return CapabilityResult(status="failed", error={"code": "invalid_ref"})
        max_files = context.parameters.get("max_files", 2000)
        max_file_bytes = context.parameters.get("max_file_bytes", 2_000_000)
        if isinstance(max_files, bool) or not isinstance(max_files, int) or not 1 <= max_files <= 10000:
            return CapabilityResult(status="failed", error={"code": "invalid_max_files"})
        if isinstance(max_file_bytes, bool) or not isinstance(max_file_bytes, int) or not 1 <= max_file_bytes <= 20_000_000:
            return CapabilityResult(status="failed", error={"code": "invalid_max_file_bytes"})

        api = "https://api.github.com/repos/" + repository
        repo_data, error, status = _request_json(api, token)
        if error:
            return CapabilityResult(status="failed", error={"code": "github_repository_unavailable", "http_status": status or None, "reason": error})
        selected_ref = ref or repo_data.get("default_branch")
        if not isinstance(selected_ref, str) or not selected_ref:
            return CapabilityResult(status="failed", error={"code": "github_default_branch_missing"})
        encoded_ref = urllib.parse.quote(selected_ref, safe="")
        commit_data, error, status = _request_json(api + "/commits/" + encoded_ref, token)
        if error:
            return CapabilityResult(status="failed", error={"code": "github_ref_unavailable", "http_status": status or None, "reason": error})
        commit = commit_data.get("sha")
        tree_sha = ((commit_data.get("commit") or {}).get("tree") or {}).get("sha")
        if not isinstance(commit, str) or not isinstance(tree_sha, str):
            return CapabilityResult(status="failed", error={"code": "github_commit_response_invalid"})
        tree_data, error, status = _request_json(api + "/git/trees/" + tree_sha + "?recursive=1", token)
        if error:
            return CapabilityResult(status="failed", error={"code": "github_tree_unavailable", "http_status": status or None, "reason": error})
        entries = tree_data.get("tree")
        if not isinstance(entries, list):
            return CapabilityResult(status="failed", error={"code": "github_tree_response_invalid"})

        records = []
        skipped_ignored = 0
        skipped_unsupported = 0
        skipped_large = 0
        for entry in entries:
            if not isinstance(entry, Mapping) or entry.get("type") != "blob":
                continue
            path = entry.get("path")
            if not _safe_path(path):
                skipped_unsupported += 1
                continue
            segments = path.split("/")
            if any(segment.lower() in _IGNORED_SEGMENTS for segment in segments):
                skipped_ignored += 1
                continue
            classification = _classify(path)
            if classification is None:
                skipped_unsupported += 1
                continue
            size = entry.get("size")
            if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                skipped_unsupported += 1
                continue
            if size > max_file_bytes:
                skipped_large += 1
                continue
            if len(records) >= max_files:
                break
            asset_type, media_type, parser_hint = classification
            blob_sha = entry.get("sha")
            if not isinstance(blob_sha, str) or not re.fullmatch(r"[a-f0-9]{40,64}", blob_sha):
                skipped_unsupported += 1
                continue
            encoded_path = urllib.parse.quote(path, safe="/")
            records.append({
                "record_type": "repository_asset_candidate",
                "provider": "github",
                "repository": repository,
                "repository_uri": "https://github.com/" + repository,
                "commit_sha": commit,
                "tree_sha": tree_sha,
                "path": path,
                "blob_sha": blob_sha,
                "size_bytes": size,
                "asset_type": asset_type,
                "media_type": media_type,
                "parser_hint": parser_hint,
                "uri": "https://github.com/" + repository + "/blob/" + commit + "/" + encoded_path,
                "content_fetch_status": "not_fetched",
                "evidence_promoted": False,
            })
        warnings = []
        truncated = tree_data.get("truncated") is True
        if truncated:
            warnings.append({"code": "github_tree_truncated", "message": "GitHub returned a truncated tree; inventory is incomplete"})
        if len(records) >= max_files and len(entries) > len(records):
            warnings.append({"code": "asset_limit_reached", "limit": max_files})
        status = "partial" if warnings else "succeeded"
        return CapabilityResult(
            status=status,
            records=tuple(records),
            warnings=tuple(warnings),
            metadata={
                "provider": "github",
                "repository": repository,
                "ref": selected_ref,
                "commit_sha": commit,
                "tree_sha": tree_sha,
                "tree_truncated": truncated,
                "candidate_count": len(records),
                "skipped_ignored": skipped_ignored,
                "skipped_unsupported": skipped_unsupported,
                "skipped_large": skipped_large,
                "max_files": max_files,
                "max_file_bytes": max_file_bytes,
                "content_fetched": False,
                "evidence_promoted": False,
            },
        )
