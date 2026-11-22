# Generic Ledger Source Adapter

> Status: M13-H first implementation plus mapping/numeric hardening; CSV/XLSX mapping is explicit and source-system agnostic. No real ERP connector is claimed.

## 1. Purpose

The adapter converts a user-provided stock or general-ledger export into Radar's canonical Ledger Effect records. It is a format and mapping boundary, not an ERP integration and not a business assessment engine.

The adapter is deliberately driven by a Pack business-model declaration:

- The business model declares the adapter id, source system, ledger kind, file format, header row, field map, value maps, date format, and numeric locale.
- The user selects the declared adapter id when importing a file.
- Unknown or ambiguous headers are rejected; no fuzzy matching is used.
- The adapter does not infer missing identifiers, accounting periods, units, currencies, or sign conventions.

A real ERP export mapping must be verified against an actual export before it is declared production-ready. The weak-current Pack does not ship a vendor-specific mapping because no real ERP export was supplied.

## 2. Pack business-model declaration

A minimal stock CSV mapping looks like:

~~~json
{
  "id": "erp-stock-csv-v1",
  "source_system": "erp-a",
  "format": "csv",
  "ledger_kind": "stock",
  "header_row": 1,
  "delimiter": ",",
  "field_map": {
    "ledger_entry_id": ["Ledger Entry ID", "库存流水号"],
    "company_id": ["Company ID", "公司编码"],
    "voucher_type": ["Voucher Type", "单据类型"],
    "voucher_id": ["Voucher ID", "单据号"],
    "voucher_item_id": ["Voucher Item ID", "单据明细ID"],
    "event_kind": ["Event Kind", "业务事件"],
    "posting_status": ["Posting Status", "过账状态"],
    "currency": ["Currency", "币种"],
    "accounting_period": ["Accounting Period", "会计期间"],
    "item_id": ["Item ID", "物料编码"],
    "warehouse_id": ["Warehouse ID", "仓库编码"],
    "quantity_delta": ["Quantity Delta", "数量变动"],
    "quantity_uom": ["Quantity UOM", "计量单位"],
    "stock_value_delta": ["Stock Value Delta", "库存价值变动"]
  },
  "optional_fields": ["posting_date", "reversal_of"],
  "value_maps": {
    "posting_status": {
      "Posted": "posted",
      "Reversal": "reversal",
      "Adjustment": "adjustment",
      "已过账": "posted",
      "冲销": "reversal",
      "调整": "adjustment"
    }
  },
  "number_format": {
    "decimal_separator": ".",
    "thousands_separator": ","
  },
  "date_format": "%Y-%m-%d"
}
~~~

For XLSX, set format to xlsx and declare an exact sheet_name. The header_row remains one-based.

General-ledger mappings use ledger_kind general_ledger and must map account_id, debit_amount, and credit_amount instead of the stock dimensions.

Required common fields include ledger_entry_id, company_id, voucher_type, voucher_id, voucher_item_id, event_kind, posting_status, currency, and accounting_period. The source_system and ledger_kind are explicit adapter-level constants.

## 3. Supported conversions

- CSV: UTF-8/UTF-8-SIG by default; delimiter must be declared.
- XLSX: exact sheet and header row; current stdlib parser supplies cell values and sheet/cell positions.
- Decimal: decimal and thousands separators are explicit. No float arithmetic is used.
- Date: parse using the declared date_format or ISO date format.
- Status: source values must map to posted, reversal, or adjustment.
- Sign: source quantities and amounts are preserved as signed values. The adapter does not infer movement direction.
- Units and currency: passed through as declared source values; no conversion is performed.

The adapter enforces a source file size limit and an XLSX expanded-size/compression-ratio limit.

## 4. Evidence and provenance

Each non-empty source row creates or reuses a Workspace Evidence record:

- CSV locator: path + row + block=row.
- XLSX locator: path + sheet + row + block=row.
- Evidence statement preserves the original headers and row values.
- The original source file is copied into the Workspace content-addressed assets directory; the persisted bytes are SHA-256 verified before the Asset is created.
- Asset metadata records the source file SHA-256, format, adapter id, and Workspace-relative storage path; the Asset URI points to the persisted copy, not the caller's transient input path.
- Re-importing the same file reuses the same Asset and row Evidence.

The ledger validator now accepts a row-block locator. This points to the entire source row, not a fabricated single-cell locator.

Rows that cannot be mapped still retain source Evidence and appear in the unresolved report. They do not become Ledger Effects.

## 5. Explicit voucher extraction manifest

GL voucher completeness requires a separate export manifest. The adapter accepts an optional JSONL file with one voucher assertion per line:

