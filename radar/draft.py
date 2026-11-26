"""Draft candidate seeds from URLs to reduce manual entry cost (Issue #2)."""
from __future__ import annotations

import os
import re
from datetime import datetime

from .adapters import CLEAR_LICENSES, _curl_json, infer_covers
from .model import (RadarError, _default_artifact, _default_title, _infer_platform,
                    canonical_url, load_json)
from .verify import _curl_text, _repo
from .web import _sentences, detect_license, extract_html, fetch_text


def _today():
    return datetime.now().astimezone().strftime("%Y-%m-%d")


def _candidate_quotes(text, max_quotes=3):
    """Pick clean verbatim body sentences (40-180 chars preferred)."""
    sents = _sentences(text)
    preferred = [s for s in sents if 40 <= len(s) <= 180 and not s.endswith("…")]
    pool = preferred or [s for s in sents if len(s) >= 20 and not s.endswith("…")]
    return list(dict.fromkeys(pool))[:max_quotes]


def _next_id_number(existing_sources, prefix="SRC-"):
    max_num = 0
    pat = re.compile(r"^%s(\d+)$" % re.escape(prefix))
    for src in existing_sources or []:
        m = pat.match(str(src.get("id", "")))
        if m:
            max_num = max(max_num, int(m.group(1)))
    return max_num + 1


def _fetch_github_draft(url, token=None, timeout=20):
    repo = _repo(url)
    if not repo:
        return None, "无法解析 GitHub 仓库路径"
    api = "https://api.github.com/repos/%s/%s" % repo
    meta, err = _curl_json(api, token=token, accept="application/vnd.github+json")
    if err or not isinstance(meta, dict) or "full_name" not in meta:
        return None, err or "GitHub API 未返回仓库元数据"
    headers = ["Accept: application/vnd.github.raw"]
    if token:
        headers.append("Authorization: Bearer %s" % token)
    readme, _, _ = _curl_text(api + "/readme", headers=headers, timeout=timeout)
    lic = (meta.get("license") or {}).get("spdx_id") or "unknown"
    if lic == "NOASSERTION":
        lic = "unknown"
    desc = meta.get("description") or ""
    body_text = "\n".join(x for x in (readme or "", desc) if x)
    return {
        "title": meta.get("full_name") or _default_title(url),
        "stars": meta.get("stargazers_count"),
        "license": lic,
        "license_status": "clear" if lic in CLEAR_LICENSES else "needs_review",
        "evidence_level": "readme" if readme else "metadata",
        "text": body_text,
        "quotes": _candidate_quotes(body_text),
    }, None


def _fetch_gitee_draft(url, gitee_token=None, timeout=20):
    repo = _repo(url)
    if not repo:
        return None, "无法解析 Gitee 仓库路径"
    meta, err = _curl_json("https://gitee.com/api/v5/repos/%s/%s" % repo, token=gitee_token)
    readme = None
    for branch in ("main", "master"):
        txt, _, r_err = _curl_text(
            "https://gitee.com/%s/%s/raw/%s/README.md" % (repo[0], repo[1], branch),
            timeout=timeout)
        if not r_err and txt:
            readme = txt
            break
    if (err or not isinstance(meta, dict) or "full_name" not in meta) and not readme:
        return None, err or "Gitee 仓库元数据与 README 均读取失败"
    meta = meta if isinstance(meta, dict) else {}
    lic = meta.get("license") if isinstance(meta.get("license"), str) and meta.get("license") else "unknown"
    desc = meta.get("description") or ""
    body_text = "\n".join(x for x in (readme or "", desc) if x)
    return {
        "title": meta.get("full_name") or _default_title(url),
        "stars": meta.get("stargazers_count"),
        "license": lic,
        "license_status": "clear" if lic in CLEAR_LICENSES else "needs_review",
        "evidence_level": "readme" if readme else "metadata",
        "text": body_text,
        "quotes": _candidate_quotes(body_text),
    }, None


