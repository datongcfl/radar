# M15-D3b：PDF Parser Capability v1

## Decision

**Accept as an optional L2 capability: pypdf 6.21.4.** Do not install it in Core or make it a default dependency.

Reasons:
- pypdf 6.21.4 supports Python >=3.9 and is BSD-3-Clause, preserving Radar's current minimum Python version. Newer pypdf 7.1.1 requires Python >=3.10, so it is not selected for the current cross-version baseline.
- The wheel is platform-independent and the release includes PyPI Trusted Publishing provenance.
- It provides page-level text extraction without requiring a native executable or OCR model.
- The PDF parser can be isolated behind the existing Parser Capability contract and is loaded lazily.

pdfplumber 0.11.11 is MIT and has richer character/line/table geometry, but its current upstream test matrix starts at Python 3.10, it depends on pdfminer.six, and its latest PyPI release has no provenance metadata. It remains a candidate for a later layout/table-specific capability, not a reason to add it to the baseline parser now. The two tools solve different depths of extraction and should not be treated as interchangeable.

References:
- pypdf 6.21.4 metadata, Python requirement, license, wheel and provenance: https://pypi.org/project/pypdf/6.21.4/
- pypdf 7.1.1 metadata and Python >=3.10: https://pypi.org/project/pypdf/7.1.1/
- pdfplumber 0.11.11 metadata and upstream tested Python versions: https://pypi.org/project/pdfplumber/0.11.11/
- pypdf visitor API and coordinate information: https://github.com/py-pdf/pypdf/blob/main/docs/user/extract-text.md

## Installation

The Core remains free of the PDF dependency. Install the optional, hash-pinned dependency only where PDF parsing is required:

```bash
python -m pip install --require-hashes -r requirements-pdf.txt
```

The dependency is deliberately kept out of the universal Core lockfile for this increment; a future packaging change should expose an install extra and update the universal lock atomically.

## Output contract

The provider emits one `document_fragment` per text-bearing page. Locators preserve:
- 1-based `page_number` and 0-based `page_index`;
- page-local character interval `[char_start, char_end)`;
- page-local line range;
- page text SHA-256 and whole-document SHA-256.

This first implementation deliberately uses page-level fragments. It does not claim reliable paragraph ordering, bounding boxes, table cells, headers/footers classification, reading order, or OCR. It never converts parse output directly into Evidence.

## Failure and safety behavior

- Missing pypdf returns `unavailable` with an installation hint.
- Encrypted PDFs are `skipped`; no password guessing or decryption workflow is attempted.
- Invalid headers, malformed files, resource limits, and extraction errors are explicit failures.
- Defaults cap input at 25 MiB, document length at 500 pages, and extracted text at 500,000 characters per page.
- Pages without extractable text produce warnings; mixed documents return `partial`; documents with no extractable text return `skipped` (likely scanned/image-only).
- No OCR, macros, JavaScript, embedded files, or network access are executed.

The byte/page/character limits are guardrails, not a complete sandbox. Production use on untrusted PDFs still requires process-level CPU/memory/time limits and adversarial corpus testing.

## Validation scope

The tests generate small valid PDF fixtures with selectable text and verify page locators, hashes, encrypted-file handling, no-text pages, input validation and resource limits. This validates the adapter contract, not extraction quality across real-world PDFs.

A representative benchmark corpus remains necessary before claiming support for multi-column layouts, Chinese font encodings, rotated pages, complex tables, malformed cross-reference tables, or scanned PDFs.
