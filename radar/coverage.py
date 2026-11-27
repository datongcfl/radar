"""Coverage matrix: module/subsystem x sources."""
from __future__ import annotations

from urllib.parse import urlsplit

from .model import LEVELS, level_for_source, normalized_host

# 存在性阶梯（existence ladder），不是质量排序：production 只证明“东西存在”，
# 不证明“工程质量更好”。质量判断另看测试/文档/维护/边界。
EV_RANK = {"marketing": 0, "metadata": 1, "readme": 2, "docs": 3,
           "real_artifact": 4, "code_tests": 5, "production": 6}


def _pick_strongest(sources):
    def key(s):
        return (LEVELS[level_for_source(s)], EV_RANK.get(s.get("evidence_level"), 0), s["id"])
    return sorted(sources, key=key, reverse=True)[0] if sources else None


def _host(src):
    return normalized_host(src.get("url", ""))


def _row(item, kind, sources):
    matched = [s for s in sources if item["id"] in s.get("covers", []) and s.get("status") != "rejected"]
    level = "none"
    if matched:
        level = max((level_for_source(s) for s in matched), key=lambda x: LEVELS[x])
    evidence = [s for s in matched if LEVELS[level_for_source(s)] >= LEVELS["evidence"]]
    independent = len({_host(s) for s in evidence if _host(s)})
    verified = [s for s in evidence if s.get("quote_verified") == "true"
                and s.get("quote_verified_by") == "web"]
    verified_hosts = len({_host(s) for s in verified if _host(s)})
    # Strong needs two independent hosts that were verified in this run/seed.
    if level == "strong" and (len(verified) < 2 or verified_hosts < 2):
        level = "evidence"
    strongest = _pick_strongest(matched)
    reusable = any(s.get("license_status") == "clear" for s in matched)
    return {
        "id": item["id"],
        "name": item["name"],
        "kind": kind,
        "level": level,
        "source_count": len(matched),
        "evidence_count": len(evidence),
        "independent_count": independent,
        "verified_count": len(verified),
        "verified_independent_count": verified_hosts,
        "sources": [s["id"] for s in matched],
        "strongest": strongest["id"] if strongest else None,
        "reusable": reusable,
        "single_source": len(evidence) == 1,
    }


def compute_coverage(pack, sources):
    modules = [_row(m, "module", sources) for m in pack["modules"]]
    subsystems = [_row(s, "subsystem", sources) for s in pack["subsystems"]]
    all_rows = modules + subsystems
    summary = {"none": 0, "mention": 0, "evidence": 0, "strong": 0}
    for row in all_rows:
        summary[row["level"]] += 1
    platforms = {}
    for s in sources:
        platforms[s["platform"]] = platforms.get(s["platform"], 0) + 1
    return {
        "modules": modules,
        "subsystems": subsystems,
        "summary": summary,
        "sources": len(sources),
        "platforms": platforms,
    }


def gap_rows(coverage, min_level="evidence"):
    need = LEVELS[min_level]
    return [r for r in coverage["modules"] + coverage["subsystems"]
            if LEVELS[r["level"]] < need]
