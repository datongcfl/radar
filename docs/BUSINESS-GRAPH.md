# Pack-driven Business Graph (M11)

## Purpose and boundary

The business graph is a deterministic, derived projection. It does not add a ninth core domain object and does not turn business concepts such as Purchase Order into generic Assets. The eight existing discovery record types remain unchanged.

An industry Pack declares business entities, process transitions, and exception scenarios in a separate, data-only `business-model.json`. Radar projects those declarations together with Requirement, Asset, and Evidence records. No Python expressions, plugins, or executable rules are accepted in the model.

## Schema v1

- `entities`: stable ID, bilingual aliases, key fields, evidence terms, and risk notes.
- `processes.transitions`: from/to entity IDs, business condition, and required evidence.
- `exceptions`: aliases, evidence terms, related entities, expected evidence, and risk.

The sidecar model explicitly binds to Pack name and Pack version. Its own version and SHA-256 are included in every projection. A model change therefore creates a distinguishable projection even when the base Pack file is unchanged.

## Graph semantics

Node kinds: `business_entity`, `business_process`, `business_exception`, `asset`, `evidence`, `requirement`, and `acceptance_criterion`.

Edges include:

- `declared_transition`: a Pack-defined process relationship, status `declared_not_verified`.
- `affects_entity`: an exception-to-entity declaration, status `declared_not_verified`.
- `candidate_mention` / `candidate_exception_mention`: lexical candidate links from Evidence, status `candidate_only`; each stores matched terms, evidence ID, Asset ID, and exact locator.
- `has_step`: connects a declared process to its ordered business entities.
- `located_in`: connects an Evidence node to its source Asset.
- `has_criterion`: connects a Requirement to its acceptance criterion.
- `candidate_requires`: lexical candidate mapping from an acceptance criterion to a business entity; status `candidate_only`.
- `candidate_requires_exception`: lexical candidate mapping from a criterion to an exception scenario; status `candidate_only`.
- `candidate_evidence_for`: candidate Evidence links for each acceptance criterion, with exact Evidence ID, Asset ID, locator, and matched entity/exception IDs; never marks a criterion supported.
- `candidate_transition`: a candidate cross-file transition when a typed Asset relationship connects evidence-bearing assets matching the declared transition endpoints; status `candidate_only`.

A term match never creates `implements` or `supports`. Declared transitions have no evidence IDs and do not prove implementation. No match means only that the current evidence set did not match the declared terms; it does not mean the feature is absent. Cross-file links require an existing typed Asset-to-Asset relationship plus separate endpoint Evidence mentions; the result remains a candidate, not a verified business transition. Evidence verification status is copied from its source record, not upgraded by graph projection.

## CLI

After a Discover run, project the stored records:

```bash
python -m radar business-graph \
  --workspace ws_d03_material_procurement \
  --workspace-root .radar-d03-workspace \
  --pack packs/weak-current/pack.json \
  --business-model packs/weak-current/business-model.json \
  --out .radar-d03-workspace/business-graph.json
```

The output is a derived JSON artifact and does not mutate immutable Evidence or historical DiscoveryRun records. The CLI verifies the Workspace Pack name/version/content digest lock before projection. The graph records the Workspace ID, DiscoveryRun IDs, model digest, Pack identity/version, counts, and inference policy.

## M12 static code analysis (candidate evidence)\n\nThe GitHub adapter analyzes fetched Python source snapshots with the standard-library AST module. It can emit:\n\n- `depends_on` Asset relationships for imports that resolve to another discovered Python file in the same repository.\n- `tests` Asset relationships when an import is found in a conventionally named test file.\n- code Evidence for the exact import line, with repository path and immutable commit ref.\n- guarded status-assignment candidates for narrow patterns such as `if doc.status == "Draft": doc.status = "Submitted"`. These include guard/assignment line ranges and class/function scope.\n\nEvery inferred relationship carries `metadata.inference_status=candidate_only`; state observations carry `metadata.code_analysis.inference_status=candidate_only`. Static AST inspection does not prove that a branch executes, that all states are covered, or that a workflow is correct. The current analyzer only handles Python and only resolves imports among code files already discovered in that run.\n\n## M12 declarative business invariants and verification levels

The Pack may optionally declare data-only invariants using a closed operator set: `sum_equals`, `less_than_or_equal`, `multiplication_equals`, `equal_with_tolerance`, and `separate_fields`. Each invariant names its scope, fields, related business entities, expected evidence, risk, and optional numeric tolerance. Arbitrary expressions or executable code are rejected.

Invariants appear as `business_invariant` graph nodes with status `declared_not_verified`. This release declares the D03 quantity balance, cumulative receipt/return limits, unit conversion, inventory-to-GL reconciliation, and separation of project cost dimensions. No numeric invariant is evaluated until Radar has structured source observations or test/runtime data.

Evidence also carries a separate `metadata.verification` dimension. Examples include `static_source`, `document_text`, `ci_check_success`, and `commit_status_success`. The core `verification_status=source_confirmed` means the source record was retrieved and its locator is known; it does not mean the code passed tests. CI evidence explicitly sets `runtime_observed=false`.

## M11 first-pass limitations

- Lexical matching is case-insensitive substring matching, not semantic understanding.
- The graph does not infer that a transition is complete from adjacent entity mentions.
- No criterion is marked supported by graph projection.
- The current D03 offline workspace has no locatable D03 Evidence; its graph should therefore show declared entities/processes/exceptions and zero candidate Evidence links.
- Full state-machine reconstruction across branches and files, quantitative quantity/value invariants, semantic adjudication, and automatic supported/contradicted assessment remain follow-up work. The criterion evidence matrix is a retrieval/triage aid; candidate evidence must be reviewed by an Agent or human before Assessment status changes.


