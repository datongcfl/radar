# Radar Branch Inventory and Cleanup Decision Register

> Audit date: 2026-11-22  
> Comparison base: `main@40c0528141b88c0a80ed25015b982ae44a8f8992`  
> Branch count: 23 visible branches at audit time  
> Policy: inventory first; do not delete or force-update branches as part of this audit.

## 1. Summary

The branch count grew from 19 to 24 during this consolidation work because five short-lived documentation branches were created for G1–G5. At the time the initial inventory list was captured, the G5 report branch had not yet been created; it is included below as a fifth consolidation branch. Each targets main through a separate draft PR.

The repository has three distinct branch populations:

1. **Current mainline:** `main`.
2. **Long-lived divergent source branches:** `feat/requirement-driven-discovery` and `chore/m15-architecture-realignment`. These contain large unique histories and are not safe merge candidates.
3. **Merged/obsolete or review-only branches:** most M15/M16 branches have zero commits ahead of main and are only behind; they are candidates for archival/deletion after checking PR provenance and whether anyone still uses them.
4. **Current consolidation branches:** four new docs branches, all ahead-only and each tied to an open draft PR.

## 2. Current branch inventory

Ahead/behind values below compare each branch tip against current main. For branches not re-compared during this pass, values are from the immediately preceding audit against the same unchanged main SHA `40c0528141b88c0a80ed25015b982ae44a8f8992`.

| Branch | Ahead | Behind | Classification | Recommendation |
|---|---:|---:|---|---|
| `main` | 0 | 0 | Active baseline | Keep |
| `feat/requirement-driven-discovery` | 197 | 57 | Diverged historical feature line | Archive as source snapshot; do not merge wholesale; preserve until PR-0…PR-6 replay and owner decisions finish |
| `chore/m15-architecture-realignment` | 200 | 57 | Diverged architecture line | Archive as source snapshot; extract only individually reviewed changes; do not merge wholesale |
| `arena/3efab84a-radar` | 2 | 0 | Review/delivery artifact branch | Keep temporarily until delivery snapshot and checksum manifest are verified; then archive or delete |
| `docs/m15-office-parser-selection` | 0 | 15 | Behind-only historical docs branch | Delete candidate after confirming PR provenance and no external workflow references |
| `feat/m15-capability-registry` | 0 | 53 | Behind-only merged feature branch | Delete candidate after PR provenance check |
| `feat/m15-cli-lazy-capabilities` | 0 | 50 | Behind-only merged feature branch | Delete candidate after PR provenance check |
| `feat/m15-dependency-governance` | 0 | 51 | Behind-only merged feature branch | Delete candidate after PR provenance check |
| `feat/m15-discovery-domain-core` | 0 | 55 | Behind-only merged feature branch | Delete candidate after PR provenance check |
| `feat/m15-document-parser-capability` | 0 | 39 | Behind-only merged feature branch | Delete candidate after PR provenance check |
| `feat/m15-docx-parser-capability` | 0 | 18 | Behind-only merged feature branch | Delete candidate after PR provenance check |
| `feat/m15-gitee-source-capability` | 0 | 51 | Behind-only merged feature branch | Delete candidate after PR provenance check |
| `feat/m15-github-source-capability` | 0 | 52 | Behind-only merged feature branch | Delete candidate after PR provenance check |
| `feat/m15-parser-cli-integration` | 0 | 4 | Behind-only merged feature branch | Delete candidate after PR provenance check |
| `feat/m15-pdf-parser-capability` | 0 | 27 | Behind-only merged feature branch | Delete candidate after PR provenance check |
| `feat/m15-pptx-parser-capability` | 0 | 6 | Behind-only merged feature branch | Delete candidate after PR provenance check |
| `feat/m15-xlsx-parser-capability` | 0 | 11 | Behind-only merged feature branch | Delete candidate after PR provenance check |
| `feat/m16-github-asset-inventory` | 0 | 1 | Behind-only merged feature branch | Delete candidate after PR provenance check |
| `fix/agents-authorized-fix-branch` | 0 | 60 | Behind-only repair branch | Delete candidate only after confirming no unmerged review artifact or handoff depends on it |
| `docs/repository-consolidation-g1` | 3 | 0 | Active consolidation PR branch | Keep until PR #44 disposition |
| `docs/repository-consolidation-g2` | 2 | 0 | Active consolidation PR branch | Keep until PR #45 disposition |
| `docs/repository-consolidation-g3-plan` | 2 | 0 | Active consolidation PR branch | Keep until PR #46 disposition |
| `docs/repository-consolidation-g4` | 5 | 0 | Active consolidation PR branch | Keep until PR #47 disposition |
| `docs/repository-consolidation-g5` | 1 | 0 | Active consolidation PR branch | Keep until PR #48 disposition |

