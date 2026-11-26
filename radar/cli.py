"""radar CLI: run / validate / diff."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from . import __version__
from .adapters import collect_github, collect_gitee
from .fetch import fetch_sources
from .snowball import snowball
from .web import enrich_web
from .verify import verify_sources
from .coverage import compute_coverage
from .claims import evaluate_claims, write_claims
from .diff import diff_runs
from .draft import draft_seeds_from_urls
from .model import (RadarError, enforce_web_verification, load_json, load_pack, load_seeds,
                    merge_sources, sha256_file, write_json)
from .report import write_run
from .state import compare_sources, read_sources, write_changes


def _now():
    return datetime.now().astimezone()


def _git_commit():
    try:
        proc = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              cwd=Path(__file__).resolve().parent.parent,
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=5)
        return proc.stdout.strip() if proc.returncode == 0 else None
    except Exception:
        return None


def _gitee_token():
    token = os.environ.get("GITEE_TOKEN")
    if token:
        return token.strip()
    path = Path.home() / ".config" / "radar" / "gitee_token"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return None


def cmd_run(args):
    if (args.github or args.gitee or args.snowball or args.fetch or args.web) and not shutil.which("curl"):
        raise RadarError("网络选项需要 curl；请先安装 curl，或去掉 --github/--gitee/--snowball/--fetch/--web")
    pack = load_pack(args.pack)
    seeds = load_seeds(args.seeds, pack, strict=args.strict)
    warnings = []
    sources = list(seeds)
    if args.github:
        got, warns = collect_github(pack, limit_per_query=args.limit,
                                    max_queries=args.max_queries,
                                    token=os.environ.get("GITHUB_TOKEN"))
        sources.extend(got)
        warnings.extend(warns)
    if args.gitee:
        got, warns = collect_gitee(pack, limit_per_query=args.limit,
                                   max_queries=args.max_queries,
                                   token=_gitee_token())
        sources.extend(got)
        warnings.extend(warns)
    if args.snowball:
        got, warns = snowball(sources, pack, token=os.environ.get("GITHUB_TOKEN"),
                               per_source=args.snowball_per_source,
                               max_sources=args.snowball_max)
        sources.extend(got)
        warnings.extend(warns)
    if args.fetch:
        sources, warns = fetch_sources(sources, limit=args.fetch_limit,
                                        timeout=args.fetch_timeout)
        warnings.extend(warns)
    if args.web:
        sources, warns = enrich_web(sources, limit=args.web_limit,
                                     timeout=args.web_timeout,
                                     respect_robots=args.respect_robots)
        warnings.extend(warns)
    sources = merge_sources(sources)
    if args.verify_quotes:
        sources, warns = verify_sources(sources, limit=args.verify_limit,
                                        timeout=args.verify_timeout)
        warnings.extend(warns)
    if args.require_web_verify:
        enforce_web_verification(sources)
    coverage = compute_coverage(pack, sources)
    run_id = _now().strftime("%Y%m%d-%H%M%S")
    out = Path(args.out)
    state = {
        "schema_version": 1,
        "run_id": run_id,
        "radar_version": __version__,
        "radar_commit": _git_commit(),
        "title": args.title,
        "created_at": _now().isoformat(timespec="seconds"),
        "pack": pack["pack"],
        "pack_version": pack.get("version"),
        "pack_sha256": sha256_file(args.pack),
        "seeds_sha256": sha256_file(args.seeds),
        "mode": "run",
        "base": None,
        "options": {"github": bool(args.github), "gitee": bool(args.gitee),
                    "snowball": bool(args.snowball), "fetch": bool(args.fetch),
                    "fetch_limit": args.fetch_limit, "web": bool(args.web),
                    "web_limit": args.web_limit, "respect_robots": bool(args.respect_robots),
                    "require_web_verify": bool(args.require_web_verify),
                    "verify_quotes": bool(args.verify_quotes), "limit": args.limit,
                    "max_queries": args.max_queries, "strict": bool(args.strict)},
        "counts": {"sources": len(sources), "modules": len(coverage["modules"]),
                   "subsystems": len(coverage["subsystems"])},
        "warnings": warnings,
    }
    write_run(out, pack, sources, coverage, state)
    return {
        "run": str(out),
        "sources": len(sources),
        "modules": len(coverage["modules"]),
        "subsystems": len(coverage["subsystems"]),
        "summary": coverage["summary"],
        "warnings": warnings,
    }


def cmd_claims(args):
    pack = load_pack(args.pack)
    sources = read_sources(args.run)
    data = load_json(args.claims)
    results = evaluate_claims(data, pack, sources)
    meta = {
        "schema_version": 1,
        "run": args.run,
        "pack": pack["pack"],
        "created_at": _now().isoformat(timespec="seconds"),
        "radar_version": __version__,
        "claims_sha256": sha256_file(args.claims),
        "count": len(results),
    }
    write_claims(args.out, results, meta)
    return {
        "out": str(args.out),
        "claims": len(results),
        "high": sum(1 for r in results if r["label"] == "high"),
        "medium": sum(1 for r in results if r["label"] == "medium"),
        "low": sum(1 for r in results if r["label"] == "low"),
        "contested": sum(1 for r in results if r["status"] == "contested"),
    }


def cmd_validate(args):
    pack = load_pack(args.pack)
    seeds = load_seeds(args.seeds, pack, strict=args.strict)
    return {
        "pack": pack["pack"],
        "pack_version": pack.get("version"),
        "modules": len(pack["modules"]),
        "subsystems": len(pack["subsystems"]),
        "sources": len(seeds),
        "selected": sum(1 for s in seeds if s["status"] == "selected"),
        "needs_review": sum(1 for s in seeds if s["status"] == "needs_review"),
        "rejected": sum(1 for s in seeds if s["status"] == "rejected"),
    }


def cmd_scan(args):
    result = cmd_run(args)
    out = Path(args.out)
    diff_path = out / "diff.md"
    text = diff_runs(args.base, str(out), out=str(diff_path))
    old_sources = read_sources(args.base)
    new_sources = read_sources(out)
    changes = compare_sources(old_sources, new_sources)
    write_changes(out, changes)
    state = load_json(out / "state.json")
    state["mode"] = "scan"
    state["base"] = args.base
    state["since"] = args.base
    write_json(out / "state.json", state)
    result["diff"] = str(diff_path)
    result["diff_bytes"] = len(text)
    result["changes"] = {"added": len(changes["added"]),
                         "removed": len(changes["removed"]),
                         "changed": len(changes["changed"]),
                         "unchanged": changes["unchanged"]}
    if args.fail_on_change and (changes["added"] or changes["removed"] or changes["changed"]):
        result["_exit_code"] = 2
    return result


def cmd_diff(args):
    text = diff_runs(args.old, args.new, out=args.out)
    return {"old": args.old, "new": args.new, "out": args.out, "bytes": len(text)}


def cmd_draft(args):
    if not shutil.which("curl"):
        raise RadarError("draft 需要 curl；请先安装 curl")
    pack = load_pack(args.pack)
    urls = list(args.url or [])
    if args.urls_file:
        text = Path(args.urls_file).read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    if not urls:
        raise RadarError("请至少提供一个 --url 或 --urls-file")
    covers = [c.strip() for c in args.covers.split(",") if c.strip()] if args.covers else None
    payload, warnings, skipped = draft_seeds_from_urls(
        pack, urls, covers=covers, existing_seeds_path=args.seeds,
        token=os.environ.get("GITHUB_TOKEN"), gitee_token=_gitee_token(),
        timeout=args.timeout)
    write_json(args.out, payload)
    return {
        "out": str(args.out),
        "pack": pack["pack"],
        "drafted": len(payload["sources"]),
        "skipped_duplicates": len(skipped),
        "warnings": warnings,
    }


def build_parser():
    p = argparse.ArgumentParser(prog="radar", description="最小行业雷达：pack + 来源账本 + 覆盖度")
    sub = p.add_subparsers(dest="command", required=True)

    def add_run_args(p):
        p.add_argument("--pack", required=True)
        p.add_argument("--seeds", required=True)
        p.add_argument("--title", required=True)
        p.add_argument("--out", required=True)
        p.add_argument("--github", action="store_true", help="可选：加 GitHub 搜索")
        p.add_argument("--gitee", action="store_true", help="可选：加 Gitee 搜索（需要 GITEE_TOKEN）")
        p.add_argument("--snowball", action="store_true", help="可选：forward snowballing（GitHub forks）")
        p.add_argument("--snowball-per-source", type=int, default=2)
        p.add_argument("--snowball-max", type=int, default=5)
        p.add_argument("--fetch", action="store_true", help="可选：抓 URL 的 ETag/content_hash")
        p.add_argument("--fetch-limit", type=int, default=0)
        p.add_argument("--fetch-timeout", type=int, default=20)
        p.add_argument("--web", action="store_true", help="可选：抽取公开网页正文 + 许可提示")
        p.add_argument("--web-limit", type=int, default=5)
        p.add_argument("--web-timeout", type=int, default=20)
        p.add_argument("--respect-robots", action="store_true", help="可选：遵守 robots.txt")
        p.add_argument("--require-web-verify", action="store_true",
                       help="只承认本次验证的 quote，忽略 seeds 自带标记")
        p.add_argument("--verify-quotes", action="store_true",
                       help="抓取 source 正文校验 quote（GitHub/Gitee/网页）")
        p.add_argument("--verify-limit", type=int, default=0)
        p.add_argument("--verify-timeout", type=int, default=20)
        p.add_argument("--limit", type=int, default=3)
        p.add_argument("--max-queries", type=int, default=3)
        p.add_argument("--strict", action="store_true", help="要求 v0.1 的完整 12 字段")

    r = sub.add_parser("run", help="跑一次雷达")
    add_run_args(r)
    r.set_defaults(func=cmd_run)

    sc = sub.add_parser("scan", help="增量扫描：新 run + 与 base diff")
    add_run_args(sc)
    sc.add_argument("--base", "--since", dest="base", required=True, help="上一次 run 目录（--since 同义）")
    sc.add_argument("--fail-on-change", action="store_true",
                    help="有新增/移除/变化时退出码 2（仍会写完产物）")
    sc.set_defaults(func=cmd_scan)

    cl = sub.add_parser("claims", help="校验 claim 账本并计算置信度")
    cl.add_argument("--pack", required=True)
    cl.add_argument("--run", required=True, help="已有 run 目录")
    cl.add_argument("--claims", required=True)
    cl.add_argument("--out", required=True)
    cl.set_defaults(func=cmd_claims)

    v = sub.add_parser("validate", help="只校验 pack/seeds")
    v.add_argument("--pack", required=True)
    v.add_argument("--seeds", required=True)
    v.add_argument("--strict", action="store_true", help="要求 v0.1 的完整 12 字段")
    v.set_defaults(func=cmd_validate)

    d = sub.add_parser("diff", help="比较两次 run")
    d.add_argument("--from", dest="old", required=True)
    d.add_argument("--to", dest="new", required=True)
    d.add_argument("--out", default=None)
    d.set_defaults(func=cmd_diff)

    dr = sub.add_parser("draft", help="从 URL 自动抓取元数据与候选引文，生成 seeds 草稿")
    dr.add_argument("--pack", required=True)
    dr.add_argument("--url", action="append", default=[], help="候选来源 URL（可重复）")
    dr.add_argument("--urls-file", default=None, help="每行一个 URL 的文本文件（# 开头为注释）")
    dr.add_argument("--covers", default=None, help="可选：逗号分隔的模块/子系统 ID，如 M02,S04")
    dr.add_argument("--seeds", default=None, help="可选：已有 seeds 文件，用于续编 ID 与 URL 去重")
    dr.add_argument("--out", required=True, help="输出草稿 JSON 文件")
    dr.add_argument("--timeout", type=int, default=20)
    dr.set_defaults(func=cmd_draft)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.func(args)
        code = result.pop("_exit_code", 0)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return code
    except (RadarError, OSError, ValueError) as exc:
        print("[fail] %s" % exc, file=sys.stderr)
        return 1
