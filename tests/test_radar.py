import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from radar.coverage import compute_coverage, gap_rows
from radar.report import render_gaps, render_report
from radar.state import compare_sources, render_changes
from radar.adapters import parse_gitee_items, gitee_search, github_search, collect_github, collect_gitee
from radar.draft import draft_seeds_from_urls
from radar.fetch import apply_fetch, parse_headers
from radar.snowball import parse_github_repo, fork_source, snowball as run_snowball
from radar.web import extract_html, detect_license, apply_web, enrich_web, verify_quotes
from radar.verify import source_text, verify_source, verify_sources
from radar.model import level_for_source
from radar.adapters import infer_covers
from radar.claims import compute_confidence, evaluate_claims, write_claims
from radar.diff import diff_runs
from radar.model import (RadarError, canonical_url, enforce_web_verification, load_pack,
                         load_seeds, merge_sources, validate_source, _infer_platform)

PACK = ROOT / "packs/weak-current/pack.json"
SEEDS = ROOT / "seeds/weak-current.json"


def src(sid, covers, evidence="readme", quotes=None, status="selected"):
    return {
        "id": sid, "platform": "github", "url": "https://example.com/%s" % sid,
        "title": sid, "artifact_type": "readme", "access_status": "public",
        "license": "MIT", "license_status": "clear", "evidence_level": evidence,
        "covers": covers, "quotes": quotes if quotes is not None else ["quote"],
        "status": status, "why_selected": "test",
        "quote_verified": "true", "quote_verified_by": "web",
    }


class TestModel(unittest.TestCase):
    def test_canonical_url(self):
        self.assertEqual(canonical_url("https://www.Example.com/a/?utm_source=x#frag"),
                         "https://example.com/a")
        self.assertEqual(canonical_url("https://example.com/a"), "https://example.com/a")
        self.assertEqual(canonical_url("http://example.com:8080/a?b=2&a=1"),
                         "https://example.com:8080/a?a=1&b=2")
        self.assertEqual(canonical_url("https://user:pw@example.com/a"),
                         "https://example.com/a")
        self.assertEqual(canonical_url("http://example.com/a"),
                         canonical_url("https://example.com/a"))
        self.assertEqual(canonical_url("http://example.com:80/a"),
                         canonical_url("https://example.com/a"))
        self.assertEqual(canonical_url("https://example.com:443/a"),
                         canonical_url("https://example.com/a"))

    def test_infer_covers_short_keywords(self):
        pack = {"modules": [
            {"id": "M01", "name": "AI", "keywords": ["ai"]},
            {"id": "M02", "name": "DC", "keywords": ["dc"]},
            {"id": "M03", "name": "UPS", "keywords": ["ups"]},
        ], "subsystems": []}
        self.assertEqual(infer_covers("maintain container", pack), [])
        self.assertEqual(infer_covers("docs and broadcast", pack), [])
        self.assertEqual(infer_covers("groups", pack), [])
        self.assertEqual(infer_covers("edge ai gateway", pack), ["M01"])
        self.assertEqual(infer_covers("UPS status", pack), ["M03"])

    def test_infer_platform_exact_host(self):
        self.assertEqual(_infer_platform("https://notgithub.com/a/b"), "web")
        self.assertEqual(_infer_platform("https://evilgitee.com/x"), "web")
        self.assertEqual(_infer_platform("https://www.github.com/a/b"), "github")

    def test_merge_keeps_covers_and_quotes(self):
        a = src("A", ["M01", "M02"], quotes=["qa"])
        b = src("B", ["M03"], evidence="production", quotes=["qb"])
        b["url"] = a["url"]
        b["access_status"] = "blocked"
        merged = merge_sources([a, b])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["covers"], ["M01", "M02", "M03"])
        self.assertEqual(merged[0]["quotes"], ["qa", "qb"])
        self.assertEqual(merged[0]["access_status"], "blocked")
        self.assertEqual(merged[0]["_merged_from"], ["A", "B"])

    def test_merge_false_quote_wins(self):
        a = src("A", ["M01"], quotes=["qa"]); a["quote_verified"] = "false"
        b = src("B", ["M01"], quotes=["qb"]); b["url"] = a["url"]; b["quote_verified"] = "unknown"
        merged = merge_sources([a, b])[0]
        self.assertEqual(merged["quote_verified"], "false")

    def test_rejected_does_not_pollute_selected(self):
        a = src("A", ["M01"], quotes=["qa"])
        b = src("B", ["M02"], quotes=["qb"], status="rejected")
        b["url"] = a["url"]
        merged = merge_sources([a, b])[0]
        self.assertEqual(merged["status"], "selected")
        self.assertEqual(merged["covers"], ["M01"])
        self.assertEqual(merged["quotes"], ["qa"])

    def test_enforce_web_verification(self):
        a = src("A", ["M01"], evidence="real_artifact")
        a["quote_verified"] = "true"; a["quote_verified_by"] = "web"
        a["quote_verified_this_run"] = False
        enforce_web_verification([a])
        self.assertEqual(a["quote_verified"], "unknown")
        self.assertIsNone(a["quote_verified_by"])
        self.assertEqual(level_for_source(a), "evidence")

    def test_merge_rejects_duplicate_ids(self):
        a = src("A", ["M01"]); b = src("A", ["M02"]); b["url"] = "https://example.com/other"
        with self.assertRaises(RadarError):
            merge_sources([a, b])

    def test_pack_and_seeds_valid(self):
        pack = load_pack(PACK)
        seeds = load_seeds(SEEDS, pack)
        self.assertEqual(len(pack["modules"]), 14)
        self.assertEqual(len(pack["subsystems"]), 23)
        self.assertEqual(len(seeds), 41)

    def test_second_pack_valid(self):
        pack = load_pack(ROOT / "packs/pet-hospital/pack.json")
        seeds = load_seeds(ROOT / "seeds/pet-hospital.json", pack)
        self.assertEqual(len(pack["modules"]), 6)
        self.assertEqual(len(pack["subsystems"]), 6)
        self.assertEqual(len(seeds), 3)

    def test_data_center_pack_valid(self):
        pack = load_pack(ROOT / "packs/data-center-ops/pack.json")
        seeds = load_seeds(ROOT / "seeds/data-center-ops.json", pack)
        self.assertEqual(len(pack["modules"]), 10)
        self.assertEqual(len(pack["subsystems"]), 16)
        self.assertEqual(len(seeds), 40)

    def test_video_pack_valid(self):
        pack = load_pack(ROOT / "packs/video-kb/pack.json")
        seeds = load_seeds(ROOT / "seeds/video-kb.json", pack)
        self.assertEqual(len(pack["modules"]), 10)
        self.assertEqual(len(pack["subsystems"]), 16)
        self.assertEqual(len(seeds), 32)

    def test_minimal_seed_defaults(self):
        pack = load_pack(PACK)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "minimal.json"
            path.write_text(json.dumps({
                "schema_version": 1, "pack": "weak-current",
                "sources": [{
                    "id": "MIN-001", "url": "https://example.com/doc",
                    "evidence_level": "docs", "covers": ["M01"],
                    "quotes": [], "status": "selected",
                }],
            }), encoding="utf-8")
            seeds = load_seeds(path, pack)
        item = seeds[0]
        self.assertEqual(item["platform"], "web")
        self.assertEqual(item["artifact_type"], "article")
        self.assertEqual(item["access_status"], "public")
        self.assertEqual(item["license"], "unknown")
        self.assertEqual(item["license_status"], "needs_review")
        self.assertEqual(item["why_selected"], "")

    def test_strict_rejects_minimal(self):
        pack = load_pack(PACK)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "minimal.json"
            path.write_text(json.dumps({
                "schema_version": 1, "pack": "weak-current",
                "sources": [{
                    "id": "MIN-001", "url": "https://example.com/doc",
                    "evidence_level": "docs", "covers": ["M01"],
                    "quotes": [], "status": "selected",
                }],
            }), encoding="utf-8")
            with self.assertRaises(RadarError):
                load_seeds(path, pack, strict=True)

    def test_bad_cover_rejected(self):
        pack = load_pack(PACK)
        with self.assertRaises(RadarError):
            validate_source(src("X", ["M99"]), pack)