## M13 structured business observations and deterministic invariant evaluation

A separate observation bundle may be supplied to `radar business-graph` with `--observations`. Its schema is versioned and each observation identifies an invariant, scope key, explicit origin (`runtime`, `test`, `static_source`, or `manual`), typed field values, and per-field Evidence ID plus a precise locator.

The evaluator uses Python's `Decimal` and a closed operator set. It emits `pass` or `fail` only for a concrete observation; missing observations remain `no_observation`. Every computed result carries its field-level provenance and Evidence IDs. Unknown Evidence references, non-finite numbers, missing field locators, and mismatches between declared and stored runtime verification metadata are rejected.

Verification levels remain distinct: runtime observations require Evidence explicitly marked `runtime_observed=true`; test fixtures produce `test_fixture`; static-source inputs produce `static_candidate`; manual inputs produce `manual_unverified`. Evaluation does not mutate Evidence, upgrade verification status, or directly change Requirement Assessment. A test fixture passing a numeric rule is not a production runtime verification.

Example bundle:
```json
{
  "schema_version": 1,
  "observations": [{
    "id": "obs_receipt_item_001",
    "invariant_id": "receipt_quantity_balance",
    "scope_key": "PO-001/item-1/receipt-1",
    "origin": "test",
    "values": {"accepted_qty": 8, "rejected_qty": 2, "received_qty": 10},
    "field_provenance": {
      "accepted_qty": {"evidence_id": "evd-accepted", "locator": {"path": "receipt.json", "field": "accepted_qty"}, "verification_level": "ci_check_success", "runtime_observed": false},
      "rejected_qty": {"evidence_id": "evd-rejected", "locator": {"path": "receipt.json", "field": "rejected_qty"}, "verification_level": "ci_check_success", "runtime_observed": false},
      "received_qty": {"evidence_id": "evd-received", "locator": {"path": "receipt.json", "field": "received_qty"}, "verification_level": "ci_check_success", "runtime_observed": false}
    }
  }]
}
```

Invoke with `radar business-graph --observations observations.json ...`. The observation's Evidence IDs must already exist in the selected Workspace.


## M13 acceptance-criterion to invariant mapping

An acceptance criterion may explicitly declare `invariant_ids`. The graph validates each ID against the locked business model, creates a `requires_invariant` edge, and attaches any scoped invariant evaluation records to that criterion. The criterion matrix reports `not_mapped`, `no_observation`, `computed_pass`, `computed_fail`, or `mixed` separately from its lexical candidate-evidence status.

These values are calculation states, not Requirement Assessment decisions. The edge status remains `computed_not_assessed`; a test fixture passing a rule cannot by itself make the acceptance criterion `supported`. D03 explicitly maps its receipt, quality, unit conversion, return, inventory valuation, and project-cost criteria to the corresponding Pack invariants.


## M13 conservative table-to-observation extraction

The weak-current Business Model now declares explicit bilingual `field_aliases` for receipt quantities, order/return quantities, unit conversion, and inventory/GL values. Alias collisions are rejected during Business Model validation. Aliases are Pack knowledge, not hard-coded global business vocabulary.

Use `radar extract-observations` to parse a local CSV or XLSX file and match its first row (per worksheet) to those exact aliases. The command requires an existing Workspace Asset and Evidence records for every source cell it uses. The `--source-path` value must exactly match the path stored in those Evidence locators. It emits a versioned observation bundle that can be supplied to `radar business-graph --observations`.

Only complete row-scoped numeric observations are emitted. Missing cells, missing Evidence, ambiguous aliases, non-numeric values, and unsupported `separate_fields` rules are skipped rather than guessed. The first version does not aggregate values across rows or accounting periods, infer project/document scope, or extract values from free-form prose. CSV and XLSX are supported; PDF/OCR, DOCX semantic tables, and runtime database/API observations are not.

Example:
```bash
python -m radar extract-observations \
  --workspace ws_d03_material_procurement \
  --workspace-root .radar-d03-workspace \
  --pack packs/weak-current/pack.json \
  --business-model packs/weak-current/business-model.json \
  --asset-id ast_receipt_register \
  --input receipts.xlsx \
  --source-path data/receipts.xlsx \
  --out observations.json

python -m radar business-graph \
  --workspace ws_d03_material_procurement \
  --workspace-root .radar-d03-workspace \
  --pack packs/weak-current/pack.json \
  --business-model packs/weak-current/business-model.json \
  --observations observations.json \
  --out business-graph.json
```

A successful numeric calculation from a document remains `static_candidate`, not runtime verification. It is not a final Requirement Assessment.


## M13 automatic table Evidence during GitHub discovery

When `radar discover --github` is used and the selected Pack directory contains `business-model.json`, discovery loads and validates that Business Model automatically. An explicit `--business-model` path can override the default.

For parsed CSV/XLSX documents, the Pack's exact `field_aliases` identify tables whose header row contains every required field for an invariant. Discovery creates a separate Evidence record for each populated data cell needed by those invariants, preserving repository path, immutable revision, Blob SHA, and CSV row/column or XLSX sheet/cell locator. This happens even when an individual cell does not contain a normal GitHub search keyword.

The selected cells are passed to the observation extractor in the same Discovery Run. A versioned bundle is written under the Workspace's `observations/` directory and its path and counts are included in the CLI result. Pass it to `radar business-graph --observations <path>`.

This remains conservative: only exact declared aliases and complete numeric rows are considered. It does not aggregate across multiple receipts/orders, infer document identity, prove that a document is authoritative, or turn a static document calculation into runtime verification. Missing tokens, unavailable repository trees, unsupported formats, and missing business models cannot silently produce successful observations.
