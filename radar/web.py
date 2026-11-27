"""Minimal web extraction + license hints (v0.3), standard library only."""
from __future__ import annotations

import ipaddress
import re
import socket
import subprocess
import tempfile
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

UA = "radar-mvp/1.7.0"
MAX_FETCH_BYTES = 5242880
_BLOCKED_HOST_SUFFIXES = (".localhost", ".local", ".internal", ".arpa", ".localdomain")


def _is_disallowed_ip(ip_obj):
    if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped is not None:
        return _is_disallowed_ip(ip_obj.ipv4_mapped)
    return (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
        or not ip_obj.is_global
    )


def resolve_public_url(url):
    """Validate URL and resolve DNS once, returning (approved_ip, host, port, err).

    approved_ip is None when host is already a literal public IP; otherwise it is the
    first validated public IP to pin via curl --resolve so curl never re-resolves DNS.
    """
    raw = str(url or "").strip()
    parts = urlsplit(raw)
    if parts.scheme.lower() not in ("http", "https"):
        return None, None, None, "非 http(s) URL"
    if parts.username is not None or parts.password is not None:
        return None, None, None, "拒绝包含 userinfo 的 URL"
    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        return None, None, None, "URL 缺少主机名"
    if host == "localhost" or any(host.endswith(suf) for suf in _BLOCKED_HOST_SUFFIXES):
        return None, None, None, "拒绝本地或内网主机名: %s" % host
    try:
        port = parts.port or (443 if parts.scheme.lower() == "https" else 80)
    except ValueError:
        return None, None, None, "URL 端口非法"
    try:
        ip_literal = ipaddress.ip_address(host)
    except ValueError:
        ip_literal = None
    if ip_literal is not None:
        if _is_disallowed_ip(ip_literal):
            return None, None, None, "拒绝私网/回环/保留 IP 地址: %s" % host
        return None, host, port, None
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        return None, None, None, "主机名解析失败: %s (%s)" % (host, exc)
    if not infos:
        return None, None, None, "主机名无可用解析记录: %s" % host
    approved_ip = None
    for info in infos:
        sockaddr = info[4]
        addr = sockaddr[0].split("%", 1)[0]
        try:
            resolved_ip = ipaddress.ip_address(addr)
        except ValueError:
            return None, None, None, "解析结果含非法 IP: %s" % addr
        if _is_disallowed_ip(resolved_ip):
            return None, None, None, "拒绝解析到私网/回环/保留地址的域名: %s -> %s" % (host, addr)
        if approved_ip is None:
            approved_ip = ("[%s]" % addr) if isinstance(resolved_ip, ipaddress.IPv6Address) else addr
    return approved_ip, host, port, None


def validate_public_url(url):
    """Ensure URL is public http(s) without userinfo or private/loopback/link-local targets."""
    _, _, _, err = resolve_public_url(url)
    return err


def _extract_location(header_text):
    location = None
    for line in (header_text or "").splitlines():
        if line.lower().startswith("location:"):
            location = line.split(":", 1)[1].strip()
    return location


def safe_curl_fetch(url, headers=None, timeout=20, max_bytes=MAX_FETCH_BYTES, max_redirects=5, ua=UA):
    """Fetch public http(s) text via curl without -L, pinning approved IP per hop via --resolve."""
    current = str(url or "").strip()
    for _ in range(max_redirects + 1):
        approved_ip, host, port, err = resolve_public_url(current)
        if err:
            return None, 0, err
        with tempfile.TemporaryDirectory() as tmp:
            hdr = Path(tmp) / "headers.txt"
            body = Path(tmp) / "body.bin"
            cmd = [
                "curl", "-sS", "--max-time", str(timeout),
                "-H", "User-Agent: %s" % ua,
                "--max-filesize", str(max_bytes),
                "-D", str(hdr), "-o", str(body), "-w", "%{http_code}",
            ]
            if approved_ip and host and port:
                cmd += ["--resolve", "%s:%d:%s" % (host, port, approved_ip)]
            for h in headers or []:
                cmd += ["-H", h]
            cmd.append(current)
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=timeout + 5,
                )
            except Exception as exc:
                return None, 0, "curl 异常: %s" % exc
            try:
                status = int((proc.stdout or "0").strip())
            except ValueError:
                status = 0
            if proc.returncode != 0:
                return None, status, (proc.stderr or "curl exit %s" % proc.returncode).strip()[:240]
            if status in (301, 302, 303, 307, 308):
                hdr_text = hdr.read_text(encoding="utf-8", errors="replace") if hdr.exists() else ""
                loc = _extract_location(hdr_text)
                if not loc:
                    return None, status, "HTTP %s 缺少 Location 头" % status
                current = urljoin(current, loc)
                continue
            if status != 200:
                return None, status, "HTTP %s" % status
            if body.exists() and body.stat().st_size > max_bytes:
                return None, status, "响应体超过上限 (%d bytes)" % max_bytes
            text = body.read_text(encoding="utf-8", errors="replace") if body.exists() else ""
            return text, status, None
    return None, 0, "重定向次数超过上限 (%d)" % max_redirects