class TestCoverage(unittest.TestCase):
    def setUp(self):
        self.pack = {"modules": [{"id": "M01", "name": "项目"}],
                     "subsystems": [{"id": "S01", "name": "视频"}]}

    def test_single_source_capped_at_evidence(self):
        cov = compute_coverage(self.pack, [src("A", ["M01"], evidence="real_artifact")])
        row = cov["modules"][0]
        self.assertEqual(row["level"], "evidence")
        self.assertTrue(row["single_source"])

    def test_two_sources_can_be_strong(self):
        b = src("B", ["M01"], evidence="docs")
        b["url"] = "https://other.example/B"
        cov = compute_coverage(self.pack, [
            src("A", ["M01"], evidence="real_artifact"),
            b,
        ])
        self.assertEqual(cov["modules"][0]["level"], "strong")
        self.assertFalse(cov["modules"][0]["single_source"])

    def test_same_host_is_not_strong(self):
        b = src("B", ["M01"], evidence="real_artifact")
        b["url"] = "https://example.com/B2"
        cov = compute_coverage(self.pack, [
            src("A", ["M01"], evidence="real_artifact"), b,
        ])
        self.assertEqual(cov["modules"][0]["level"], "evidence")
        self.assertEqual(cov["modules"][0]["independent_count"], 1)

    def test_mention_does_not_erase_single_source(self):
        a = src("A", ["M01"], evidence="real_artifact")
        b = src("B", ["M01"], quotes=[])
        b["url"] = "https://other.example/B"
        cov = compute_coverage(self.pack, [a, b])
        self.assertTrue(cov["modules"][0]["single_source"])
        self.assertEqual(cov["modules"][0]["evidence_count"], 1)

    def test_unverified_quote_caps_evidence(self):
        a = src("A", ["M01"], evidence="real_artifact")
        a["quote_verified"] = "unknown"
        b = src("B", ["M01"], evidence="docs"); b["url"] = "https://other.example/B"
        cov = compute_coverage(self.pack, [a, b])
        self.assertEqual(cov["modules"][0]["level"], "evidence")

    def test_human_true_is_not_strong(self):
        a = src("A", ["M01"], evidence="real_artifact")
        a["quote_verified"] = "true"; a["quote_verified_by"] = "human"
        b = src("B", ["M01"], evidence="docs"); b["url"] = "https://other.example/B"
        cov = compute_coverage(self.pack, [a, b])
        self.assertEqual(cov["modules"][0]["level"], "evidence")

    def test_false_quote_is_mention(self):
        a = src("A", ["M01"], evidence="real_artifact")
        a["quote_verified"] = "false"
        cov = compute_coverage(self.pack, [a])
        self.assertEqual(cov["modules"][0]["level"], "mention")

    def test_one_verified_one_unknown_not_strong(self):
        a = src("A", ["M01"], evidence="real_artifact")
        b = src("B", ["M01"], evidence="docs")
        b["url"] = "https://other.example/B"; b["quote_verified"] = "unknown"
        b["quote_verified_by"] = None
        cov = compute_coverage(self.pack, [a, b])
        self.assertEqual(cov["modules"][0]["level"], "evidence")
        self.assertEqual(cov["modules"][0]["verified_count"], 1)

    def test_bad_access_is_mention(self):
        a = src("A", ["M01"], evidence="production")
        a["access_status"] = "deleted"
        cov = compute_coverage(self.pack, [a])
        self.assertEqual(cov["modules"][0]["level"], "mention")

    def test_reusable_requires_clear(self):
        a = src("A", ["M01"]); a["license_status"] = "needs_review"
        b = src("B", ["M01"]); b["license_status"] = "clear"; b["url"] = "https://other.example/B"
        cov = compute_coverage(self.pack, [a, b])
        self.assertTrue(cov["modules"][0]["reusable"])

    def test_no_quote_is_mention(self):
        cov = compute_coverage(self.pack, [src("A", ["M01"], quotes=[])])
        self.assertEqual(cov["modules"][0]["level"], "mention")

    def test_rejected_does_not_count(self):
        cov = compute_coverage(self.pack, [src("A", ["M01"], status="rejected")])
        self.assertEqual(cov["modules"][0]["level"], "none")

    def test_gaps_report_includes_single_source(self):
        cov = compute_coverage(self.pack, [src("A", ["M01"], evidence="real_artifact")])
        text = render_gaps(self.pack, cov)
        self.assertIn("单源待印证", text)
        self.assertIn("M01", text)


    def test_gap_query_artifact_not_joined_list(self):
        # {artifact} 插值应取第一个 artifact，而不是把数组拼成 "readme, docs"
        pack = {"title": "T",
                "modules": [{"id": "M01", "name": "模块", "artifacts": ["readme", "docs"]}],
                "subsystems": [{"id": "S01", "name": "子", "artifacts": ["code"]}],
                "query_templates": ["{module} {artifact} 开源"]}
        cov = compute_coverage(pack, [])  # M01/S01 均无来源 → 均进 gaps
        text = render_gaps(pack, cov)
        self.assertIn("模块 readme 开源", text)
        self.assertNotIn("readme, docs", text)

    def test_gap_query_without_artifacts_field(self):
        # pack 项缺 artifacts 字段时不应崩溃，回退为"资料"
        pack = {"title": "T",
                "modules": [{"id": "M01", "name": "模块"}],
                "subsystems": [{"id": "S01", "name": "子"}],
                "query_templates": ["{module} {artifact} 开源"]}
        cov = compute_coverage(pack, [])
        text = render_gaps(pack, cov)
        self.assertIn("模块 资料 开源", text)

    def test_platform_bias_warning_single_platform(self):
        # 90%+ 来源来自单一平台时应输出平台偏置警告
        state = {"title": "T", "run_id": "r1"}
        pack = {"title": "T", "modules": self.pack["modules"], "subsystems": self.pack["subsystems"], "pack": "p", "version": "0"}
        text = render_report(pack, [src("A", ["M01"])], compute_coverage(self.pack, [src("A", ["M01"])]), state)
        self.assertIn("平台偏置", text)

    def test_platform_bias_no_warning_multi_platform(self):
        state = {"title": "T", "run_id": "r1"}
        pack = {"title": "T", "modules": self.pack["modules"], "subsystems": self.pack["subsystems"], "pack": "p", "version": "0"}
        two = [src("A", ["M01"]), src("B", ["M01"])]
        two[1]["platform"] = "gitee"
        cov = compute_coverage(self.pack, two)
        text = render_report(pack, two, cov, state)
        self.assertNotIn("平台偏置", text)

    def test_low_star_high_coverage_listed(self):
        # 低星（≤50）但覆盖 ≥2 格的来源应被列出
        state = {"title": "T", "run_id": "r1"}
        pack = {"title": "T", "modules": self.pack["modules"], "subsystems": self.pack["subsystems"], "pack": "p", "version": "0"}
        low = src("A", ["M01", "S01"])
        low["stars"] = 3
        cov = compute_coverage(self.pack, [low])
        text = render_report(pack, [low], cov, state)
        self.assertIn("低星但高覆盖", text)
        self.assertIn("覆盖 2 格", text)


