"""Verify quotes against source content (v1.1), no third-party deps."""
from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from .model import canonical_url
from .web import extract_html, fetch_text, verify_quotes

UA = "radar-mvp/1.1.0"


def _now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _repo(url):
    parts = urlsplit(url)
    path = [p for p in parts.path.split("/") if p]
    if len(path) < 2:
        return None
    return path[0], path[1].replace(".git", "")


def _github_file(url):
    parts = urlsplit(url)
    path = [p for p in parts.path.split("/") if p]
    if len(path) >= 5 and path[2] == "blob":
        return path[0], path[1], path[3], "/".join(path[4:])
    return None


def _curl_text(url, headers=None, timeout=20):
    with tempfile.TemporaryDirectory() as tmp:
        body = Path(tmp) / "body.bin"
        cmd = ["curl", "-sS", "-L", "--max-time", str(timeout),
               "-H", "User-Agent: %s" % UA, "-o", str(body), "-w", "%{http_code}"]
        for h in headers or []:
            cmd += ["-H", h]
        cmd.append(url)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=timeout + 5)
        except Exception as exc:
            return None, 0, "curl 异常: %s" % exc
        try:
            status = int((proc.stdout or "0").strip())
        except ValueError:
            status = 0
        text = body.read_text(encoding="utf-8", errors="replace") if body.exists() else ""
        if proc.returncode != 0:
            return None, status, (proc.stderr or "curl exit %s" % proc.returncode).strip()[:200]
        if status != 200:
            return None, status, "HTTP %s" % status
        return text, status, None


def source_text(src, timeout=20):
    """Best-effort text for a source. Returns (text, status, error)."""
    url = src.get("url", "")
    platform = src.get("platform")
    if platform == "github":
        repo = _repo(url)
        if not repo:
            return None, 0, "无法解析 GitHub repo"
        headers = ["Accept: application/vnd.github.raw"]
        import os
        if os.environ.get("GITHUB_TOKEN"):
            headers.append("Authorization: Bearer %s" % os.environ["GITHUB_TOKEN"])
        file_ref = _github_file(url)
        if file_ref:
            owner, repo_name, branch, path = file_ref
            return _curl_text(
                "https://api.github.com/repos/%s/%s/contents/%s?ref=%s" % (
                    owner, repo_name, path, branch),
                headers=headers, timeout=timeout)
        readme, status, err = _curl_text(
            "https://api.github.com/repos/%s/%s/readme" % repo,
            headers=headers, timeout=timeout)
        meta, _, _ = _curl_text(
            "https://api.github.com/repos/%s/%s" % repo,
            headers=["Accept: application/vnd.github+json"] + ([headers[-1]] if len(headers) > 1 else []),
            timeout=timeout)
        desc = ""
        try:
            desc = json.loads(meta or "{}").get("description") or ""
        except Exception:
            desc = ""
        text = "\n".join(x for x in (readme or "", desc) if x)
        if text:
            return text, status or 200, None
        return None, status, err or "GitHub README/description 为空"
    if platform == "gitee":
        repo = _repo(url)
        if not repo:
            return None, 0, "无法解析 Gitee repo"
        last = None
        for branch in ("main", "master"):
            text, status, err = _curl_text(
                "https://gitee.com/%s/%s/raw/%s/README.md" % (repo[0], repo[1], branch),
                timeout=timeout)
            if not err:
                return text, status, None
            last = (text, status, err)
        return last
    text, status, err = fetch_text(url, timeout=timeout)
    if err:
        return None, status, err
    return extract_html(text, max_chars=200000)["text"], status, None


def verify_source(src, timeout=20):
    out = dict(src)
    text, status, err = source_text(src, timeout=timeout)
    out["quote_verified_by"] = "web"
    out["quote_verified_at"] = _now()
    out["quote_verified_this_run"] = True
    if err:
        out["quote_verified"] = "unknown"
        out["quote_verify_error"] = err[:200]
        return out
    out["quote_verified"] = verify_quotes(
        src.get("quotes") or [], text, truncated=(len(text or "") >= 200000))
    out["quote_verify_chars"] = len(text or "")
    return out


def verify_sources(sources, limit=0, timeout=20):
    out, warnings = [], []
    count = 0
    for src in sources:
        if limit and count >= limit:
            out.append(src)
            continue
        if src.get("status") == "rejected" or not (src.get("quotes") or []):
            out.append(src)
            continue
        item = verify_source(src, timeout=timeout)
        if item.get("quote_verify_error"):
            warnings.append("%s: %s" % (src.get("id"), item["quote_verify_error"]))
        out.append(item)
        count += 1
    return out, warnings
