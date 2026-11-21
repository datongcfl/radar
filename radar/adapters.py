"""Optional GitHub adapter. Seeds work offline; this is opt-in."""
from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.parse

CLEAR_LICENSES = {"MIT", "Apache-2.0", "BSD-3-Clause", "BSD-2-Clause", "0BSD",
                  "ISC", "MPL-2.0", "GPL-2.0", "GPL-3.0", "LGPL-3.0",
                  "PostgreSQL", "Unlicense", "CC0-1.0"}


def _curl_json(url, token=None, accept="application/json", timeout=25):
    cmd = ["curl", "-sS", "--max-time", str(timeout), "-H", "User-Agent: radar-mvp",
           "-H", "Accept: %s" % accept]
    if token:
        cmd += ["-H", "Authorization: Bearer %s" % token]
    cmd.append(url)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout + 5)
    except Exception as exc:
        return None, "curl 异常: %s" % exc
    if proc.returncode != 0:
        return None, proc.stderr.strip()[:300]
    try:
        return json.loads(proc.stdout), None
    except Exception as exc:
        return None, "JSON 解析失败: %s" % exc


def _keyword_hit(text, keyword):
    kw = str(keyword or "").strip().lower()
    if not kw:
        return False
    # Short ASCII tokens (ai/dc/ups/bim/kv) need word boundaries; Chinese and
    # longer phrases keep substring matching.
    if len(kw) <= 4 and re.fullmatch(r"[a-z0-9]+", kw):
        return re.search(r"(?<![a-z0-9])%s(?![a-z0-9])" % re.escape(kw), text) is not None
    return kw in text


def infer_covers(text, pack, limit=6):
    text = (text or "").lower()
    hits = []
    for item in pack["modules"] + pack["subsystems"]:
        names = [item["name"]] + list(item.get("keywords", []))
        if any(_keyword_hit(text, n) for n in names if str(n).strip()):
            hits.append(item["id"])
    return hits[:limit]


def github_search(query, pack, limit=3, token=None, id_offset=0):
    url = ("https://api.github.com/search/repositories?q="
           + urllib.parse.quote(query)
           + "&sort=updated&order=desc&per_page=%d" % max(1, min(limit, 10)))
    data, err = _curl_json(url, token)
    if err:
        return [], "GitHub 查询失败: %s" % err
    if not isinstance(data, dict) or "items" not in data:
        return [], "GitHub 返回异常: %s" % str(data)[:200]
    out = []
    for i, item in enumerate(data.get("items", [])):
        desc = item.get("description") or ""
        text = " ".join([item.get("full_name", ""), desc] + list(item.get("topics") or []))
        covers = infer_covers(text, pack)
        if not covers:
            continue
        lic = (item.get("license") or {}).get("spdx_id") or "unknown"
        out.append({
            "id": "GH-%03d" % (id_offset + i + 1),
            "platform": "github",
            "url": item.get("html_url", ""),
            "title": item.get("full_name", ""),
            "artifact_type": "code",
            "language": "unknown",
            "retrieved_at": item.get("updated_at"),
            "http_status": 200,
            "access_status": "public",
            "license": lic,
            "license_status": "clear" if lic in CLEAR_LICENSES else "needs_review",
            "evidence_level": "metadata",
            "derived_from_real_data": False,
            "stars": item.get("stargazers_count"),
            "covers": covers,
            "borrow_scope": ["workflow"],
            "quotes": [],
            "limitations": "仅 GitHub metadata，未读正文/代码",
            "status": "needs_review",
            "why_selected": "GitHub search: %s" % query,
        })
    return out, None


def collect_github(pack, limit_per_query=3, max_queries=3, token=None):
    sources, warnings = [], []
    queries = (pack.get("source_map") or {}).get("github", [])[:max_queries]
    offset = 0
    for q in queries:
        got, warn = github_search(q, pack, limit=limit_per_query, token=token,
                                  id_offset=offset)
        sources.extend(got)
        offset += len(got)
        if warn:
            warnings.append(warn)
    return sources, warnings


def parse_gitee_items(items, pack, query, id_offset=0):
    out = []
    for i, item in enumerate(items or []):
        text = " ".join([item.get("full_name", ""), item.get("description") or ""])
        covers = infer_covers(text, pack)
        if not covers:
            continue
        lic = item.get("license") if isinstance(item.get("license"), str) else "unknown"
        out.append({
            "id": "GT-%03d" % (id_offset + i + 1),
            "platform": "gitee",
            "url": item.get("html_url", ""),
            "title": item.get("full_name", ""),
            "artifact_type": "code",
            "language": item.get("language") or "unknown",
            "retrieved_at": item.get("updated_at"),
            "http_status": 200,
            "access_status": "public",
            "license": lic,
            "license_status": "clear" if lic in CLEAR_LICENSES else "needs_review",
            "evidence_level": "metadata",
            "derived_from_real_data": False,
            "stars": item.get("stargazers_count"),
            "covers": covers,
            "borrow_scope": ["workflow"],
            "quotes": [],
            "limitations": "仅 Gitee metadata，未读正文/代码",
            "status": "needs_review",
            "why_selected": "Gitee search: %s" % query,
        })
    return out


def gitee_search(query, pack, limit=3, token=None, id_offset=0):
    if not token:
        return [], "Gitee 需要 GITEE_TOKEN；已跳过（不静默返回空）"
    url = ("https://gitee.com/api/v5/search/repositories?q="
           + urllib.parse.quote(query)
           + "&per_page=%d" % max(1, min(limit, 10)))
    data, err = _curl_json(url, token)
    if err:
        return [], "Gitee 查询失败: %s" % err
    if isinstance(data, dict):
        msg = data.get("message") or str(data)[:200]
        return [], "Gitee 返回异常: %s" % msg
    if not isinstance(data, list):
        return [], "Gitee 返回异常: %s" % str(data)[:200]
    return parse_gitee_items(data, pack, query, id_offset=id_offset), None


def collect_gitee(pack, limit_per_query=3, max_queries=3, token=None):
    sources, warnings = [], []
    queries = (pack.get("source_map") or {}).get("gitee", [])[:max_queries]
    offset = 0
    for q in queries:
        got, warn = gitee_search(q, pack, limit=limit_per_query, token=token,
                                 id_offset=offset)
        sources.extend(got)
        offset += len(got)
        if warn:
            warnings.append(warn)
    return sources, warnings