class _Extractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title, self.desc, self.parts = [], "", []
        self.in_title = False
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self.in_title = True
        elif tag == "meta":
            name = (attrs.get("name") or attrs.get("property") or "").lower()
            if name in {"description", "og:description"} and not self.desc:
                self.desc = attrs.get("content") or ""
        elif tag in {"script", "style", "noscript", "svg"}:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag in {"script", "style", "noscript", "svg"} and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if self.skip:
            return
        (self.title if self.in_title else self.parts).append(data.strip())


def _sentences(text):
    """Chinese punctuation splits without spaces; English still needs a space."""
    out = []
    for chunk in re.split(r"(?<=[。！？])", text or ""):
        for part in re.split(r"(?<=[.!?])\s+", chunk):
            part = part.strip()
            if len(part) < 12:
                continue
            if len(part) > 240:
                part = part[:240].rstrip() + "…"
            out.append(part)
    return out


def extract_html(html, max_chars=20000):
    parser = _Extractor()
    try:
        parser.feed(html or "")
    except Exception:
        pass
    full_text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
    truncated = len(full_text) > max_chars
    text = full_text[:max_chars]
    quotes = []
    if parser.desc and len(parser.desc) >= 20:
        quotes.append(parser.desc[:240])
    quotes.extend(_sentences(text)[:2])
    return {"title": re.sub(r"\s+", " ", " ".join(parser.title)).strip(),
            "description": parser.desc.strip(), "text": text,
            "truncated": truncated,
            "quotes": list(dict.fromkeys(quotes))[:3]}


def detect_license(text, url=""):
    """Return (license, status, evidence).

    Standard MIT/BSD texts that include a copyright 'All rights reserved' line stay clear;
    standalone proprietary notices return proprietary; conflicting permissive + proprietary
    declarations on the same page are downgraded to needs_review.
    """
    t = (text or "").lower()
    path = (urlsplit(url).path or "").lower()
    is_license_file = path.endswith(("/license", "/license.txt", "/license.md", "/licence", "/copying"))
    has_arr = "all rights reserved" in t
    has_hard_proprietary = ("版权所有" in t or "proprietary notice" in t)

    permissive_strong = [
        (r"permission is hereby granted, free of charge, to any person obtaining a copy", "MIT"),
        (r"licensed under the apache license,? version 2\.0", "Apache-2.0"),
        (r"this source code form is subject to the terms of the mozilla public license", "MPL-2.0"),
        (r"this is free and unencumbered software released into the public domain", "Unlicense"),
        (r"cc0 1\.0 universal", "CC0-1.0"),
    ]
    for pattern, lic in permissive_strong:
        m = re.search(pattern, t, re.S)
        if m:
            if has_hard_proprietary:
                return lic, "needs_review", "conflicting license & proprietary notice: %s" % m.group(0)[:50]
            if has_arr and not is_license_file and len(t) > 2500:
                return lic, "needs_review", "conflicting all rights reserved on non-license page: %s" % m.group(0)[:50]
            return lic, "clear", m.group(0)[:80]

    copyleft_strong = [
        (r"gnu affero general public license", "AGPL-3.0"),
        (r"gnu lesser general public license", "LGPL-3.0"),
    ]
    for pattern, lic in copyleft_strong:
        m = re.search(pattern, t, re.S)
        if m:
            return lic, "needs_review", "copyleft: %s" % m.group(0)[:60]

    m = re.search(r"gnu general public license", t, re.S)
    if m:
        if re.search(r"version 3|v3", t):
            return "GPL-3.0", "needs_review", "copyleft: %s" % m.group(0)
        if re.search(r"version 2|v2", t):
            return "GPL-2.0", "needs_review", "copyleft: %s" % m.group(0)
        return "GPL", "needs_review", "GNU GPL without version"

    m = re.search(r"redistribution and use in source and binary forms", t, re.S)
    if m:
        bsd_lic = "BSD-3-Clause" if "neither the name" in t else ("BSD-2-Clause" if ("2." in t and "3." not in t) else "BSD")
        if bsd_lic == "BSD":
            return "BSD", "needs_review", "BSD without clause count"
        if has_hard_proprietary or (has_arr and not is_license_file and len(t) > 2500):
            return bsd_lic, "needs_review", "conflicting BSD & proprietary notice"
        return bsd_lic, "clear", m.group(0)

    if has_arr or has_hard_proprietary:
        return "proprietary", "proprietary", "all rights reserved / 版权所有"

    weak = [
        (r"\bmit license\b", "MIT", True),
        (r"\bapache license\b|apache-2\.0|apache", "Apache-2.0", True),
        (r"\bgnu general public license\b", "GPL", False),
        (r"\bmozilla public license\b", "MPL-2.0", True),
        (r"\bbsd license\b", "BSD", True),
    ]
    for pattern, lic, permissive in weak:
        m = re.search(pattern, t, re.S)
        if m:
            status = ("clear" if (permissive and path.endswith(("/license", "/license.txt", "/licence")))
                      else "needs_review")
            return lic, status, "weak mention: %s" % m.group(0)[:60]
    return "unknown", "needs_review", ""