def _fetch_web_draft(url, timeout=20):
    html, status, err = fetch_text(url, timeout=timeout)
    if err:
        return None, err
    page = extract_html(html, max_chars=200000)
    full_text = " ".join([page.get("title", ""), page.get("description", ""), page.get("text", "")])
    lic, lic_status, _ = detect_license(full_text, url=url)
    body_quotes = _candidate_quotes(page.get("text", ""))
    return {
        "title": page.get("title") or _default_title(url),
        "stars": None,
        "license": lic,
        "license_status": lic_status,
        "evidence_level": "docs" if len(page.get("text", "")) >= 300 else "metadata",
        "text": full_text,
        "quotes": body_quotes,
        "http_status": status,
    }, None


def draft_source(url, pack, source_id, covers=None, token=None, gitee_token=None, timeout=20):
    """Build a review-ready seed draft from a URL using stdlib/curl only."""
    platform = _infer_platform(url)
    info, err = None, None
    if platform == "github" and _repo(url):
        info, err = _fetch_github_draft(url, token=token, timeout=timeout)
    elif platform == "gitee" and _repo(url):
        info, err = _fetch_gitee_draft(url, gitee_token=gitee_token, timeout=timeout)
    else:
        info, err = _fetch_web_draft(url, timeout=timeout)

    if err or not info:
        return None, err or "抓取失败"

    chosen_covers = list(covers) if covers else infer_covers(
        "%s %s" % (info.get("title", ""), info.get("text", "")[:4000]), pack)
    out = {
        "id": source_id,
        "platform": platform,
        "url": url,
        "title": info["title"],
        "artifact_type": _default_artifact(platform),
        "language": "zh" if re.search(r"[\u4e00-\u9fff]", info.get("text", "")[:1000]) else "en",
        "retrieved_at": _today(),
        "http_status": info.get("http_status", 200),
        "access_status": "public",
        "license": info["license"],
        "license_status": info["license_status"],
        "evidence_level": info["evidence_level"],
        "derived_from_real_data": False,
        "covers": chosen_covers,
        "borrow_scope": ["workflow"],
        "quotes": info["quotes"],
        "quote_verified": "unknown",
        "limitations": "draft 自动生成：请人工确认 covers、quotes、license_status 与 evidence_level 后再改为 selected",
        "status": "needs_review",
        "why_selected": "radar draft 从 URL 自动补全元数据与正文候选引用",
    }
    if info.get("stars") is not None:
        out["stars"] = info["stars"]
    return out, None


def draft_seeds_from_urls(pack, urls, covers=None, existing_seeds_path=None,
                          token=None, gitee_token=None, timeout=20):
    """Draft a seeds payload for a list of URLs, deduplicating against existing seeds."""
    existing = []
    if existing_seeds_path:
        data = load_json(existing_seeds_path)
        existing = data.get("sources") or []
    seen_urls = {canonical_url(s.get("url", "")) for s in existing if s.get("url")}
    next_num = _next_id_number(existing)

    drafted, warnings, skipped = [], [], []
    for raw_url in urls:
        url = str(raw_url or "").strip()
        if not url:
            continue
        if not url.startswith(("http://", "https://")):
            warnings.append("%s: 跳过非 http(s) URL" % url)
            continue
        norm = canonical_url(url)
        if norm in seen_urls:
            skipped.append(url)
            continue
        sid = "SRC-%03d" % next_num
        src, err = draft_source(url, pack, sid, covers=covers, token=token,
                                gitee_token=gitee_token, timeout=timeout)
        if err:
            warnings.append("%s: %s" % (url, err))
            continue
        seen_urls.add(norm)
        next_num += 1
        drafted.append(src)

    payload = {
        "schema_version": 1,
        "pack": pack["pack"],
        "sources": drafted,
    }
    return payload, warnings, skipped