class TestClaims(unittest.TestCase):
    def _strong(self, sid, host):
        s = src(sid, ["M01"], evidence="real_artifact", quotes=["q"])
        s["url"] = "https://%s.example/x" % host
        return s

    def test_strong_two_hosts(self):
        by = {"A": self._strong("A", "a"), "B": self._strong("B", "b")}
        claim = {"id": "C1", "statement": "s", "covers": ["M01"],
                 "sources": ["A", "B"], "contradicts": []}
        r = compute_confidence(claim, by)
        self.assertEqual(r["confidence"], 0.8)
        self.assertEqual(r["label"], "high")
        self.assertEqual(r["reasons"], [])

    def test_single_source_cap(self):
        by = {"A": self._strong("A", "a")}
        claim = {"id": "C1", "statement": "s", "covers": ["M01"],
                 "sources": ["A"], "contradicts": []}
        r = compute_confidence(claim, by)
        self.assertEqual(r["confidence"], 0.55)
        self.assertIn("single_source", r["reasons"])

    def test_no_quote_cap(self):
        s = self._strong("A", "a"); s["quotes"] = []
        claim = {"id": "C1", "statement": "s", "covers": ["M01"],
                 "sources": ["A"], "contradicts": []}
        r = compute_confidence(claim, {"A": s})
        self.assertEqual(r["confidence"], 0.3)
        self.assertIn("no_quote", r["reasons"])

    def test_contradiction_contested(self):
        by = {"A": self._strong("A", "a"), "B": self._strong("B", "b")}
        claim = {"id": "C1", "statement": "s", "covers": ["M01"],
                 "sources": ["A", "B"], "contradicts": ["C2"]}
        r = compute_confidence(claim, by)
        self.assertEqual(r["status"], "contested")
        self.assertEqual(r["confidence"], 0.4)

    def test_unsupported_by_sources(self):
        by = {"A": self._strong("A", "a")}
        by["A"]["covers"] = ["M01"]
        claim = {"id": "BAD1", "statement": "M12 有发票", "covers": ["M12"],
                 "sources": ["A"], "contradicts": []}
        r = compute_confidence(claim, by)
        self.assertEqual(r["confidence"], 0.30)
        self.assertIn("unsupported_by_sources", r["reasons"])
        with tempfile.TemporaryDirectory() as tmp:
            row = dict(claim); row.update(r)
            write_claims(tmp, [row], {"run": "x", "pack": "weak-current"})
            text = (Path(tmp) / "review.csv").read_text(encoding="utf-8")
        self.assertIn("改主张", text)

    def test_no_verified_source_cap(self):
        by = {"A": self._strong("A", "a")}
        by["A"]["quote_verified"] = "unknown"
        claim = {"id": "C1", "statement": "s", "covers": ["M01"],
                 "sources": ["A"], "contradicts": []}
        r = compute_confidence(claim, by)
        self.assertEqual(r["confidence"], 0.4)
        self.assertIn("no_verified_source", r["reasons"])

    def test_verified_cover_mismatch(self):
        by = {"A": self._strong("A", "a")}
        claim = {"id": "C1", "statement": "s", "covers": ["M12"],
                 "sources": ["A"], "contradicts": []}
        r = compute_confidence(claim, by)
        self.assertEqual(r["confidence"], 0.3)
        self.assertIn("unsupported_by_verified_sources", r["reasons"])

    def test_proprietary_cap(self):
        by = {"A": self._strong("A", "a")}
        by["A"]["license_status"] = "proprietary"
        claim = {"id": "C1", "statement": "s", "covers": ["M01"],
                 "sources": ["A"], "contradicts": []}
        r = compute_confidence(claim, by)
        self.assertEqual(r["confidence"], 0.4)
        self.assertIn("proprietary_reference", r["reasons"])

    def test_contradiction_bidirectional(self):
        pack = load_pack(PACK)
        a = self._strong("A", "a"); b = self._strong("B", "b")
        data = {"schema_version": 1, "pack": "weak-current", "claims": [
            {"id": "C1", "statement": "A", "covers": ["M01"], "sources": ["A"], "contradicts": ["C2"]},
            {"id": "C2", "statement": "B", "covers": ["M01"], "sources": ["B"], "contradicts": []},
        ]}
        rows = {r["id"]: r for r in evaluate_claims(data, pack, [a, b])}
        self.assertEqual(rows["C1"]["status"], "contested")
        self.assertEqual(rows["C2"]["status"], "contested")
        self.assertIn("contradiction", rows["C2"]["reasons"])

    def test_csv_injection_sanitized(self):
        row = {"id": "C1", "statement": "=cmd|' /C calc'!A0", "confidence": 0.5,
               "label": "medium", "status": "open", "sources": ["A"],
               "reasons": [], "contradicts": []}
        with tempfile.TemporaryDirectory() as tmp:
            write_claims(tmp, [row], {"run": "x", "pack": "weak-current"})
            text = (Path(tmp) / "review.csv").read_text(encoding="utf-8")
        self.assertIn("'=cmd", text)

    def test_unknown_source_rejected(self):
        pack = load_pack(PACK)
        data = {"schema_version": 1, "pack": "weak-current", "claims": [{
            "id": "C1", "statement": "s", "covers": ["M01"], "sources": ["NOPE"]}]}
        with self.assertRaises(RadarError):
            evaluate_claims(data, pack, [])


