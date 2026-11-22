# Radar Repository Consolidation — G1 Issue Register

> Status: audit baseline, not a closure declaration  
> Baseline branch: `main`  
> Baseline commit: `40c0528141b88c0a80ed25015b982ae44a8f8992`  
> Audit date: 2026-11-22  
> Scope: recovered historical issues R01–R10 and D01–D10, current GitHub Issues, current source-tree evidence, and known gaps in historical records.

## 1. Purpose and rules

This register is the single working index for repository-consolidation findings. It does not replace GitHub Issues, tests, or architecture contracts.

Status meanings:

- **Addressed (verified):** current main contains the implementation and a corresponding test or explicit contract.
- **Partially addressed:** some capability exists, but the original end-to-end requirement is not met.
- **Open:** current main still lacks the required capability or control.
- **Needs verification:** available repository evidence is insufficient to make a reliable closure decision.
- **Historical record missing:** the original finding text could not be recovered; do not infer or fabricate it.

A feature's existence is not proof that its quality, completeness, or end-to-end semantics satisfy the original finding. In particular, candidate Asset inventory is not Evidence, and parser fragments are not automatically Evidence or Assessment.

## 2. Current repository baseline

- `main`: `40c0528141b88c0a80ed25015b982ae44a8f8992` (merge commit for PR #43).
- Open PRs: 0 at audit time.
- Open Issues: #20, #11, #1, #2.
- Visible branches: 19.
- Protected main: enabled; changes must be delivered through PRs.
- The current main tree contains Capability Registry, legacy Seeds/Claims flow, Discovery data model and store, GitHub discovery, repository asset inventory, PDF/DOCX/XLSX/PPTX parsers, parser CLI integration, and XML safety tests.

## 3. Recovered historical issue register

| ID | Recovered finding | Current-main evidence | Status | Next action |
|---|---|---|---|---|
| R01 | Repository search is metadata-heavy; file/document/code discovery is insufficient. | GitHub Repository Asset Inventory now enumerates candidate files at immutable commit + path + blob SHA. It does not fetch file bodies or create Evidence. | Partially addressed | Define and verify the fetch → hash → parse → locator → Evidence continuation. |
| R02 | Issues/PR automatic discovery is missing. | Discovery data-model document describes Issue/PR search; current Asset Inventory explicitly excludes Issue/PR discussions. Current main capability set must be checked for end-to-end execution and tests. | Needs verification | Trace the current GitHub discovery implementation and tests; record whether Issue/PR discovery is executable, not merely specified. |
| R03 | PDF/Office document processing is insufficient. | Current main contains optional PDF, DOCX, XLSX and PPTX parser modules, parser CLI, and XML safety tests. | Partially addressed | Verify format coverage, locator fidelity, security limits, optional-dependency isolation, and real-document regression corpus. OCR/layout fidelity remains out of scope unless explicitly implemented. |
| R04 | Document/code asset value and quality evaluation is insufficient. | Candidate classification and parser fragments exist; no verified end-to-end quality assessment contract has been established in this audit. | Needs verification | Separate existence, content quality, freshness, authority, maintainability, and reuse/license dimensions. |
| R05 | Coverage is not equivalent to requirement completeness. | `docs/DISCOVERY-DATA-MODEL.md` defines Requirement, Evidence and Assessment separately, including per-criterion results and `no_evidence != not_implemented`. | Partially addressed | Verify current runtime, schemas, CLI and tests implement the complete requirement-to-assessment contract. |
| R06 | Business-process validation is missing. | Discovery data model includes acceptance criteria and Assessment statuses; no end-to-end business-process validation proof is recorded here. | Needs verification | Specify process, states, preconditions, postconditions, exceptions and evidence-backed validation tests. |
| R07 | Cross-module business relationships are insufficient. | Discovery data model defines typed Relationship objects and relation types; current runtime adoption and graph traversal remain to be verified. | Partially addressed | Verify persistence, validation, provenance and query/use of relationships in actual assessment. |
| R08 | Standards version management is insufficient. | Discovery data model has versioned Pack references and versioned Requirements; no confirmed standard-document version lifecycle has been demonstrated. | Needs verification | Define authority, edition/effective dates, supersession, jurisdiction and historical applicability. |
| R09 | Evidence trust and license status are conflated. | Current legacy model separates access status, license status and quote verification; Claims confidence applies caps for unverified and proprietary references. | Partially addressed | Verify the new Evidence verification lifecycle and ensure access, license, source confirmation and implementation verification remain independent. |
| R10 | Development/delivery traceability is incomplete. | Capability Registry and PR/CI workflow exist; no single verified mapping from Requirement → Asset/Evidence → Assessment → Issue/PR → tests → release has been demonstrated. | Partially addressed | Define the traceability contract and a minimal end-to-end fixture. |

## 4. Recovered detailed findings

| ID | Finding | Current status | Notes |
|---|---|---|---|
| D01 | Chinese/English keyword coverage is insufficient. | Needs verification | Inspect current query construction and multilingual fixtures. |
| D02 | Synonyms, aliases and terminology mapping are insufficient. | Partially addressed | Requirement model specifies canonical terms, aliases and languages; verify implementation and retrieval behavior. |
| D03 | `infer_covers` does not adequately identify real document/code asset coverage. | Needs verification | Legacy Pack keyword inference and new Requirement-to-Asset discovery are distinct mechanisms; do not conflate them. |
| D04 | `query_templates` do not sufficiently drive search. | Needs verification | Verify query-template use in the actual discovery path and test it. |
| D05 | GitHub discovery is primarily repository metadata. | Partially addressed | Code/Issue/PR discovery is described in the Discovery contract; repository Asset Inventory adds file candidates. Verify execution and evidence quality. |
| D06 | File-level asset discovery is missing. | Partially addressed | Repository Asset Inventory exists, but is GitHub-only and candidate-only; no universal source or content ingestion is implied. |
| D07 | Requirement-to-code mapping is insufficient. | Partially addressed | Requirement/Pack-unit mappings and candidate `mentions` are specified; this is not equivalent to verified `implements` or `supports`. |
| D08 | Completeness and test evaluation are insufficient. | Needs verification | Parser and unit tests exist; verify requirement-criterion coverage, test-result provenance and negative/exception paths. |
| D09 | Issue/PR association chain is incomplete. | Needs verification | Verify Issue/PR Assets, PR diff Evidence, review threads, CI checks and fixes relationships. |
| D10 | Result count, keyword bias and duplicate-ID risks exist. | Needs verification | Re-test source identity, deduplication, pagination, query limits, partial-result semantics and deterministic IDs. |

## 5. Current open GitHub Issues

| Issue | Subject | Relationship to register | State |
|---|---|---|---|
| [#20](https://github.com/datongcfl/radar/issues/20) | General source foundation + industry vertical source system | Supports R01/R04 and industry-pack source expansion | Open |
| [#11](https://github.com/datongcfl/radar/issues/11) | Evidence ledger trust: 4 P0 + 9 P1 | Supports R09, D10 and data-integrity invariants | Open |
| [#1](https://github.com/datongcfl/radar/issues/1) | Early review gaps and dead links | Historical input for R10 and documentation governance | Open |
| [#2](https://github.com/datongcfl/radar/issues/2) | Seed entry cost and metadata automation | Supports R10 and ingestion ergonomics | Open |

Issue descriptions are historical reports, not proof that every listed defect still reproduces on the current main. Reproduction against `40c0528141b88c0a80ed25015b982ae44a8f8992` is required before implementation or closure.

## 6. Historical record gap

The prior conversation referred to a larger R01–R92 register. Only R01–R10 and D01–D10 could be reconstructed from currently available context. The exact text, evidence and status of R11–R92 are **not available** in this audit baseline.

Do not:
- invent titles or descriptions for R11–R92;
- renumber D01–D10 to fill the gap;
- mark missing items as resolved;
- assume the four currently open Issues represent the entire historical backlog.

Recovery sources for the missing records should be checked in this order: prior conversation exports/files, repository issue/PR history, archived review artifacts, then owner clarification.

## 7. Cross-cutting invariants to preserve

1. Asset discovery candidates are not Evidence.
2. Parser output is not automatically verified Evidence.
3. Evidence records preserve immutable source version and native locator.
4. Requirement mapping `mentions` does not mean `supports` or `implements`.
5. `no_evidence` does not mean `not_implemented`.
6. Access status, license status, quote/source verification and implementation verification are independent.
7. Partial discovery/parser failure must remain explicit; never silently report complete success.
8. Legacy CLI, Pack/Seeds schemas and existing parser/XML-safety capabilities must not regress.

## 8. Exit criteria for G1

- [x] Record the current main SHA, open PR/Issue counts and visible branch count.
- [x] Recover R01–R10 and D01–D10 without fabricating missing records.
- [x] Map the four open Issues to the historical register.
- [x] Distinguish partially addressed from verified closed.
- [ ] Recover R11–R92 from authoritative historical sources.
- [ ] Reproduce the relevant P0/P1 and D-series invariants against current main.
- [ ] Link every finding to an owner, issue, implementation PR and regression test.

G1 remains **partially complete** until the missing historical records and current-main reproductions are resolved.
