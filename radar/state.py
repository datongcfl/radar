"""Source-level change detection for scan --since.

v0.2.2 is ledger-level: compare two runs' source records. Network refresh
(`--fetch`) is intentionally not part of this version.
"""
from __future__ import annotations

import json
from pathlib import Path

from .model import canonical_url

COMPARE_FIELDS = [
    "status", "evidence_level", "covers", "quotes",
    "quote_verified", "quote_verified_by", "quote_verified_this_run",
    "license", "license_status",
    "access_status", "version", "content_hash", "etag",
]


def _key(src):
    return canonical_url(src.get("url", "")) or src.get("id", "")


def _norm(value):
    if isinstance(value, list):
        return sorted(str(v) for v in value)
    return value


def read_sources(run_dir):
    path = Path(run_dir) / "sources.jsonl"
    if not path.exists():
        raise FileNotFoundError("缺少 %s" % path)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _brief(src):
    return {"id": src.get("id"), "url": src.get("url"), "title": src.get("title")}


def compare_sources(old_sources, new_sources):
    old = {_key(s): s for s in old_sources}
    new = {_key(s): s for s in new_sources}
    added = [_brief(new[k]) for k in sorted(set(new) - set(old))]
    removed = [_brief(old[k]) for k in sorted(set(old) - set(new))]
    changed, unchanged = [], 0
    for key in sorted(set(old) & set(new)):
        a, b = old[key], new[key]
        fields = {}
        for field in COMPARE_FIELDS:
            if _norm(a.get(field)) != _norm(b.get(field)):
                fields[field] = {"old": a.get(field), "new": b.get(field)}
        if fields:
            changed.append({"id": b.get("id"), "url": b.get("url"),
                            "title": b.get("title"), "fields": fields})
        else:
            unchanged += 1
    return {"added": added, "removed": removed, "changed": changed,
            "unchanged": unchanged, "old_count": len(old), "new_count": len(new)}


def render_changes(result):
    lines = ["# 来源变更（scan --since）", "",
             "旧来源：%d · 新来源：%d · 未变：%d" % (
                 result["old_count"], result["new_count"], result["unchanged"]),
             "", "## 新增", ""]
    lines.extend(["- `%s` %s" % (x["id"], x["url"]) for x in result["added"]] or ["- 无"])
    lines.extend(["", "## 移除", ""])
    lines.extend(["- `%s` %s" % (x["id"], x["url"]) for x in result["removed"]] or ["- 无"])
    lines.extend(["", "## 变化", ""])
    if result["changed"]:
        for x in result["changed"]:
            fields = ", ".join(sorted(x["fields"]))
            lines.append("- `%s` %s：%s" % (x["id"], x["url"], fields))
    else:
        lines.append("- 无")
    lines.append("")
    return "\n".join(lines)


def write_changes(out_dir, result):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "changes.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "changes.md").write_text(render_changes(result), encoding="utf-8")