class TestWeb(unittest.TestCase):
    def test_extract_html(self):
        page = extract_html("<html><head><title>弱电报价</title>"
                            "<meta name='description' content='这是一个用于弱电工程报价与成本管理的页面内容'>"
                            "</head><body><script>bad()</script><p>弱电工程报价清单与成本管理说明。</p></body></html>")
        self.assertEqual(page["title"], "弱电报价")
        self.assertNotIn("bad()", page["text"])
        self.assertTrue(page["quotes"])

    def test_detect_license(self):
        mit = "Permission is hereby granted, free of charge, to any person obtaining a copy"
        self.assertEqual(detect_license(mit + "\nAll rights reserved")[:2], ("MIT", "clear"))
        self.assertEqual(detect_license(mit)[:2], ("MIT", "clear"))
        self.assertEqual(detect_license("licensed under the Apache License, Version 2.0")[:2],
                         ("Apache-2.0", "clear"))
        self.assertEqual(detect_license("GNU General Public License Version 3")[:2],
                         ("GPL-3.0", "needs_review"))
        self.assertEqual(detect_license("GNU Affero General Public License")[:2],
                         ("AGPL-3.0", "needs_review"))
        self.assertEqual(detect_license("All rights reserved.")[:2], ("proprietary", "proprietary"))
        self.assertEqual(detect_license("A 项目采用 Apache 协议")[:2], ("Apache-2.0", "needs_review"))
        self.assertEqual(detect_license("MIT License")[:2], ("MIT", "needs_review"))
        self.assertEqual(detect_license("hello")[:2], ("unknown", "needs_review"))

    def test_verify_quotes(self):
        self.assertEqual(verify_quotes(["弱电 工程"], "这是弱电工程报价页面"), "true")
        self.assertEqual(verify_quotes(["不存在的句子"], "短页面"), "unknown")
        self.assertEqual(verify_quotes(["不存在的句子"], "长页面" * 200), "false")
        self.assertEqual(verify_quotes(["不存在的句子"], "长页面" * 200, truncated=True), "unknown")

    def test_extract_html_marks_truncated(self):
        page = "<html><body>" + ("padding sentence. " * 2000) + "<p>THE REAL QUOTE IS AT THE END.</p></body></html>"
        ex = extract_html(page, max_chars=2000)
        self.assertTrue(ex["truncated"])
        self.assertEqual(verify_quotes(["THE REAL QUOTE IS AT THE END."], ex["text"], truncated=ex["truncated"]), "unknown")

    def test_apply_web_empty_quotes_does_not_self_certify_strong(self):
        pack = {"pack": "p", "title": "T",
                "modules": [{"id": "M01", "name": "Alpha", "artifacts": ["docs"], "keywords": ["alpha"]}],
                "subsystems": [{"id": "S01", "name": "Beta", "artifacts": ["docs"], "keywords": ["beta"]}]}
        page = {"title": "Doc", "description": "", "truncated": False,
                "text": "Alpha is fully described in this documentation page with implementation details.",
                "quotes": ["Alpha is fully described in this documentation page with implementation details."]}
        srcs = []
        for i, host in enumerate(("a.example.com", "b.example.com"), 1):
            s = src("W%d" % i, ["M01"], evidence="real_artifact", quotes=[])
            s["platform"] = "web"
            s["url"] = "https://%s/doc" % host
            srcs.append(apply_web(s, page))
        self.assertEqual(srcs[0]["quote_verified"], "unknown")
        self.assertIsNone(srcs[0]["quote_verified_by"])
        self.assertFalse(srcs[0]["quote_verified_this_run"])
        self.assertEqual(compute_coverage(pack, srcs)["modules"][0]["level"], "evidence")

    def test_web_output_reloads_and_grades(self):
        pack = load_pack(PACK)
        source = src("W1", ["M01"], evidence="real_artifact", quotes=["弱电工程报价"])
        source["url"] = "https://example.com/w1"
        page = {"title": "T", "description": "", "quotes": [],
                "text": "弱电工程报价与成本管理说明。" * 30}
        out = apply_web(source, page)
        self.assertEqual(out["quote_verified"], "true")
        self.assertEqual(out["quote_verified_by"], "web")
        self.assertTrue(out["quote_verified_this_run"])
        loaded = validate_source({k: v for k, v in out.items()
                                  if k not in {"_merged_from"}}, pack, strict=False)
        self.assertEqual(level_for_source(loaded), "strong")

    def test_apply_web_false_quote_is_mention(self):
        source = src("W2", ["M01"], evidence="real_artifact", quotes=["不存在的句子"])
        source["url"] = "https://example.com/w2"
        out = apply_web(source, {"title": "T", "description": "", "quotes": [],
                                 "text": "长正文" * 500})
        self.assertEqual(out["quote_verified"], "false")
        self.assertEqual(level_for_source(out), "mention")

    def test_apply_web(self):
        out = apply_web({"id": "A", "url": "https://example.com", "title": "x",
                         "license": "unknown", "license_status": "needs_review"},
                        {"title": "T", "description": "",
                         "text": "Permission is hereby granted, free of charge, to any person obtaining a copy",
                         "quotes": ["q"]})
        self.assertEqual(out["license"], "MIT")
        self.assertEqual(out["license_status"], "clear")
        self.assertIn("q", out["quotes"])

    def test_chinese_quotes_not_glued(self):
        text = ("这是弱电工程报价与成本管理的第一段内容，覆盖询价、清单和毛利。"
                "这是第二段内容，说明合同、采购和施工进度的边界。")
        page = extract_html("<p>%s</p>" % text)
        self.assertGreaterEqual(len(page["quotes"]), 2)
        for q in page["quotes"]:
            self.assertLessEqual(len(q), 241)

    def test_web_404_not_success(self):
        src = {"id": "W1", "url": "https://example.com/404", "platform": "web",
               "status": "selected", "access_status": "public", "title": "x"}
        with mock.patch("radar.web.fetch_text", return_value=(None, 404, "HTTP 404")):
            out, warnings = enrich_web([src], limit=1)
        self.assertEqual(out[0]["web_error"], "HTTP 404")
        self.assertEqual(out[0]["http_status"], 404)
        self.assertNotEqual(out[0]["access_status"], "public")
        self.assertTrue(warnings)


