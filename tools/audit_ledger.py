#!/usr/bin/env python3
"""Audit ledger trust: wide covers, short quotes, and strong support."""
import json
import sys
from collections import defaultdict
from pathlib import Path

import argparse
ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--pack", default="packs/weak-current/pack.json")
ap.add_argument("--seeds", default="seeds/weak-current.json")
ap.add_argument("--run", default="runs/weak-current-demo")
ap.add_argument("--expect-strong", type=int, default=None)
ap.add_argument("--expect-evidence", type=int, default=None)
args = ap.parse_args()
pack = json.loads((ROOT / args.pack).read_text(encoding="utf-8"))
seeds = json.loads((ROOT / args.seeds).read_text(encoding="utf-8"))["sources"]
units = {x["id"]: x["name"] for x in pack["modules"] + pack["subsystems"]}
support = defaultdict(list)
for s in seeds:
    for cid in s.get("covers", []):
        support[cid].append(s)

wide = [s for s in seeds if len(s.get("covers", [])) >= 5]
wide_only = [uid for uid in units if support[uid] and all(len(s["covers"]) >= 5 for s in support[uid])]
short = [s for s in seeds if any(0 < len(q) < 40 for q in (s.get("quotes") or []))]
no_quote = [s for s in seeds if not (s.get("quotes") or [])]
bad_qv = [s for s in seeds if s.get("quote_verified", "unknown") not in ("true", "false", "unknown")]
bad_by = [s for s in seeds if s.get("quote_verified_by") not in (None, "", "web", "human")]
print("sources=%d units=%d" % (len(seeds), len(units)))
print("wide_covers>=5: %s" % ([s["id"] for s in wide] or "none"))
print("units_only_wide: %s" % (wide_only or "none"))
print("short_quotes<40: %s" % ([s["id"] for s in short] or "none"))
print("no_quote (mention-ok): %s" % ([s["id"] for s in no_quote] or "none"))
print("bad_quote_verified: %s" % ([s["id"] for s in bad_qv] or "none"))
print("bad_quote_verified_by: %s" % ([s["id"] for s in bad_by] or "none"))

state_path = ROOT / args.run / "state.json"
cov_path = ROOT / args.run / "coverage.json"
if state_path.exists():
    state = json.loads(state_path.read_text(encoding="utf-8"))
    import hashlib
    seed_hash = hashlib.sha256((ROOT / args.seeds).read_bytes()).hexdigest()
    pack_hash = hashlib.sha256((ROOT / args.pack).read_bytes()).hexdigest()
    hash_ok = state.get("seeds_sha256") == seed_hash and state.get("pack_sha256") == pack_hash
    print("state_hashes: %s" % ("OK" if hash_ok else "MISMATCH"))
else:
    hash_ok = False
    print("state_hashes: MISSING (%s)" % state_path)

summary_ok = True
if cov_path.exists():
    summary = json.loads(cov_path.read_text(encoding="utf-8")).get("summary", {})
    print("coverage_summary: %s" % summary)
    if args.expect_strong is not None and summary.get("strong") != args.expect_strong:
        summary_ok = False
        print("expect_strong mismatch: got %s expected %s" % (summary.get("strong"), args.expect_strong))
    if args.expect_evidence is not None and summary.get("evidence") != args.expect_evidence:
        summary_ok = False
        print("expect_evidence mismatch: got %s expected %s" % (summary.get("evidence"), args.expect_evidence))
elif args.expect_strong is not None or args.expect_evidence is not None:
    summary_ok = False
    print("coverage_summary: MISSING (%s)" % cov_path)

if wide or wide_only or short or bad_qv or bad_by or not hash_ok or not summary_ok:
    sys.exit(1)
print("audit: PASS")
