"""Claim ledger + rule-based confidence (v0.4)."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from urllib.parse import urlsplit

from .model import LEVELS, RadarError, level_for_source, load_json, normalized_host, valid_quotes, write_json

LEVEL_BASE = {"strong": 0.80, "evidence": 0.60, "mention": 0.30, "none": 0.0}


def _sources_for(claim, by_id):
    return [by_id[sid] for sid in claim.get("sources", []) if sid in by_id]


def _distinct_hosts(sources):
    hosts = set()
    for src in sources:
        hosts.add(normalized_host(src.get("url", "")))
    hosts.discard("")
    return len(hosts)


def compute_confidence(claim, by_id):
    all_sources = _sources_for(claim, by_id)
    sources = [s for s in all_sources if s.get("status") != "rejected"]
    if not sources:
        return {"confidence": 0.0, "label": "low", "status": "unresolved",
                "reasons": ["no_sources"], "source_count": 0, "distinct_hosts": 0,
                "best_level": "none"}
    levels = [level_for_source(s) for s in sources]
    best = max(levels, key=lambda x: {"none": 0, "mention": 1, "evidence": 2, "strong": 3}[x])
    base = LEVEL_BASE.get(best, 0.0)
    cap, reasons = 1.0, []
    # Only non-rejected sources with at least evidence-level backing count toward independent corroboration.
    corroborating = [s for s in sources if LEVELS[level_for_source(s)] >= LEVELS["evidence"]]
    hosts = _distinct_hosts(corroborating)
    if len(corroborating) < 2 or hosts < 2:
        cap = min(cap, 0.55)
        reasons.append("single_source")
    supported = set()
    for src in sources:
        supported |= set(src.get("covers") or [])
    if not (set(claim.get("covers") or []) & supported):
        cap = min(cap, 0.30)
        reasons.append("unsupported_by_sources")
    verified = [s for s in sources
                if valid_quotes(s.get("quotes"))
                and s.get("quote_verified") == "true"
                and s.get("quote_verified_by") == "web"]
    verified_covers = set()
    for src in verified:
        verified_covers |= set(src.get("covers") or [])
    if not verified:
        cap = min(cap, 0.40)
        reasons.append("no_verified_source")
    elif not (set(claim.get("covers") or []) & verified_covers):
        cap = min(cap, 0.30)
        reasons.append("unsupported_by_verified_sources")
    if not any(valid_quotes(s.get("quotes")) for s in sources):
        cap = min(cap, 0.40)
        reasons.append("no_quote")
    if any(s.get("license_status") == "proprietary" for s in sources):
        cap = min(cap, 0.40)
        reasons.append("proprietary_reference")
    if claim.get("contradicts"):
        cap = min(cap, 0.40)
        reasons.append("contradiction")
    conf = round(min(base, cap), 2)
    label = "high" if conf >= 0.75 else ("medium" if conf >= 0.50 else "low")
    status = "contested" if claim.get("contradicts") else ("open" if reasons else "accepted")
    return {"confidence": conf, "label": label, "status": status,
            "reasons": reasons, "source_count": len(sources),
            "verified_count": len(verified), "distinct_hosts": hosts,
            "best_level": best}


def validate_claims(data, pack, by_id):
    if not isinstance(data, dict):
        raise RadarError("claims 顶层必须是对象")
    if data.get("schema_version") != 1:
        raise RadarError("claims.schema_version 必须是 1")
    if data.get("pack") not in (None, pack["pack"]):
        raise RadarError("claims.pack 与 pack 不一致")
    items = data.get("claims")
    if not isinstance(items, list) or not items:
        raise RadarError("claims.claims 至少 1 条")
    valid_ids = {m["id"] for m in pack["modules"]} | {s["id"] for s in pack["subsystems"]}
    seen = set()
    out = []
    for i, claim in enumerate(items):
        where = "claims[%d]" % i
        if not isinstance(claim, dict):
            raise RadarError("%s 必须是对象" % where)
        for key in ("id", "statement", "covers", "sources"):
            if key not in claim:
                raise RadarError("%s 缺少 %s" % (where, key))
        if not str(claim["id"]).strip():
            raise RadarError("%s.id 不能为空" % where)
        if claim["id"] in seen:
            raise RadarError("claim id 重复: %s" % claim["id"])
        seen.add(claim["id"])
        if not str(claim["statement"]).strip():
            raise RadarError("%s.statement 不能为空" % where)
        if not isinstance(claim["covers"], list) or not claim["covers"]:
            raise RadarError("%s.covers 至少 1 条" % where)
        for cid in claim["covers"]:
            if cid not in valid_ids:
                raise RadarError("%s.covers 含不存在的 id: %s" % (where, cid))
        if not isinstance(claim["sources"], list) or not claim["sources"]:
            raise RadarError("%s.sources 至少 1 条" % where)
        for sid in claim["sources"]:
            if sid not in by_id:
                raise RadarError("%s.sources 含不存在的来源: %s" % (where, sid))
        contradicts = claim.get("contradicts") or []
        if not isinstance(contradicts, list):
            raise RadarError("%s.contradicts 必须是数组" % where)
        item = dict(claim)
        item["contradicts"] = contradicts
        out.append(item)
    for claim in out:
        for other in claim["contradicts"]:
            if other not in seen:
                raise RadarError("%s.contradicts 含不存在的 claim: %s" % (claim["id"], other))
            if other == claim["id"]:
                raise RadarError("%s.contradicts 不能指向自己" % claim["id"])
    return out


def evaluate_claims(data, pack, sources):
    by_id = {s["id"]: s for s in sources}
    claims = validate_claims(data, pack, by_id)
    contradicted_by = {c["id"]: set() for c in claims}
    for claim in claims:
        for other in claim["contradicts"]:
            contradicted_by[other].add(claim["id"])
    results = []
    for claim in claims:
        effective = dict(claim)
        effective["contradicts"] = sorted(set(claim["contradicts"]) | contradicted_by[claim["id"]])
        row = dict(claim)
        row["contradicts"] = effective["contradicts"]
        row["declared_contradicts"] = list(claim["contradicts"])
        row.update(compute_confidence(effective, by_id))
        results.append(row)
    return results


def _next_action(row):
    if "no_sources" in row["reasons"]:
        return "补来源"
    if "no_verified_source" in row["reasons"]:
        return "先跑 --verify-quotes"
    if "unsupported_by_verified_sources" in row["reasons"]:
        return "换已验证来源或改主张"
    if "unsupported_by_sources" in row["reasons"]:
        return "换来源或改主张"
    if "contradiction" in row["reasons"]:
        return "复核矛盾"
    if "single_source" in row["reasons"]:
        return "找第二个独立来源"
    if "no_quote" in row["reasons"]:
        return "补 quote"
    if "proprietary_reference" in row["reasons"]:
        return "换可复用来源或人工复核许可"
    return "可进入需求底稿"


def write_claims(out_dir, results, meta):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "claims.json", {"meta": meta, "claims": results})
    lines = ["# Claim 账本", "",
             "Run: `%s` · Pack: `%s` · Claims: %d" % (
                 meta.get("run", ""), meta.get("pack", ""), len(results)),
             "", "| ID | 主张 | 置信度 | 状态 | 来源 | 原因 |", "| --- | --- | ---: | --- | --- | --- |"]
    for r in results:
        lines.append("| `%s` | %s | %.2f | %s | %s | %s |" % (
            r["id"], str(r["statement"]).replace("|", "\\|"), r["confidence"],
            r["status"], ", ".join(r["sources"]), ", ".join(r["reasons"]) or "—"))
    lines.append("")
    (out / "claims.md").write_text("\n".join(lines), encoding="utf-8")
    def safe(value):
        text = str(value)
        return "'" + text if text.startswith(("=", "+", "-", "@")) else text

    with (out / "review.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "statement", "confidence", "label", "status", "sources", "reasons", "next_action"])
        for r in results:
            w.writerow([safe(r["id"]), safe(r["statement"]), r["confidence"], r["label"],
                        r["status"], safe(";".join(r["sources"])),
                        safe(";".join(r["reasons"])), safe(_next_action(r))])
    write_json(out / "state.json", meta)