class TestFetch(unittest.TestCase):
    def test_parse_headers_and_apply(self):
        headers = parse_headers("HTTP/2 200\r\nETag: \"abc\"\r\nLast-Modified: Wed, 01 Jan 2026 00:00:00 GMT\r\n")
        self.assertEqual(headers["etag"], '"abc"')
        out = apply_fetch({"id": "A", "url": "https://example.com"}, 200, headers, "hash1")
        self.assertEqual(out["access_status"], "public")
        self.assertEqual(out["content_hash"], "hash1")
        self.assertEqual(out["etag"], '"abc"')
        self.assertIn("last_seen", out)

    def test_apply_fetch_auth_statuses(self):
        self.assertEqual(apply_fetch({}, 401, {}, None)["access_status"], "login_required")
        self.assertEqual(apply_fetch({}, 403, {}, None)["access_status"], "blocked")
        self.assertEqual(apply_fetch({}, 404, {}, None)["access_status"], "deleted")


class TestSnowball(unittest.TestCase):
    def test_parse_github_repo(self):
        self.assertEqual(parse_github_repo("https://github.com/demo/elv"), "demo/elv")
        self.assertIsNone(parse_github_repo("https://gitee.com/demo/elv"))

    def test_fork_source_inherits_covers(self):
        parent = src("A", ["M01", "S01"])
        parent["url"] = "https://github.com/demo/elv"
        fork = {"full_name": "other/elv", "html_url": "https://github.com/other/elv",
                "stargazers_count": 1, "language": "Python", "license": {"spdx_id": "MIT"}}
        out = fork_source(fork, parent, 1)
        self.assertEqual(out["platform"], "github")
        self.assertEqual(out["covers"], ["M01", "S01"])
        self.assertEqual(out["license_status"], "clear")
        self.assertIn("fork of A", out["why_selected"])

    def test_snowball_uses_forks(self):
        parent = src("A", ["M01"])
        parent["url"] = "https://github.com/demo/elv"
        forks = [{"full_name": "other/elv", "html_url": "https://github.com/other/elv",
                  "stargazers_count": 1, "license": {"spdx_id": "MIT"}}]
        with mock.patch("radar.snowball.github_forks", return_value=(forks, None)):
            out, warns = run_snowball([parent], {"modules": [{"id": "M01", "name": "项目", "keywords": ["项目"]}], "subsystems": [{"id": "S01", "name": "子系统", "keywords": ["子系统"]}]})
        self.assertEqual(len(out), 1)
        self.assertEqual(warns, [])
        self.assertEqual(out[0]["covers"], ["M01"])


