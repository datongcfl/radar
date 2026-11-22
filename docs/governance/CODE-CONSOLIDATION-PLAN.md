# Radar Code Structure Consolidation Plan

> Status: code-structure audit and staged implementation plan  
> Baseline: `main@40c0528141b88c0a80ed25015b982ae44a8f8992`  
> Date: 2026-11-22  
> This is not authorization to perform a broad rewrite. Every implementation increment must remain independently testable and reviewable.

## 1. Executive finding

The current repository is not simply a collection of badly named files. It has evolved from one legacy Pack/Seeds coverage CLI into two related product paths plus a capability/parser layer. The main structural risk is that the two paths and their contracts are not yet explained and enforced as one coherent system.

The immediate remedy is not to move every file. First freeze the boundaries and add regression tests; then make small changes at the orchestration seams.

## 2. Current module map

| Area | Current modules | Responsibility |
|---|---|---|
| CLI / orchestration | `radar/cli.py`, `radar/__main__.py` | Commands, argument parsing, composition of providers, orchestration |
| Legacy domain | `model.py`, `coverage.py`, `claims.py`, `state.py`, `report.py`, `diff.py` | Pack/Seeds validation, legacy source merge, coverage and claim reports |
| Legacy source acquisition | `adapters.py`, `github_capability.py`, `gitee_capability.py`, `snowball.py`, `fetch.py`, `web.py`, `verify.py` | Provider calls, enrichment, quote verification |
| New discovery domain | `discovery.py`, `discovery_store.py` | Typed records, validation, immutable Evidence, Requirement revision and JSONL persistence |
| Repository inventory | `github_asset_inventory.py` | GitHub file candidate inventory at immutable commit/path/blob identity |
| Capability boundary | `capabilities.py` | Capability Protocol, context/result, explicit registry and failure states |
| Document parsing | `document_parser.py`, `pdf_parser.py`, `docx_parser.py`, `xlsx_parser.py`, `pptx_parser.py`, `xml_safety.py` | Format-specific fragments, native locators, XML safety |
| Test suite | `tests/test_*.py` | Unit and regression tests, currently flat at one directory level |

This map describes file ownership, not a claim that every capability is fully integrated into one end-to-end workflow.

## 3. Structural hotspots found

### H1. CLI is the composition root and a large orchestration surface

The CLI currently builds legacy commands, requirement-driven discovery, parser invocation and explicit capability registration. A composition root is a valid place to wire concrete capabilities, but domain orchestration and command-specific workflows should not grow indefinitely inside one module.

**Risk:** command behavior, provider wiring, storage, and business semantics become difficult to review independently.

**Target:** keep argument parsing and top-level composition in `cli.py`; move command handlers/orchestration into focused modules only after behavior tests exist.

### H2. Legacy adapters are wrapped by capabilities, but shared helpers cross module boundaries

`github_capability.py` and `gitee_capability.py` wrap existing collectors in `adapters.py`. `snowball.py` also imports private helpers/constants from `adapters.py`.

**Risk:** private helper coupling makes the adapter module a de facto shared transport library without a declared contract.

**Target:** decide whether a small provider transport module is justified; if extracted, keep mapping/identity logic in provider modules and avoid premature generic frameworks.

### H3. Legacy and new domain models coexist

The legacy model uses Pack/Seeds source dictionaries and claims. The new discovery model defines typed Workspace, Requirement, Source, Asset, Evidence, Relationship, Assessment and Run records.

**Risk:** the same words (especially Source, evidence, status, coverage) may be used with different semantics.

**Target:** explicit compatibility/mapping adapters; no silent conversion, no shared field mutation, no assumption that legacy quote rows are already Evidence.

### H4. Repository inventory and document parsers are not one ingestion pipeline

The GitHub inventory emits candidate descriptors with `content_fetch_status=not_fetched` and `evidence_promoted=false`. Parser capabilities emit `document_fragment` records.

**Risk:** users or downstream code may interpret a listed file or parsed fragment as requirement evidence.

**Target:** add an explicit, separately scoped ingestion service: fetch immutable bytes → verify blob/hash → format/safety validation → parser → locator validation → Evidence mapping → relationship/assessment update.

### H5. Discovery domain module contains both core records and ledger-specific record families