def _strip_markdown(text):
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text or "")
    return re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)


def _norm(text):
    return re.sub(r"[\W_]+", "", _strip_markdown(text).lower())


def verify_quotes(quotes, text, truncated=False):
    """Return true/false/unknown by normalized substring match."""
    quotes = [q for q in (quotes or []) if q and q.strip()]
    if not quotes:
        return "unknown"
    page = _norm(text)
    if all(_norm(q) in page for q in quotes):
        return "true"
    if truncated:
        return "unknown"
    if len(page) >= 300:
        return "false"
    return "unknown"


def _now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def apply_web(source, page, status=200):
    out = dict(source)
    if page.get("title") and (not out.get("title") or out["title"] == out.get("url")):
        out["title"] = page["title"]
    old = [q for q in (out.get("quotes") or []) if q and str(q).strip()]
    extracted = page.get("quotes", [])
    out["quotes"] = list(dict.fromkeys(old + extracted))[:5]
    page_text = " ".join([page.get("title", ""), page.get("description", ""),
                          page.get("text", "")])
    if old:
        out["quote_verified"] = verify_quotes(
            old, page_text, truncated=bool(page.get("truncated", False)))
        out["quote_verified_by"] = "web"
        out["quote_verified_this_run"] = True
    else:
        # Extracted candidate quotes must not self-certify as verified evidence.
        out["quote_verified"] = "unknown"
        out["quote_verified_by"] = None
        out["quote_verified_this_run"] = False
        if extracted:
            out["quote_source"] = "web_extract"
    out["web_text_chars"] = len(page.get("text", ""))
    out["web_extracted"] = True
    out["last_seen"] = _now()
    out["http_status"] = status
    if status == 200:
        out["access_status"] = "public"
    lic, lic_status, evidence = detect_license(
        " ".join([page.get("title", ""), page.get("description", ""), page.get("text", "")]),
        out.get("url", ""))
    if lic_status == "clear" and out.get("license_status") in (None, "", "unknown", "needs_review"):
        out["license"], out["license_status"] = lic, "clear"
        out["license_evidence"] = evidence
    elif lic_status == "proprietary" and out.get("license_status") in (None, "", "unknown", "needs_review"):
        out["license"], out["license_status"] = "proprietary", "proprietary"
        out["license_evidence"] = evidence
    elif lic != "unknown" and out.get("license") in (None, "", "unknown"):
        out["license"] = lic
        out["license_evidence"] = evidence
    return out


def fetch_text(url, timeout=20):
    """Returns (text, status, error). Non-2xx and private/redirect SSRF targets are rejected."""
    return safe_curl_fetch(url, timeout=timeout, max_bytes=MAX_FETCH_BYTES, ua=UA)


def robots_allowed(url, timeout=10):
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return True
    robots_url = "%s://%s/robots.txt" % (parts.scheme, parts.netloc)
    text, status, err = fetch_text(robots_url, timeout=timeout)
    if err or not text:
        return True  # robots unreachable: do not block, but caller can warn
    parser = RobotFileParser()
    parser.parse(text.splitlines())
    return parser.can_fetch(UA, url)


def enrich_web(sources, limit=5, timeout=20, respect_robots=False):
    out, warnings = [], []
    count = 0
    for src in sources:
        if limit and count >= limit:
            out.append(src)
            continue
        if src.get("status") == "rejected" or src.get("platform") not in {"web", "docs"}:
            out.append(src)
            continue
        if respect_robots and not robots_allowed(src.get("url", ""), timeout=timeout):
            item = dict(src)
            item["web_error"] = "robots.txt disallowed"
            warnings.append("%s: robots.txt disallowed" % src.get("id"))
            out.append(item)
            count += 1
            continue
        text, status, err = fetch_text(src.get("url", ""), timeout=timeout)
        if err:
            item = dict(src)
            item["web_error"] = err[:240]
            item["http_status"] = status
            item["access_status"] = {401: "login_required", 403: "blocked",
                                     404: "deleted"}.get(status, "unreachable")
            warnings.append("%s: %s" % (src.get("id"), err[:160]))
            out.append(item)
            count += 1
            continue
        out.append(apply_web(src, extract_html(text), status=status))
        count += 1
    return out, warnings
