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
- `located_in`: connects an Evidence node to its source Asset.
- `has_criterion`: connects a Requirement to its acceptance criterion.

A term match never creates `implements` or `supports`. Declared transitions have no evidence IDs and do not prove implementation. No match means only that the current evidence set did not match the declared terms; it does not mean the feature is absent. Evidence verification status is copied from its source record, not upgraded by graph projection.

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

The output is a derived JSON artifact and does not mutate immutable Evidence or historical DiscoveryRun records. The graph records the model digest, Pack identity/version, counts, and inference policy.

## M11 first-pass limitations

- Lexical matching is case-insensitive substring matching, not semantic understanding.
- The graph does not infer that a transition is complete from adjacent entity mentions.
- No criterion is marked supported by graph projection.
- The current D03 offline workspace has no locatable D03 Evidence; its graph should therefore show declared entities/processes/exceptions and zero candidate Evidence links.
- Cross-file joins, state-machine reconstruction, quantitative quantity/value invariants, and automated criterion-level evidence evaluation remain follow-up work.