The current `discovery.py` owns common record validation and includes ledger effect/manifest/aggregation-rule types.

**Risk:** specialized ledger semantics may enlarge the general discovery core and make unrelated changes harder to isolate.

**Target:** retain shared envelope/validation primitives in Core; extract domain-specific ledger validation only when the ledger module contract and ownership are settled. Do not split files just for aesthetics.

### H6. Tests are flat and integration boundaries are not obvious

Tests cover capabilities, CLI lazy imports, Discovery, storage, parsers and legacy behavior, but are all in a single tests directory.

**Risk:** it is harder to distinguish contract, unit, integration, security and end-to-end coverage; however, moving tests now can create churn without improving confidence.

**Target:** first tag/organize tests by naming and CI jobs; physically move them only if discovery/import behavior remains stable.

## 4. Proposed implementation sequence

| Increment | Scope | Files likely involved | Acceptance |
|---|---|---|---|
| G3-0 | Baseline contract map and test inventory | `docs/architecture/ARCHITECTURE-OVERVIEW.md`, tests | Every module has an owner and each critical invariant has a test reference |
| G3-1 | Characterization tests for legacy/new boundaries | `tests/test_radar.py`, `tests/test_discovery.py`, `tests/test_discovery_store.py`, new focused tests | Existing CLI outputs, merge rules, evidence immutability and partial failures are pinned before refactor |
| G3-2 | CLI orchestration extraction | `radar/cli.py`, new command modules | CLI flags/output/exit codes unchanged; lazy import and optional dependency tests pass |
| G3-3 | Provider transport boundary | `radar/adapters.py`, `radar/snowball.py`, provider capabilities | No private cross-module imports; provider tests and offline tests pass |
| G3-4 | Explicit inventory-to-ingestion boundary | `github_asset_inventory.py`, new ingestion module, parser modules, discovery store | Blob/content hashes and locators validated; candidate never auto-promotes to Evidence |
| G3-5 | Domain specialization boundary | `discovery.py`, ledger-specific modules/tests if owner-approved | Core domain validator remains stable; ledger-specific invariants are isolated without schema drift |
| G3-6 | Test layout/CI alignment | `tests/`, workflow | Contract/unit/integration/security suites are independently runnable and full suite remains green |

## 5. Refactor rules

1. No broad package rename or directory reshuffle.
2. No behavior change bundled with a pure file move.
3. Before extracting a module, add characterization tests for its existing behavior.
4. Each PR should have one architectural purpose and a small file surface.
5. Preserve Python 3.9 Core compatibility.
6. Preserve optional dependency laziness and the no-optional-dependency CLI path.
7. Do not add runtime dependencies without the component-selection process and owner approval.
8. Do not remove old Pack/Seeds commands or change legacy schemas as a side effect.
9. Keep the Registry explicit; do not introduce dynamic plugin discovery or arbitrary imports.
10. Every failure/partial state remains explicit; never turn missing capability into successful empty output.

## 6. Blockers before production refactoring

- The supplied `radar-delivery-07c6ec7b.zip` snapshot has not been retrieved into a local execution environment in this session. Its checksum manifest and 13 review tests have therefore not been independently reproduced.
- GitHub Actions reports the current main merge commit test workflow as successful, but that does not substitute for local reproduction of the separate review snapshot.
- Several business-semantic decisions in the branch-fix handoff remain owner decisions: cross-source same-ID vs mirror deduplication, Legacy locator schema, content-version reference, ZIP limits, ledger identity/kind, ledger schema ownership and PR-1a scope.
- No local test execution has been performed for this audit increment. Do not label a source-level inspection as a reproduced test result.

## 7. G3 exit criteria

- [x] Map the current modules to architectural responsibilities.
- [x] Identify structural hotspots and distinguish architectural risk from cosmetic cleanup.
- [x] Define a staged, test-first refactor sequence.
- [ ] Obtain and verify the exact review snapshot and reproduce its test suite.
- [ ] Add characterization tests before refactoring.
- [ ] Execute at least one bounded code-structure PR with CI passing.
- [ ] Verify the new inventory-to-ingestion contract without promoting candidates to Evidence automatically.

G3 remains **audit/planning complete, implementation not yet complete**. This is intentional: code movement without a reproducible local baseline would make the repository less trustworthy, not cleaner.
