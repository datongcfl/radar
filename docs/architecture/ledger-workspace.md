# Ledger Workspace Records

Ledger controls can now be backed by immutable, Workspace-scoped records instead of a transient JSON bundle.

## Trust boundary

- Source Assets and Evidence must already exist in the selected Workspace.
- Every imported ledger effect and extraction manifest must reference an existing Evidence ID.
- The Evidence must belong to the same Asset, and its exact locator must match the imported row.
- Import does not create or upgrade Evidence. A supplied Evidence object must exactly equal the persisted Workspace record.
- Ledger effects, voucher extraction manifests, and aggregation rules are stored as distinct typed records in append-only JSONL collections.
- A bundle is preflighted for schema and duplicate identity errors before the first append. Filesystem failures during append are not a multi-file transaction.
- Control results remain computed outputs, not business assessments.

## Commands

Import a bundle whose Evidence has already been recorded in the Workspace:

```bash
radar ledger-import \
  --workspace ws_d03_material_procurement \
  --workspace-root .radar-d03-workspace \
  --input ledger-control-input.json
```

Run controls from persisted Workspace records:

```bash
radar ledger-control \
  --workspace ws_d03_material_procurement \
  --workspace-root .radar-d03-workspace \
  --out ledger-control-result.json
```

The legacy explicit-input mode remains available:

```bash
radar ledger-control --input ledger-control-input.json --out ledger-control-result.json
```

`--input` and `--workspace` are mutually exclusive. Workspace mode reads the complete set of persisted ledger records and the referenced Workspace Evidence; tolerance values remain explicit CLI inputs.

## Record collections

- `ledger_effects.jsonl`: normalized stock / general-ledger effects with exact Evidence provenance.
- `ledger_manifests.jsonl`: explicit voucher extraction manifests.
- `ledger_aggregation_rules.jsonl`: declared aggregation rules.

No ERP adapter or automatic Discovery trigger is implied by these commands. Import is an explicit trust-boundary crossing; source completeness and ERP extraction semantics remain the responsibility of a future adapter and Pack-governed workflow.
