#!/usr/bin/env python3
"""Run review-only contract tests against a feature-branch snapshot.

The current checkout is main. This runner puts the requested snapshot first on
sys.path so the tests exercise the branch implementation without checking the
branch out into the repository.
"""
from __future__ import annotations

import argparse
import os
import sys
import unittest
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--branch-root",
        default=os.environ.get("RADAR_BRANCH_ROOT", "/tmp/rdd"),
        help="path to a checkout/tarball of feat/requirement-driven-discovery",
    )
    args = parser.parse_args()

    branch_root = Path(args.branch_root).expanduser().resolve()
    if not (branch_root / "radar" / "business_invariants.py").is_file():
        parser.error(
            "branch root does not contain radar/business_invariants.py: %s" % branch_root
        )

    # Branch first, then the review test directory itself.
    sys.path.insert(0, str(branch_root))
    sys.path.insert(0, str(Path(__file__).resolve().parent))

    suite = unittest.defaultTestLoader.discover(
        str(Path(__file__).resolve().parent), pattern="test_*.py"
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