## 3. Divergent branches: strict handling

### `feat/requirement-driven-discovery`

- 197 commits ahead and 57 behind main.
- This branch is the source snapshot referenced by the branch-fix handoff.
- It contains valuable review material and code that must be replayed in bounded increments.
- Do not merge, rebase wholesale or delete it.
- The exact source snapshot ZIP has not been locally verified in this session. Keep the branch until the archive is independently checksummed and the handoff is complete.

### `chore/m15-architecture-realignment`

- 200 commits ahead and 57 behind main.
- It is a long-running architecture line with a different base history.
- Do not merge the branch as a whole.
- Compare each unique capability/document independently against main; accept only small, test-backed PRs.

## 4. Behind-only branches

For a branch with zero commits ahead of main, the branch tip is already contained in main according to the GitHub compare result. That is a strong deletion signal, but it is not the only required check.

Before deletion, verify:

1. No open PR points to the branch.
2. The branch was merged or its unique work was intentionally superseded.
3. No CI workflow, release script, handoff document or external automation references the branch name.
4. No one is using the branch as a delivery or review snapshot.
5. The branch name and head SHA are recorded in this register or an archived manifest.

Only after all five checks pass should an owner approve deletion. A branch being behind is not, by itself, proof that it is safe to delete.

## 5. Consolidation PR branches

The five branches created during this work are intentionally separate:

- [PR #44 — G1 issue register](https://github.com/datongcfl/radar/pull/44)
- [PR #45 — G2 architecture overview](https://github.com/datongcfl/radar/pull/45)
- [PR #46 — G3 code consolidation plan](https://github.com/datongcfl/radar/pull/46)
- [PR #47 — G4 documentation and CI alignment](https://github.com/datongcfl/radar/pull/47)
- [PR #48 — G5 branch cleanup register](https://github.com/datongcfl/radar/pull/48)

They must not be deleted until each PR is reviewed and either merged or explicitly closed. They are not production feature branches.

## 6. Recommended cleanup order

1. Preserve `feat/requirement-driven-discovery` and `chore/m15-architecture-realignment` as protected historical sources.
2. Preserve `arena/3efab84a-radar` until the ZIP snapshot checksum and review tests are verified.
3. Review and merge/close the four consolidation PRs.
4. Generate a branch-to-PR/commit provenance manifest for all behind-only branches.
5. Ask the owner to approve a single batch deletion of branches that pass all five safety checks.
6. Re-run branch inventory and compare against main after cleanup.

## 7. G5 exit criteria

- [x] Enumerate all 23 visible branches.
- [x] Identify the two divergent long-lived branches and prohibit wholesale merge.
- [x] Separate current consolidation branches from historical feature branches.
- [x] Identify behind-only branches as deletion candidates, not automatic deletions.
- [ ] Verify PR provenance and automation references for each behind-only branch.
- [ ] Verify and archive the delivery snapshot and review artifacts.
- [ ] Obtain owner approval before deleting any branch.
- [ ] Re-run branch inventory after approved cleanup.

G5 is **audit complete, cleanup pending owner review**. No branch has been deleted or force-updated by this audit.
