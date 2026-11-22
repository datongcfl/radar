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
from .model import (RadarError, enforce_web_verification, load_json, load_pack, load_seeds,
                    merge_sources, sha256_file, write_json)
from .report import write_run
from .state import compare_sources, read_sources, write_changes
from .discover import run_discovery
from .business_graph import build_business_graph, validate_business_model
from .business_invariants import validate_observation_bundle
from .business_observation_extractor import extract_table_observations
from .document_parser import extract_csv_document, extract_office_document
from .ledger_control_pipeline import run_ledger_control_pipeline
from .discovery_store import JsonWorkspaceStore


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


def cmd_discover(args):
    if args.github and not shutil.which("curl"):
        raise RadarError("--github 需要 curl；请先安装 curl 或去掉 --github")
    return run_discovery(args.workspace, args.requirements, args.pack,
                         args.seeds, workspace_root=args.workspace_root,
                         github=args.github, github_limit=args.github_limit,
                         business_model_path=args.business_model)


def cmd_extract_observations(args):
    pack = load_pack(args.pack)
    model = validate_business_model(load_json(args.business_model), pack)
    store = JsonWorkspaceStore(args.workspace_root, args.workspace)
    workspace_rows = store.list_records("workspace")
    if not workspace_rows:
        raise RadarError("Workspace is not initialized")
    workspace = workspace_rows[0]
    expected_digest = sha256_file(args.pack)
    locked = any(ref.get("pack") == pack["pack"]
                 and str(ref.get("version")) == str(pack.get("version"))
                 and ref.get("digest") == expected_digest
                 for ref in workspace.get("pack_refs", []))
    if not locked:
        raise RadarError("Workspace Pack version lock differs; use the Pack version locked by this Workspace")
    assets = store.list_records("asset")
    asset = next((item for item in assets if item["id"] == args.asset_id), None)
    if asset is None:
        raise RadarError("asset_id is not present in the selected Workspace")
    source_path = args.source_path or Path(args.input).name
    extension = Path(args.input).suffix.lower().lstrip(".")
    if extension == "csv":
        try:
            content = Path(args.input).read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            raise RadarError("could not read CSV input: %s" % exc)
        parsed = extract_csv_document(content)
    elif extension == "xlsx":
        try:
            parsed = extract_office_document(Path(args.input).read_bytes(), "xlsx")
        except OSError as exc:
            raise RadarError("could not read XLSX input: %s" % exc)
    else:
        raise RadarError("extract-observations supports CSV and XLSX inputs only")
    if parsed["status"] != "parsed":
        raise RadarError("document parsing %s: %s" %
                         (parsed["status"], parsed.get("reason") or "no reason"))
    for chunk in parsed["chunks"]:
        chunk["locator"]["path"] = source_path
    evidence = [item for item in store.list_records("evidence")
                if item.get("asset_id") == args.asset_id]
    result = extract_table_observations(
        model.get("invariants", []), parsed["chunks"], evidence,
        args.asset_id, origin="static_source")
    validate_observation_bundle(result, model.get("invariants", []), evidence)
    write_json(args.out, result)
    return {"out": str(args.out), "asset_id": args.asset_id,
            "source_path": source_path, "counts": result["summary"]}


def cmd_business_graph(args):
    pack = load_pack(args.pack)
    model = load_json(args.business_model)
    store = JsonWorkspaceStore(args.workspace_root, args.workspace)
    workspace = store.list_records("workspace")[0]
    expected_digest = sha256_file(args.pack)
    locked = any(ref.get("pack") == pack["pack"]
                 and str(ref.get("version")) == str(pack.get("version"))
                 and ref.get("digest") == expected_digest
                 for ref in workspace.get("pack_refs", []))
    if not locked:
        raise RadarError("Workspace Pack version lock differs; use the Pack version locked by this Workspace")
    graph = build_business_graph(
        model, pack,
        requirements=store.list_records("requirement"),
        assets=store.list_records("asset"),
        evidence=store.list_records("evidence"),
        model_digest=sha256_file(args.business_model),
        workspace_id=args.workspace,
        discovery_runs=store.list_records("discovery_run"),
        relationships=store.list_records("relationship"),
        observations=load_json(args.observations) if getattr(args, "observations", None) else None,
        ledger_control_results=load_json(args.ledger_control) if getattr(args, "ledger_control", None) else None,
    )
    write_json(args.out, graph)
    return {"out": str(args.out), "counts": graph["counts"],
            "pack": graph["pack"], "business_model_version": graph["business_model_version"]}


