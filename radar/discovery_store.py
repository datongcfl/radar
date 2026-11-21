"""Append-only JSON/JSONL storage for discovery workspaces (stdlib only)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol
import hashlib
import json
import os
import re
import tempfile

from .discovery import DiscoveryValidationError, validate_record


class StorageError(RuntimeError):
    pass


class Storage(Protocol):
    def append(self, record: dict[str, Any]) -> None: ...
    def get(self, object_type: str, record_id: str) -> dict[str, Any] | None: ...
    def list_records(self, object_type: str) -> list[dict[str, Any]]: ...
    def save_snapshot(self, content: bytes | str) -> str: ...


_COLLECTIONS = {
    "requirement": "requirements.jsonl",
    "source": "sources.jsonl",
    "asset": "assets.jsonl",
    "evidence": "evidence.jsonl",
    "relationship": "relationships.jsonl",
    "assessment": "assessments.jsonl",
}


def _json_bytes(data: Any) -> bytes:
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".radar-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


class JsonWorkspaceStore:
    """One Workspace boundary; records and snapshots are never shared implicitly."""

    def __init__(self, root: str | Path, workspace_id: str):
        if not re.match(r"^ws_[A-Za-z0-9][A-Za-z0-9._-]{1,127}$", workspace_id or ""):
            raise StorageError("invalid workspace id")
        self.root = Path(root).expanduser().resolve() / "workspaces" / workspace_id
        self.workspace_id = workspace_id

    def initialize(self, workspace: dict[str, Any]) -> None:
        data = validate_record(workspace, "workspace")
        if data["id"] != self.workspace_id:
            raise StorageError("workspace record id does not match store boundary")
        path = self.root / "workspace.json"
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing.get("id") != self.workspace_id:
                raise StorageError("workspace directory identity mismatch")
            return
        _atomic_write(path, _json_bytes(data))

    def _ensure_initialized(self) -> None:
        if not (self.root / "workspace.json").is_file():
            raise StorageError("workspace is not initialized")

    def _collection_path(self, object_type: str) -> Path:
        if object_type in _COLLECTIONS:
            return self.root / _COLLECTIONS[object_type]
        raise StorageError("unsupported append-only collection: %s" % object_type)

    def list_records(self, object_type: str) -> list[dict[str, Any]]:
        self._ensure_initialized()
        if object_type == "workspace":
            return [json.loads((self.root / "workspace.json").read_text(encoding="utf-8"))]
        if object_type == "discovery_run":
            records = []
            for path in sorted((self.root / "runs").glob("*/run.json")):
                records.append(json.loads(path.read_text(encoding="utf-8")))
            return records
        path = self._collection_path(object_type)
        if not path.exists():
            return []
        records = []
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise StorageError("%s line %d is invalid JSON" % (path, line_no)) from exc
        return records

    def get(self, object_type: str, record_id: str) -> dict[str, Any] | None:
        for record in self.list_records(object_type):
            if record.get("id") == record_id:
                return record
        return None

    def append(self, record: dict[str, Any]) -> None:
        self._ensure_initialized()
        data = validate_record(record)
        kind = data["object_type"]
        if kind == "workspace":
            raise StorageError("workspace identity is initialized once and cannot be appended")
        if data.get("workspace_id") not in (None, self.workspace_id):
            raise StorageError("record belongs to another workspace")
        if self.get(kind, data["id"]) is not None:
            raise StorageError("duplicate immutable record id: %s" % data["id"])
        if kind == "requirement":
            for existing in self.list_records("requirement"):
                if existing.get("key") == data.get("key") and existing.get("version") == data.get("version"):
                    raise StorageError("duplicate requirement key/version: %s v%s" % (data["key"], data["version"]))
        if kind == "discovery_run":
            target = self.root / "runs" / data["id"] / "run.json"
            if target.exists():
                raise StorageError("duplicate discovery run id: %s" % data["id"])
            _atomic_write(target, _json_bytes(data))
            return
        path = self._collection_path(kind)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("ab") as stream:
            stream.write(_json_bytes(data))
            stream.flush()
            os.fsync(stream.fileno())

    def find_requirement_history(self, key: str) -> list[dict[str, Any]]:
        rows = [r for r in self.list_records("requirement") if r.get("key") == key]
        return sorted(rows, key=lambda row: (row.get("version", 0), row.get("id", "")))

    def find_relationships(self, object_type: str, record_id: str) -> list[dict[str, Any]]:
        found = []
        for relation in self.list_records("relationship"):
            for endpoint in ("from", "to"):
                ref = relation.get(endpoint) or {}
                if ref.get("object_type") == object_type and ref.get("id") == record_id:
                    found.append(relation)
                    break
        return found

    def evidence_for_asset(self, asset_id: str) -> list[dict[str, Any]]:
        return [r for r in self.list_records("evidence") if r.get("asset_id") == asset_id]

    def save_snapshot(self, content: bytes | str) -> str:
        self._ensure_initialized()
        raw = content.encode("utf-8") if isinstance(content, str) else bytes(content)
        digest = hashlib.sha256(raw).hexdigest()
        path = self.root / "snapshots" / "sha256" / digest[:2] / digest
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise StorageError("snapshot hash collision or corrupted snapshot")
            return digest
        _atomic_write(path, raw)
        return digest

    def read_snapshot(self, digest: str) -> bytes:
        if not re.match(r"^[a-f0-9]{64}$", digest or ""):
            raise StorageError("invalid SHA-256 digest")
        path = self.root / "snapshots" / "sha256" / digest[:2] / digest
        try:
            content = path.read_bytes()
        except FileNotFoundError as exc:
            raise StorageError("snapshot not found: %s" % digest) from exc
        if hashlib.sha256(content).hexdigest() != digest:
            raise StorageError("snapshot integrity check failed: %s" % digest)
        return content