class TestGitee(unittest.TestCase):
    def test_parse_gitee_items(self):
        pack = load_pack(PACK)
        items = [{
            "full_name": "demo/elv-quote", "html_url": "https://gitee.com/demo/elv-quote",
            "description": "弱电 报价 清单", "stargazers_count": 3,
            "updated_at": "2026-11-01T00:00:00+08:00", "language": "Python",
        }]
        out = parse_gitee_items(items, pack, "弱电 报价")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["platform"], "gitee")
        self.assertEqual(out[0]["license"], "unknown")
        self.assertEqual(out[0]["license_status"], "needs_review")
        self.assertIn("M06", out[0]["covers"])

    def test_gitee_offset_ids(self):
        pack = load_pack(PACK)
        items = [{"full_name": "demo/elv", "html_url": "https://gitee.com/demo/elv",
                  "description": "弱电 报价", "stargazers_count": 1}]
        out = parse_gitee_items(items, pack, "q", id_offset=3)
        self.assertEqual(out[0]["id"], "GT-004")

    def test_github_offset_ids(self):
        pack = load_pack(PACK)
        item = {"full_name": "demo/elv", "html_url": "https://github.com/demo/elv",
                "description": "弱电 报价", "stargazers_count": 1}
        with mock.patch("radar.adapters._curl_json", return_value=({"items": [item]}, None)):
            out, err = github_search("q", pack, id_offset=5)
        self.assertIsNone(err)
        self.assertEqual(out[0]["id"], "GH-006")

    def test_gitee_without_token_is_explicit(self):
        pack = load_pack(PACK)
        got, warn = gitee_search("弱电", pack, token=None)
        self.assertEqual(got, [])
        self.assertIn("GITEE_TOKEN", warn)

    def test_multi_query_github_gitee_ids_do_not_collide(self):
        pack = load_pack(PACK)
        def gh_item(name, desc, lic="MIT"):
            return {"full_name": name, "description": desc, "topics": [],
                    "html_url": "https://github.com/" + name,
                    "license": {"spdx_id": lic}, "updated_at": "2026", "stargazers_count": 1}
        gh_responses = [
            ({"items": [gh_item("x/skip1", "nothing"), gh_item("y/hit1", "弱电 报价")]}, None),
            ({"items": [gh_item("z/hit2", "弱电 报价", "GPL-3.0"), gh_item("w/skip2", "nothing")]}, None),
            ({"items": [gh_item("u/skip3", "nothing"), gh_item("v/hit3", "弱电 报价")]}, None),
        ]
        with mock.patch("radar.adapters._curl_json", side_effect=gh_responses):
            got, warns = collect_github(pack, limit_per_query=2, max_queries=3)
        self.assertEqual(warns, [])
        self.assertEqual([g["id"] for g in got], ["GH-001", "GH-002", "GH-003"])
        self.assertEqual(got[1]["license_status"], "needs_review")

        def gt_item(name, desc):
            return {"full_name": name, "description": desc,
                    "html_url": "https://gitee.com/" + name,
                    "license": "MIT", "updated_at": "2026", "stargazers_count": 1}
        gt_responses = [
            ([gt_item("x/skip1", "nothing"), gt_item("y/hit1", "弱电 报价")], None),
            ([gt_item("z/hit2", "弱电 报价"), gt_item("w/skip2", "nothing")], None),
            ([gt_item("u/skip3", "nothing"), gt_item("v/hit3", "弱电 报价")], None),
        ]
        gt_pack = dict(pack)
        gt_pack["source_map"] = {"gitee": ["q1", "q2", "q3"]}
        with mock.patch("radar.adapters._curl_json", side_effect=gt_responses):
            got_gt, warns_gt = collect_gitee(gt_pack, limit_per_query=2, max_queries=3, token="tok")
        self.assertEqual(warns_gt, [])
        self.assertEqual([g["id"] for g in got_gt], ["GT-001", "GT-002", "GT-003"])


