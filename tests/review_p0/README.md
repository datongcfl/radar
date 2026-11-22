# Review-only P0 contract tests

This directory is **not** part of the normal test discovery. It is a failing-test
skeleton for the findings in `docs/reviews/2026-11-22-branch-review.md`.

It is deliberately kept out of `tests/test_*.py` so that the current `main`
suite stays green while the feature branch has not been replayed. Run it against
a branch snapshot:

```bash
python3 tests/review_p0/run.py --branch-root /tmp/rdd
```

Expected result: failures (or errors) for the un-fixed P0/P1 behavior. A green
run means the contract is now satisfied. Do not move these tests into `tests/`
until the corresponding production change is in the same PR.

Design rules:

- tests assert **desired** behavior, not current behavior;
- each P0 has at least one negative case;
- no network, no third-party dependency;
- no production code is imported from the review-only directory until the
  branch modules are on `sys.path` via `run.py`.
