# Radar Repository Consolidation — G1–G6 Status and Acceptance Report

> Audit date: 2026-11-22  
> Main baseline: `40c0528141b88c0a80ed25015b982ae44a8f8992`  
> Status: baseline validation completed; overall consolidation acceptance remains open  
> This report records facts and blockers. It does not declare the repository fully clean or the end-to-end product complete.

## 1. Executive result

The G1–G6 consolidation sequence has been carried through its first reviewable pass. Five documentation/governance PRs have been prepared; no changes have been written to main, no PR has been merged, no historical branch has been deleted, and no runtime dependency or schema version has been changed.

The audit surfaced one important architecture correction: current main contains the Discovery domain records, JSON Schema and JSONL storage primitives, but the CLI does **not** expose a `discover` command. Therefore the end-to-end Requirement → Source/Asset → Evidence → Assessment workflow is not yet complete.

The repository is better documented and its cleanup plan is explicit, but it is not yet accurate to call the repository fully consolidated.

## 2. Phase status

| Phase | Deliverable | Current status | Remaining acceptance work |
|---|---|---|---|
| G1 — Issue register | [PR #44](https://github.com/datongcfl/radar/pull/44) | Draft register for R01–R10, D01–D10 and four open Issues | Recover R11–R92; reproduce historical findings against current main; link each item to test/PR/owner |
| G2 — Architecture blueprint | [PR #45](https://github.com/datongcfl/radar/pull/45) | Draft current-state/target-state architecture overview; explicitly states no discover CLI | Runtime import/flow audit; owner decisions; verify domain/schema/store alignment |
| G3 — Code convergence | [PR #46](https://github.com/datongcfl/radar/pull/46) | Structural audit and staged test-first refactor plan | Obtain review ZIP; reproduce 13 review tests; add characterization tests; execute bounded production-code refactor |
| G4 — Docs and CI governance | [PR #47](https://github.com/datongcfl/radar/pull/47) | README, Roadmap, component-selection status and stale push-branch triggers updated in draft | Owner review; merge in dependency-safe order; verify links after merge |
| G5 — Branch cleanup | [PR #48](https://github.com/datongcfl/radar/pull/48) | Branch inventory and safe deletion rules prepared; no branch deleted | Verify PR provenance/automation references; archive source artifacts; owner approves deletion batch |
| G6 — Acceptance | This report | Current main CI and PR checks reviewed | Final acceptance requires merged changes, code workflow completion, branch disposition and post-merge validation |

## 3. CI validation evidence

### 3.1 Main baseline

GitHub Actions run for main commit `40c0528141b88c0a80ed25015b982ae44a8f8992` completed successfully on 2026-11-22.

### 3.2 Consolidation PR checks

For the recorded head commits:

| PR | Checks | Result |
|---|---:|---|
| #44 | 12 | 12/12 success |
| #45 | 12 | 12/12 success |
| #46 | 12 | 12/12 success |
| #47 | 12 | 12/12 success |
| #48 | 12 | Re-run triggered after final inventory edit; result must be refreshed before merge |

The 12 checks include core test jobs and optional PDF, DOCX, XLSX and PPTX parser jobs across the configured Python matrix. No optional parser job was removed.

CI success proves the current workflow passed for these documentation/CI branches. It does **not** prove the unimplemented Discovery orchestration or the separate review ZIP tests.

## 4. Confirmed repository facts

1. Main baseline remains `40c0528141b88c0a80ed25015b982ae44a8f8992` throughout this pass.
2. The current CLI exposes `run`, `scan`, `claims`, `validate`, `parse` and `diff`; it does not expose `discover`.
3. Discovery domain records, validation, JSON Schema and JSONL store primitives exist.
4. GitHub Repository Asset Inventory returns candidate descriptors and explicitly does not fetch content or promote Evidence.
5. Text/PDF/DOCX/XLSX/PPTX parser capabilities exist; parser fragments are not automatically Discovery Evidence.
6. `pyproject.toml` declares Python >=3.9 and no default runtime dependencies. Optional parser dependencies are managed through separate hash-pinned requirement files and CI jobs.
7. The latest main workflow is green; the documentation-only consolidation branches #44–#47 also passed all 12 CI checks at the inspected head commits.
8. The branch inventory contains long-lived divergent lines that must not be merged wholesale.

## 5. Validation not performed

The delivery archive `radar-delivery-07c6ec7b.zip` has not been retrieved into a local execution environment in this session. Therefore:

- the 161-entry SHA-256 manifest has not been verified;
- the archived source tree has not been independently checked out;
- `python3 tests/review_p0/run.py --branch-root /tmp/rdd` has not been executed;
- the 13 reported review failures have not been reproduced locally.

Do not report these tests as passed or failed in this session. The correct status is **not run / not independently reproduced**.

## 6. Blocking items before declaring the repository clean

### Blocker A — Discovery workflow gap

Implement and test a real `radar discover` workflow. It must connect Requirement versions, Pack mappings, Source/Asset discovery, immutable content ingestion, parser fragments, locator-bound Evidence, Relationships, Assessment criteria and DiscoveryRun history.

### Blocker B — Evidence ingestion gap

Connect candidate inventory to fetch/hash/format validation/parser execution and explicit fragment-to-Evidence mapping. Preserve immutable source version, blob/content hash and native locator. Never auto-promote candidates or fragments.

### Blocker C — Historical defect verification

Recover R11–R92 from authoritative history and reproduce R01–R10 / D01–D10 against the current mainline. Historical reports must not be treated as current bugs without reproduction, and missing records must not be fabricated.

### Blocker D — Review snapshot verification

Obtain the exact delivery ZIP, verify every manifest entry, run the review harness and then follow the approved PR-0…PR-6 short-branch replay process. Keep the unresolved business-semantic decisions as owner gates.

### Blocker E — Branch cleanup

Do not delete behind-only branches until their PR provenance and automation references are checked. Preserve the two divergent long-lived branches and the review snapshot until their unique value has been extracted and archived. Branch deletion requires owner approval.

### Blocker F — Merge and post-merge verification

The five consolidation PRs are drafts. The owner must review and decide their merge order. After merge, rerun the full main workflow, verify documentation links, refresh the branch inventory and confirm main contains the accepted files.

## 7. Non-regression invariants

- No direct main writes; all changes through PRs.
- No automatic PR merges or self-approval.
- No wholesale merge of the two divergent feature histories.
- No new runtime dependencies without component review and owner approval.
- Preserve Python 3.9 Core compatibility and optional parser isolation.
- Preserve existing parser, XML safety and optional parser CI coverage.
- Do not change `schema_version`, LICENSE or release tags as part of cleanup.
- Asset candidates, parser fragments, Evidence and Assessment remain distinct states.

## 8. Final acceptance decision

**G6 baseline validation: passed for the inspected main and completed PR checks.**

**Overall G1–G6 repository consolidation: not yet accepted.**

The remaining work is substantive, not cosmetic: complete the executable Discovery workflow, close the ingestion gap, recover and reproduce historical issues, verify the delivery archive, and complete owner-approved branch cleanup. Until those are done and the PRs are merged with post-merge CI green, the repository should be described as **consolidation in progress**, not clean and complete.
