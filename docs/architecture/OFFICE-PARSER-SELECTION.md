# M15-D3c：Office Parser 组件选型与拆分策略

## 状态

- Status: proposed and approved for staged implementation
- Base: `main` after PDF parser PR #36
- Scope of this decision: DOCX, XLSX, PPTX parser capabilities
- This document does not claim that any Office parser is implemented.

## 1. Decision

Office parsing is split into three independent capabilities and optional dependency groups:

| Format | Candidate | Initial decision | Why |
|---|---|---|---|
| DOCX | `python-docx` 1.2.0 | Select for the first adapter | MIT; Python >=3.9; mature document object model; supports paragraph/table extraction |
| XLSX | `openpyxl` 3.1.5 | Select for a separate later adapter | MIT; Python >=3.8; exposes worksheets, cells, formulas, merged ranges, and visibility; formulas are not calculated |
| PPTX | `python-pptx` 1.0.2 | Select for a separate later adapter | MIT; Python >=3.8; exposes slides, shapes, text frames, tables, and speaker notes |

These packages are not installed together by default. Each adapter is imported lazily and installed independently. A user needing only DOCX must not install spreadsheet or presentation dependencies.

## 2. Dependency and supply-chain review

### DOCX: python-docx

- Selected version: 1.2.0.
- License: MIT.
- Requires Python >=3.9, matching Radar's current baseline.
- Direct dependency tree includes `lxml`; the exact transitive version and wheel hashes must be pinned when the adapter is implemented.
- PyPI release files currently show no Trusted Publishing provenance. This is a recorded supply-chain limitation, not a claim that the package is unsafe.
- PyPI wheel SHA-256 for `python_docx-1.2.0-py3-none-any.whl`: `3fd478f3250fbbbfd3b94fe1e985955737c145627498896a8a6bf81f4baf66c7`.

### XLSX: openpyxl

- Selected version: 3.1.5.
- License: MIT.
- Requires Python >=3.8, compatible with Radar's baseline.
- Runtime dependency includes `et-xmlfile`; the optional extra must pin and hash the full transitive set.
- PyPI release files currently show no Trusted Publishing provenance.
- Upstream explicitly warns that XML expansion attacks are not guarded by default and recommends `defusedxml` for that threat class. The Radar adapter must add the required protection or reject untrusted workbooks under a documented resource policy; this is a release gate, not a deferred footnote.
- PyPI wheel SHA-256 for `openpyxl-3.1.5-py2.py3-none-any.whl`: `5282c12b107bffeef825f4617dc029afaf41d0ea60823bbb665ef3079dc79de2`.

### PPTX: python-pptx

- Selected version: 1.0.2.
- License: MIT.
- Requires Python >=3.8, compatible with Radar's baseline.
- Runtime dependencies include `lxml` and `Pillow`; chart-related features may introduce further dependencies. The adapter must avoid enabling unused chart-writing paths and lock the actual resolved dependency set.
- PyPI release files currently show no Trusted Publishing provenance.
- PyPI wheel SHA-256 for `python_pptx-1.0.2-py3-none-any.whl`: `160838e0b8565a8b1f67947675886e9fea18aa5e795db7ae531606d68e785cba`.

## 3. Adapter order

Implement and validate in this order:

1. DOCX paragraphs and tables.
2. XLSX worksheets and cell-level observations.
3. PPTX slide text, tables, and notes.

This order prioritizes business requirements and process evidence commonly stored in Word documents and spreadsheets, while avoiding a combined dependency and test surface.

## 4. Required source-native locators

### DOCX

- Paragraph: body-order index, paragraph index, style name, heading path.
- Table: body-order index, table index, row index, cell index.
- Preserve the distinction between paragraph text and table-cell text.
- Handle nested tables without flattening their contents into the parent cell's locator.
- Headers, footers, comments, tracked changes, footnotes, and embedded objects are out of the first increment unless explicitly tested.

### XLSX

- Worksheet name and stable worksheet index.
- Cell coordinate and row/column indices.
- Formula text and cached value are separate fields; never evaluate formulas.
- Load formula and cached-value views separately where possible. A missing cached value must remain missing, not be presented as zero.
- Record hidden/very-hidden sheet state, merged ranges, and workbook date epoch.
- Do not treat a cell's displayed formatting as its semantic value.

### PPTX

- 1-based slide number and zero-based slide index.
- Shape index and shape type.
- Paragraph index for text frames.
- Table index, row index, and cell index.
- Speaker notes are a separate fragment type and locator namespace.
- Reading order is shape order, not a guarantee of visual reading order.

## 5. Common parser output contract

All adapters emit `document_fragment` records, never Evidence or Assessment records.

Every fragment must include:

- original document URI;
- SHA-256 of the original document bytes;
- document format and parser identity/version;
- stable fragment index and fragment type;
- extracted text or a typed structured observation;
- source-native locator with explicit index bases;
- bounded warnings for omitted or unsupported content.

The adapter must not invent semantic relationships between paragraphs, rows, cells, slides, or notes. Relationship construction belongs to later discovery/normalization stages.

## 6. Safety and resource gates

Office files are ZIP containers with XML and may be malicious or oversized. Each adapter must:

- enforce compressed input byte limit, entry count limit, per-entry uncompressed limit, and total uncompressed size limit before parsing;
- reject path traversal entries and suspicious compression ratios;
- reject encrypted or unsupported package structures explicitly;
- prevent XML entity expansion and external resource resolution;
- cap paragraphs, tables, rows, columns, slides, shapes, cells, and extracted characters;
- never execute VBA/macros, formulas, embedded scripts, or external links;
- return partial/failed/skipped with explicit warnings rather than silently dropping content;
- avoid returning local absolute paths or secrets.

The implementation must include malformed, truncated, oversized, and adversarial fixtures. A successful unit test on a tiny generated file is not equivalent to qualification against real Office documents.

## 7. Packaging policy

- Do not add Office libraries to `project.dependencies`.
- Add a named optional extra only alongside a working adapter and a full optional-dependency CI job.
- Lock all transitive dependencies and hashes; do not use an unhashed requirements file as a reproducibility substitute.
- Keep each format independently installable.
- Keep the default Core test matrix free of Office dependencies.
- Do not change `uv.lock` until the named extras are approved and all platform/Python markers are verified.

## 8. Acceptance gates before implementation is considered complete

- Python 3.9 and 3.13 support.
- Reproducible, hash-verified optional installation.
- Missing optional dependency returns `unavailable`, not import-time failure.
- Source-native locator tests for all supported fragment types.
- No automatic Evidence promotion.
- Resource-limit and malformed-file tests.
- Real-world corpus qualification covering ordinary and complex documents.
- Core CI remains green without Office extras.

## 9. Explicit non-goals

- OCR of embedded/scanned images.
- Full visual-layout reconstruction or guaranteed reading order.
- Formula execution or recalculation.
- Macro execution.
- Full fidelity round-trip editing.
- Automatic business-process inference from Office layout alone.
