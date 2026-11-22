# Radar Document Adapter Contract

> Status: M14-D contract v1; implementation and production qualification are staged separately.

## 1. Purpose

Radar must parse heterogeneous knowledge assets without coupling its Evidence model to a particular parser vendor. The adapter boundary isolates file-format parsing from Asset identity, Evidence trust, requirement coverage, and business assessment.

A parser extracts observations. Radar decides what those observations mean.

## 2. Responsibilities

### Adapter responsibilities

- Declare supported file formats and parser engine/version.
- Parse bytes without executing macros, scripts, embedded programs, or document actions.
- Return text and structured blocks with deterministic source locators.
- Preserve page, paragraph, table, row, column, Sheet/Cell, slide, code line/column, or character-region coordinates where available.
- Return explicit parsed, partial, unsupported, dependency_missing, or failed states.
- Surface warnings, skipped content, extraction limitations, and parser metadata.
- Apply configured byte/page/time limits or run inside a constrained worker.

### Radar core responsibilities

- Resolve the input to a Workspace Asset and validate its identity and source provenance.
- Create Evidence records only after checking Asset ownership, content hash, and locator consistency.
- Keep raw extracted text distinct from normalized text, model-generated interpretation, and business conclusions.
- Map Evidence to requirements and Pack units.
- Run domain rules and Assessment separately.
- Preserve unresolved results when the parser cannot prove extraction completeness.

An adapter must never create a verified business fact, approve a requirement, or upgrade an Evidence trust level by itself.

## 3. Result contract

A parser result is a JSON-compatible object:

~~~json
{
  "schema_version": 1,
  "status": "parsed",
  "adapter": {
    "id": "pdf.pypdf",
    "version": "6.21.4"
  },
  "source": {
    "asset_id": "asset_123",
    "content_sha256": "..."
  },
  "chunks": [
    {
      "kind": "page_text",
      "text": "Purchase order PO-001 ...",
      "locator": {
        "page": 1,
        "block": "page_text"
      },
      "extraction": {
        "method": "native_text",
        "confidence": null
      }
    }
  ],
  "warnings": [],
  "errors": []
}
~~~

Required fields:

- schema_version: result contract version.
- status: one of parsed, partial, unsupported, dependency_missing, failed.
- adapter.id and adapter.version: exact parser identity.
- source.asset_id and source.content_sha256: the input Asset and immutable byte identity.
- chunks: zero or more independently locatable observations.
- warnings and errors: machine-readable diagnostic arrays.

A zero-chunk parsed result is not allowed unless the adapter explicitly establishes that the document contains no extractable content. Otherwise it must return partial, unsupported, or failed.

## 4. Locator contract

Locators are one-based for human-facing page/paragraph/table/row/column/slide numbers, unless a field explicitly documents a zero-based coordinate.

| Format | Minimum locator | Preferred additional locator |
|---|---|---|
| PDF text | page number | block index, bounding box, character offsets |
| PDF table | page + table + row + column | cell bounding box |
| DOCX | paragraph or table/row/column | part name, heading path, run range |
| XLSX | Sheet + Cell | formula/value type, merged range, row/column |
| PPTX | slide + paragraph | shape id, notes/chart reference |
| CSV | row + column | header name, byte range |
| Source code | path + start/end line | start/end column, byte range, symbol path |

Locator values must be deterministic for identical input bytes and the same adapter version. If the parser cannot provide a stable locator, the result must say so rather than inventing one.

## 5. Adapter selection and fallback

- Engine selection must be explicit in reproducible jobs.
- An auto mode may be added only when its priority order is deterministic and the chosen engine is recorded in the result.
- Fallback is allowed only when the previous engine is unavailable or fails; the result must record all attempted engines.
- Do not concatenate outputs from multiple engines without deduplication and provenance. Duplicate text must not inflate evidence coverage.
- Preserve the parser-native locator alongside any Radar-normalized locator.

## 6. Security and failure isolation

- Reject oversized input and ZIP expansion beyond configured limits.
- Do not execute Office macros, JavaScript, embedded executables, or PDF actions.
- Disable parser-initiated network access.
- Native parsers such as PDFium should run in a worker process with timeout and memory limits before production use.
- Never log document contents, credentials, or private source paths unnecessarily.
- A timeout, crash, or malformed file must become an explicit failed/unresolved result, not an empty successful parse.

## 7. First implementation order

1. Keep the existing stdlib CSV/DOCX/XLSX/PPTX parser as the fallback baseline.
2. Implement a PDF page-text adapter with pypdf as the first candidate.
3. Add a separate table/geometry adapter only if real sample benchmarks justify pdfplumber or pypdfium2.
4. Add a Tree-sitter source adapter for syntax structure only; keep Python AST semantic extraction intact.
5. Add OCR and Docling only as isolated optional capabilities after model, data, and security review.

## 8. Acceptance criteria

- Adapter result schema validates.
- Same input bytes and adapter version produce stable locators.
- Every chunk links back to the same Asset and content hash.
- Missing optional dependencies return dependency_missing with install guidance.
- Unsupported formats are not reported as successful empty parses.
- Existing CLI and stdlib parsers continue to work without optional extras.
- Adapter output cannot create Evidence or Assessment without Radar validation.
- Tests cover malformed, oversized, partial, multilingual, and duplicate-content inputs.

## 9. Related decisions

- Dependency tiers and admission: ../OPEN_SOURCE_COMPONENT_SELECTION.md
- Existing Office parsing and M14 component inventory: ../M14-COMPONENT-INVENTORY.md
- Ledger Evidence trust boundary: ledger-workspace.md