class TestCLIErrors(unittest.TestCase):
    def test_missing_run_prints_fail_not_traceback(self):
        proc = subprocess.run([sys.executable, "-m", "radar", "diff", "--from", "/nope/a",
                               "--to", "/nope/b"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("[fail]", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_run_cleans_stale_scan_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run"
            cmd = [sys.executable, "-m", "radar", "run", "--pack", str(PACK),
                   "--seeds", str(SEEDS), "--title", "T", "--out", str(out)]
            subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True)
            (out / "changes.md").write_text("stale", encoding="utf-8")
            (out / "diff.md").write_text("stale", encoding="utf-8")
            subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True)
            self.assertFalse((out / "changes.md").exists())
            self.assertFalse((out / "diff.md").exists())


class TestChanges(unittest.TestCase):
    def test_added_removed_changed(self):
        a = src("A", ["M01"]); a["quotes"] = ["old"]
        b = src("B", ["S01"])
        a2 = src("A", ["M01"]); a2["quotes"] = ["new"]
        c = src("C", ["M01"])
        result = compare_sources([a, b], [a2, c])
        self.assertEqual([x["id"] for x in result["added"]], ["C"])
        self.assertEqual([x["id"] for x in result["removed"]], ["B"])
        self.assertEqual(len(result["changed"]), 1)
        self.assertIn("quotes", result["changed"][0]["fields"])
        self.assertIn("新增", render_changes(result))

    def test_no_change(self):
        a = src("A", ["M01"])
        result = compare_sources([a], [dict(a)])
        self.assertEqual(result["added"], [])
        self.assertEqual(result["removed"], [])
        self.assertEqual(result["changed"], [])
        self.assertEqual(result["unchanged"], 1)


class TestCLI(unittest.TestCase):
    def test_run_and_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            out1 = tmp / "run1"
            subprocess.run([sys.executable, "-m", "radar", "run", "--pack", str(PACK),
                            "--seeds", str(SEEDS), "--title", "测试", "--out", str(out1)],
                           cwd=ROOT, check=True, capture_output=True, text=True)
            for name in ["sources.jsonl", "coverage.json", "toc.md", "coverage.md",
                         "gaps.md", "report.md", "state.json"]:
                self.assertTrue((out1 / name).exists(), name)

            data = json.loads(SEEDS.read_text(encoding="utf-8"))
            data["sources"] = [s for s in data["sources"] if s["id"] != "SRC-013"]
            seeds2 = tmp / "seeds2.json"
            seeds2.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            out2 = tmp / "run2"
            subprocess.run([sys.executable, "-m", "radar", "run", "--pack", str(PACK),
                            "--seeds", str(seeds2), "--title", "测试", "--out", str(out2)],
                           cwd=ROOT, check=True, capture_output=True, text=True)
            diff = tmp / "diff.md"
            diff_runs(out1, out2, out=diff)
            text = diff.read_text(encoding="utf-8")
            self.assertIn("移除来源", text)
            self.assertIn("SRC-013", text)

            scan_out = tmp / "scan"
            subprocess.run([sys.executable, "-m", "radar", "scan", "--pack", str(PACK),
                            "--seeds", str(seeds2), "--title", "测试", "--out", str(scan_out),
                            "--since", str(out1)], cwd=ROOT, check=True, capture_output=True, text=True)
            self.assertTrue((scan_out / "diff.md").exists())
            self.assertTrue((scan_out / "changes.md").exists())
            self.assertIn("SRC-013", (scan_out / "diff.md").read_text(encoding="utf-8"))
            self.assertIn("SRC-013", (scan_out / "changes.md").read_text(encoding="utf-8"))
            state = json.loads((scan_out / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["mode"], "scan")
            self.assertEqual(state["since"], str(out1))
            self.assertEqual(state["radar_version"], "1.7.0")
            self.assertIn("radar_commit", state)
            self.assertIn("Radar: v1.7.0", (scan_out / "report.md").read_text(encoding="utf-8"))

            claims_file = tmp / "claims.json"
            claims_file.write_text(json.dumps({
                "schema_version": 1, "pack": "weak-current",
                "claims": [{"id": "C1", "statement": "测试主张", "covers": ["M01"],
                            "sources": ["SRC-001"], "contradicts": []}],
            }, ensure_ascii=False), encoding="utf-8")
            claims_out = tmp / "claims"
            subprocess.run([sys.executable, "-m", "radar", "claims", "--pack", str(PACK),
                            "--run", str(out1), "--claims", str(claims_file),
                            "--out", str(claims_out)], cwd=ROOT, check=True,
                           capture_output=True, text=True)
            self.assertTrue((claims_out / "claims.md").exists())
            self.assertTrue((claims_out / "review.csv").exists())
            self.assertEqual(json.loads((claims_out / "state.json").read_text())["radar_version"], "1.7.0")


class TestVerify(unittest.TestCase):
    def test_verify_source_true(self):
        with mock.patch("radar.verify.source_text", return_value=("弱电工程报价与成本管理说明", 200, None)):
            out = verify_source({"id": "A", "url": "https://example.com", "platform": "web",
                                 "quotes": ["弱电工程报价"]})
        self.assertEqual(out["quote_verified"], "true")
        self.assertEqual(out["quote_verified_by"], "web")
        self.assertTrue(out["quote_verified_this_run"])

    def test_verify_quotes_strip_markdown_links(self):
        text = "Please see the [website](https://apps.ankiweb.net) to learn more."
        self.assertEqual(verify_quotes(["Please see the website to learn more."], text), "true")

    def test_github_blob_file_included(self):
        with mock.patch("radar.verify._curl_text", return_value=("Templates is a core plugin.", 200, None)) as call:
            text, status, err = source_text({"platform": "github",
                                             "url": "https://github.com/o/r/blob/main/docs/T.md"})
        self.assertIsNone(err)
        self.assertIn("Templates is a core plugin", text)
        self.assertIn("/repos/o/r/contents/docs/T.md?ref=main", call.call_args.args[0])
        self.assertIn("Accept: application/vnd.github.raw", call.call_args.kwargs["headers"])

    def test_github_description_included(self):
        with mock.patch("radar.verify._curl_text", side_effect=[
                ("README body", 200, None),
                ('{"description": "repo description text"}', 200, None)]):
            text, status, err = source_text({"platform": "github",
                                             "url": "https://github.com/o/r"})
        self.assertIsNone(err)
        self.assertIn("repo description text", text)

    def test_verify_source_false(self):
        with mock.patch("radar.verify.source_text", return_value=("短", 200, None)):
            out = verify_source({"id": "A", "url": "https://example.com", "platform": "web",
                                 "quotes": ["不存在的句子"]})
        self.assertEqual(out["quote_verified"], "unknown")

    def test_verify_source_error(self):
        with mock.patch("radar.verify.source_text", return_value=(None, 500, "HTTP 500")):
            out = verify_source({"id": "A", "url": "https://example.com", "platform": "web",
                                 "quotes": ["q"]})
        self.assertEqual(out["quote_verified"], "unknown")
        self.assertIn("HTTP 500", out["quote_verify_error"])

    def test_verify_sources_skips_no_quote(self):
        out, warnings = verify_sources([{"id": "A", "url": "https://example.com", "quotes": []}])
        self.assertEqual(len(out), 1)
        self.assertEqual(warnings, [])


class TestSchemas(unittest.TestCase):
    def test_schema_files_load(self):
        for path in sorted((ROOT / "schemas").glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("$schema", data)
            self.assertIn("$id", data)


class TestAutomation(unittest.TestCase):
    def test_fail_on_change_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "base"
            subprocess.run([sys.executable, "-m", "radar", "run", "--pack", str(PACK),
                            "--seeds", str(SEEDS), "--title", "T", "--out", str(base)],
                           cwd=ROOT, check=True, capture_output=True, text=True)
            seed2 = Path(tmp) / "seeds2.json"
            data = json.loads(SEEDS.read_text(encoding="utf-8"))
            data["sources"] = [x for x in data["sources"] if x["id"] != "SRC-013"]
            seed2.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            out = Path(tmp) / "scan"
            proc = subprocess.run([sys.executable, "-m", "radar", "scan", "--pack", str(PACK),
                                   "--seeds", str(seed2), "--title", "T", "--out", str(out),
                                   "--base", str(base), "--fail-on-change"],
                                  cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 2)
            self.assertTrue((out / "changes.md").exists())


@unittest.skipUnless(os.name == "posix", "scan_all.sh 需要 POSIX shell；Windows 用 Git Bash 手动运行")
class TestScanAllScript(unittest.TestCase):
    def test_pointer_and_exit_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "packs").mkdir(); (root / "seeds").mkdir(); (root / "runs").mkdir()
            for name in ("weak-current", "video-kb", "pet-hospital"):
                (root / "packs" / name).mkdir()
                (root / "packs" / name / "pack.json").write_text("{}", encoding="utf-8")
                (root / "seeds" / f"{name}.json").write_text("{}", encoding="utf-8")
                (root / "runs" / f"{name}-demo").mkdir()
                (root / "runs" / f"{name}-demo" / "sentinel").write_text("x", encoding="utf-8")
            bin_dir = root / "bin"; bin_dir.mkdir()
            fake = bin_dir / "python3"
            fake.write_text('#!/usr/bin/env bash\ncase "$*" in *weak-current*) exit "${WEAK_RC:-0}";; *video-kb*) exit "${VIDEO_RC:-0}";; *) exit 0;; esac\n', encoding="utf-8")
            fake.chmod(0o755)
            env = {"PACK_ROOT": str(root/"packs"), "SEED_ROOT": str(root/"seeds"),
                   "BASE_ROOT": str(root/"runs"), "STAMP": "one",
                   "PATH": str(bin_dir) + ":" + str(Path("/usr/bin"))}
            env = dict(os.environ, **env)
            subprocess.run([str(ROOT/"scripts/scan_all.sh")], cwd=ROOT, env=env,
                           check=True, capture_output=True, text=True)
            self.assertIn("weak-current-scan-one", (root/"runs/weak-current-last.txt").read_text())
            self.assertTrue((root/"runs/weak-current-demo/sentinel").exists())
            self.assertEqual(len(list((root/"runs/weak-current-demo").iterdir())), 1)
            for name in ("weak-current", "video-kb", "pet-hospital"):
                (root / "runs" / f"{name}-scan-one").mkdir()
            # second run must use the first run as base
            log = root / "args.log"
            fake.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "' + str(log) + '"\ncase "$*" in *weak-current*) exit 0;; *video-kb*) exit 2;; *) exit 0;; esac\n', encoding="utf-8")
            fake.chmod(0o755)
            env["STAMP"] = "two"
            p = subprocess.run([str(ROOT/"scripts/scan_all.sh")], cwd=ROOT, env=env,
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 2)
            args = log.read_text()
            self.assertIn("--base " + str(root/"runs/weak-current-scan-one"), args)
            # failure must dominate change
            fake.write_text('#!/usr/bin/env bash\nexit "${WEAK_RC:-0}"\n', encoding="utf-8")
            fake.chmod(0o755)
            env["STAMP"] = "three"; env["WEAK_RC"] = "1"; env["VIDEO_RC"] = "2"
            p = subprocess.run([str(ROOT/"scripts/scan_all.sh")], cwd=ROOT, env=env,
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 1)