def cmd_ledger_control(args):
    bundle = load_json(args.input)
    if not isinstance(bundle, dict):
        raise RadarError("ledger-control input must be a JSON object")
    required = ("ledger_effects", "evidence_records",
                "extraction_manifests", "aggregation_rules")
    missing = [field for field in required if field not in bundle]
    if missing:
        raise RadarError("ledger-control input missing fields: %s" % ", ".join(missing))
    result = run_ledger_control_pipeline(
        bundle["ledger_effects"], bundle["evidence_records"],
        bundle["extraction_manifests"], bundle["aggregation_rules"],
        reconciliation_tolerance=bundle.get("reconciliation_tolerance", "0.01"),
        voucher_tolerance=bundle.get("voucher_tolerance", "0"))
    write_json(args.out, result)
    return {"out": str(args.out), "summary": result["summary"],
            "schema_version": result["schema_version"]}


def cmd_diff(args):
    text = diff_runs(args.old, args.new, out=args.out)
    return {"old": args.old, "new": args.new, "out": args.out, "bytes": len(text)}


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

    ds = sub.add_parser("discover", help="从需求出发执行资产发现、证据整理和初步评价")
    ds.add_argument("--workspace", required=True, help="稳定 Workspace ID，必须使用 ws_ 前缀")
    ds.add_argument("--workspace-root", default=".", help="Workspace 存储根目录")
    ds.add_argument("--requirements", required=True, help="schema_version=1 的需求文件")
    ds.add_argument("--pack", required=True)
    ds.add_argument("--seeds", required=True, help="兼容现有 Seeds 来源账本")
    ds.add_argument("--github", action="store_true",
                    help="主动搜索 GitHub 文件、Issues 和 PR（需要 GITHUB_TOKEN）")
    ds.add_argument("--github-limit", type=int, default=5,
                    help="每条需求、每个 GitHub 搜索类型的候选上限（1-10）")
    ds.add_argument("--business-model", default=None,
                    help="行业业务模型 JSON；默认读取 Pack 同目录的 business-model.json")
    ds.set_defaults(func=cmd_discover)

    eo = sub.add_parser("extract-observations",
        help="从带有精确 Evidence 的 CSV/XLSX 表格提取结构化业务观察值")
    eo.add_argument("--workspace", required=True)
    eo.add_argument("--workspace-root", default=".")
    eo.add_argument("--pack", required=True)
    eo.add_argument("--business-model", required=True)
    eo.add_argument("--asset-id", required=True)
    eo.add_argument("--input", required=True, help="CSV 或 XLSX 文件")
    eo.add_argument("--source-path", default=None,
                    help="与 Workspace Evidence locator.path 完全一致的原始路径")
    eo.add_argument("--out", required=True)
    eo.set_defaults(func=cmd_extract_observations)

    bg = sub.add_parser("business-graph", help="从行业 Pack 声明和 Workspace 证据生成派生业务图谱")
    bg.add_argument("--workspace", required=True)
    bg.add_argument("--workspace-root", default=".")
    bg.add_argument("--pack", required=True)
    bg.add_argument("--business-model", required=True)
    bg.add_argument("--out", required=True)
    bg.add_argument("--observations", default=None,
                    help="可选：schema_version=1 的结构化业务观察值 JSON")
    bg.add_argument("--ledger-control", default=None,
                    help="可选：radar ledger-control 生成的完整流水线结果 JSON")
    bg.set_defaults(func=cmd_business_graph)

    lc = sub.add_parser("ledger-control",
        help="运行来源账本验证、凭证平衡、账簿聚合和库存总账勾稽")
    lc.add_argument("--input", required=True,
                    help="包含 ledger_effects/evidence_records/extraction_manifests/aggregation_rules 的 JSON")
    lc.add_argument("--out", required=True)
    lc.set_defaults(func=cmd_ledger_control)

    d = sub.add_parser("diff", help="比较两次 run")
    d.add_argument("--from", dest="old", required=True)
    d.add_argument("--to", dest="new", required=True)
    d.add_argument("--out", default=None)
    d.set_defaults(func=cmd_diff)
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
