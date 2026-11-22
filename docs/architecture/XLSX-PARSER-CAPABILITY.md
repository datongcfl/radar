# M15-D3c2：XLSX Parser Capability v1

## Decision

Use the optional `openpyxl==3.1.5` library for XLSX workbook parsing.

- openpyxl: MIT; Python >=3.8; direct dependency.
- et-xmlfile: MIT; Python >=3.8; transitive dependency.
- defusedxml: PSF-2.0; explicit security dependency. openpyxl documents that its default XML handling does not guard against quadratic blowup or billion-laughs attacks unless defusedxml is installed.
- All three packages are pinned and SHA-256 locked in `requirements-xlsx.txt`.
- PyPI currently reports no Trusted Publishing provenance for these selected artifacts. This is a supply-chain observation, not evidence of malicious behavior.

The parser remains optional and does not add dependencies to Radar Core, `pyproject.toml`, or `uv.lock`.

## Input and output

Input is the original XLSX byte sequence, source URI, and optional filename. Output consists only of `document_fragment` records.

The parser emits:
- workbook metadata and defined-name observations;
- one worksheet metadata fragment per sheet, including visibility state, used range, merged ranges, and table references;
- one cell fragment per populated cell, with source-native sheet/cell locator, value type, number format, formula text, and cached formula value where present.

Formula text and cached values are distinct fields. The parser never evaluates formulas. Cached values may be absent or stale; their presence is not a claim that the formula is correct or current.

Hidden and very-hidden worksheets are retained and explicitly labeled. External links are not followed; openpyxl is invoked with `keep_links=False`. Macro-enabled workbooks are outside the v1 scope.

## Loading strategy

Use normal (non-read-only) workbook loading to retain merged-cell, table, named-range, and worksheet metadata. This costs more memory than streaming mode; therefore the parser applies input, ZIP expansion, XML, worksheet, cell, fragment, and character limits before and during extraction.

Load once with `data_only=False` to preserve formulas. If formula cells exist, load a second view with `data_only=True` to retrieve cached values. This does not calculate formulas; it reads values already stored in the XLSX package. The second workbook is not opened when there are no formulas.

## Safety preflight

Before importing openpyxl:
- enforce compressed input size and ZIP entry count;
- stream-decompress every ZIP member and count actual bytes rather than trusting central-directory sizes;
- enforce per-entry, total expanded-size, compression-ratio, and aggregate XML limits;
- reject absolute paths, backslashes, parent traversal, duplicate entries, encrypted members, DTD/entity declarations, and malformed ZIP/XML;
- count worksheet cell elements under a hard limit;
- require the XLSX content-types and workbook parts.

The default limits are 20 MiB input, 2,048 ZIP entries, 20 MiB per entry, 100 MiB total expanded data, 200:1 compression ratio, 20 MiB aggregate XML, 200 worksheets, 100,000 cells, 100,000 output fragments, and 2,000,000 extracted characters.

These checks reduce common archive/XML resource risks. They do not replace process isolation, CPU/memory limits, malware scanning, or adversarial corpus testing.

## Locator and semantics

Cell locators use the source-native worksheet title, worksheet index, A1 coordinate, and zero-based row/column indices. Worksheet metadata includes the original visibility state. Merged ranges and table references are preserved as structured metadata rather than pretending merged placeholders are independent values.

Cell values are normalized to JSON-safe primitives. Date/time values use ISO-8601 strings. Formula cells expose formula text and cached value separately.

## Explicit limitations

- XLSX is supported; XLS, XLSM, XLTX, and XLTM are not parsed by this capability.
- No formula execution, recalculation, VBA execution, external-link resolution, or data connection refresh.
- Charts, images, drawings, comments, pivot caches, slicers, conditional formatting semantics, data validation rules, and rich formatting are not reconstructed in v1.
- Styles are represented only by cell number format and style identifier; visual rendering is not attempted.
- Very large workbooks may exceed conservative limits. The parser is not a substitute for a streaming analytics engine.
- Cached formula values can be absent or stale.
- Parser output is not Evidence and does not determine truth, relevance, or requirement coverage.
- Real-world enterprise XLSX corpus testing remains outstanding.

## Acceptance

Generated workbook tests cover ordinary cells, formulas and cached values, date normalization, hidden/very-hidden sheets, merged ranges, tables, named ranges, source hash, locators, and the Evidence boundary. Dependency-independent tests cover missing optional dependencies, invalid packages, ZIP/XML safety checks, and configured resource limits. CI installs the hash-locked optional dependency set on Python 3.9 and 3.13.