~~~json
{"id":"MAN-2026-11-JV-1","source_system":"erp-a","company_id":"C1","currency":"USD","voucher_type":"Journal Entry","voucher_id":"JV-1","accounting_period":"2026-11","expected_ledger_entry_ids":["GL-1","GL-2"],"export_id":"ERP-EXPORT-2026-11"}
~~~

The expected ledger entry ids must come from an independent ERP export control or trusted extraction process. The adapter never derives this list from the ledger rows it is validating.

Each manifest line gets its own Asset and Evidence with a JSONL line locator. Manifest Evidence is marked unverified because the adapter can prove what the manifest file says, not that the ERP's completeness assertion is true. Voucher validation remains a computed control, not a business Assessment.

If no manifest is supplied, GL voucher completeness remains unresolved with missing_voucher_extraction_manifest.

## 6. Import and idempotency

Command:

~~~bash
radar ledger-adapt \
  --workspace ws_d03_material_procurement \
  --workspace-root .radar-d03-workspace \
  --pack packs/weak-current/pack.json \
  --business-model packs/weak-current/business-model.json \
  --adapter-id erp-stock-csv-v1 \
  --input stock-ledger.csv \
  --out stock-adapt-result.json

radar ledger-adapt \
  --workspace ws_d03_material_procurement \
  --workspace-root .radar-d03-workspace \
  --pack packs/weak-current/pack.json \
  --business-model packs/weak-current/business-model.json \
  --adapter-id erp-gl-csv-v1 \
  --input general-ledger.csv \
  --manifest gl-export-manifest.jsonl \
  --out gl-adapt-result.json
~~~

The Workspace must already exist and its Pack lock must match the supplied Pack.

The adapter:

1. validates the mapping;
2. parses the source file and creates/reuses source Asset and row Evidence;
3. validates each normalized Ledger Effect;
4. records unresolved rows and duplicate identities;
5. imports only new, non-conflicting effects, manifests, and Pack aggregation rules through the existing Workspace ledger importer.

Exact re-imports are idempotent. A repeated ledger identity with changed business values is unresolved and excluded. The adapter does not overwrite append-only Workspace records.

After import, run controls explicitly:

~~~bash
radar ledger-control \
  --workspace ws_d03_material_procurement \
  --workspace-root .radar-d03-workspace \
  --out ledger-control-result.json
~~~

## 7. Boundaries and known limitations

- CSV and XLSX only; no direct ERP API, database, EDI, PDF, or scanned-document adapter.
- No source-specific mapping is approved without a real export sample.
- XLSX formulas are not recalculated; only cached values exposed by the current parser can be used.
- The adapter does not prove the export covers the complete accounting period or all source records.
- The external manifest is an assertion with provenance, not cryptographic proof of completeness.
- No automatic FX, unit conversion, valuation, account mapping, or reversal generation.
- The append-only multi-file Workspace write is not a cross-file transaction; a filesystem failure may leave source Evidence without corresponding Ledger Effects.
- Ledger Control outputs remain computed_not_assessed until a separate Assessment workflow evaluates the business criteria.

## 8. Acceptance tests

The first implementation covers:

- explicit CSV header mapping and decimal/date parsing;
- row-level Evidence locator validation;
- source file and Evidence reuse on re-import;
- ambiguous headers rejected before Asset creation;
- malformed numeric rows retained as Evidence but excluded as effects;
- conflicting duplicate ledger identities excluded;
- external JSONL voucher manifest imported as separate Evidence;
- GL voucher completeness and balancing checked against the independent manifest;
- Pack business-model adapter declarations validated;
- CLI enforces the Workspace Pack lock;
- locale-aware decimal parsing rejects malformed thousands grouping;
- normalized value-map key collisions and cross-ledger-kind field mappings are rejected;
- floating-point constants are rejected to avoid silently importing binary floating-point approximations;
- imported stock effects are rehydrated from Workspace and passed through the full Ledger Control Pipeline, including aggregation, without being promoted to business Assessment.


## 9. CI validation

The first implementation passed 254 tests on Python 3.9 and Python 3.13. The mapping/numeric hardening pass added five regression tests; the full 259-test suite passed on both versions. The dedicated adapter tests cover CSV, XLSX, row Evidence, idempotency, ambiguous headers, locale-specific decimal parsing, malformed thousands grouping, normalized value-map collisions, cross-ledger-kind mapping rejection, float-constant rejection, duplicate identities, external GL voucher manifests, and an end-to-end adapter-to-Ledger-Control-Pipeline test. Both the regular Radar test workflow and the package smoke workflow passed:

- https://github.com/datongcfl/radar/actions/runs/44981403964
- https://github.com/datongcfl/radar/actions/runs/44981403973