class TestAudit(unittest.TestCase):
    def test_ledger_audit(self):
        proc = subprocess.run([sys.executable, str(ROOT / "tools/audit_ledger.py"),
                               "--expect-strong", "5", "--expect-evidence", "20"],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_ledger_audit_missing_run_fails(self):
        proc = subprocess.run([sys.executable, str(ROOT / "tools/audit_ledger.py"),
                               "--run", "runs/does-not-exist"],
                              capture_output=True, text=True, timeout=30)
        self.assertNotEqual(proc.returncode, 0)


class TestDraft(unittest.TestCase):
    def test_draft_seeds_from_urls_dedup_and_validate(self):
        pack = load_pack(PACK)
        html = ("<html><head><title>弱电立项规范</title></head>"
                "<body><p>弱电项目立项与项目台账管理系统需要覆盖项目编码、立项审批与阶段跟踪的完整流程。</p>"
                "<p>Permission is hereby granted, free of charge, to any person obtaining a copy</p></body></html>")
        with mock.patch("radar.draft.fetch_text", return_value=(html, 200, None)):
            payload, warnings, skipped = draft_seeds_from_urls(
                pack,
                ["https://gitee.com/eywe-butler/eywe", "https://example.com/initiation-guide"],
                covers=["M02"],
                existing_seeds_path=SEEDS,
            )
        self.assertEqual(warnings, [])
        self.assertEqual(skipped, ["https://gitee.com/eywe-butler/eywe"])
        self.assertEqual(len(payload["sources"]), 1)
        s = payload["sources"][0]
        self.assertEqual(s["id"], "SRC-042")
        self.assertEqual(s["status"], "needs_review")
        self.assertEqual(s["quote_verified"], "unknown")
        self.assertEqual(s["license"], "MIT")
        self.assertEqual(s["license_status"], "clear")
        self.assertTrue(s["quotes"])
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "draft.json"
            p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            loaded = load_seeds(p, pack, strict=False)
            self.assertEqual(len(loaded), 1)


if __name__ == "__main__":
    unittest.main()
