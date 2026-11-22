# M15-D3c1：DOCX Parser Capability v1

## Scope

The first Office parser increment implements DOCX paragraph and table-cell extraction using the optional `python-docx==1.2.0` dependency. It does not add the dependency to Radar Core, change `pyproject.toml`, or update `uv.lock`.

The parser is imported only inside `execute()`. If the optional package is absent, the capability returns `unavailable` instead of breaking Radar imports.

## Input and output

Input is the original DOCX byte sequence, source URI, and optional filename. The output consists only of `document_fragment` records.

Each record contains the source URI, original-byte SHA-256, parser identity/version, fragment type, text, heading path, and a source-native locator.

### Paragraph locator

- `body_order_index`: zero-based position among top-level body blocks.
- `paragraph_index`: zero-based index among top-level paragraphs.
- `style_name`: source paragraph style.
- `heading_path`: current Heading 1..9 ancestry.

### Table-cell locator

- `table_index`: zero-based index in parser traversal order.
- `row_index` / `cell_index`: zero-based indices in the source table grid.
- `grid_span`: horizontal merge span where exposed by the source XML.
- `table_path`: parent table/cell ancestry for nested tables.
- `paragraph_count`: number of direct paragraphs in the cell.

Cell content is emitted as one cell fragment. Nested tables are emitted as their own table/cell fragments and are not silently flattened into the parent cell locator.

## Safety preflight

Before importing or invoking python-docx, the parser checks:

- input byte limit;
- ZIP entry count, individual entry size, total uncompressed size, and compression ratio;
- absolute paths, backslashes, parent traversal, and duplicate ZIP entry names;
- total XML size;
- DTD/entity declarations in XML and relationship parts;
- required DOCX package entries.

The default limits are 20 MiB compressed input, 2,048 ZIP entries, 20 MiB per entry, 100 MiB total uncompressed data, 200:1 maximum compression ratio, 20 MiB aggregate XML, 100,000 fragments, and 2,000,000 extracted characters.

These checks reduce common archive/XML resource risks; they are not a substitute for process isolation, CPU timeouts, memory limits, malware scanning, or a real adversarial corpus. The adapter never executes macros, fields, formulas, embedded scripts, or external links.

## Dependency decision

- Direct dependency: `python-docx==1.2.0` (MIT; Python >=3.9).
- XML backend: `lxml==6.1.3`, a transitive dependency (BSD-3-Clause).
- Compatibility dependency: `typing_extensions==4.16.0` (PSF-2.0), required by the selected python-docx release metadata.
- None of these packages is a Core dependency.
- `requirements-docx.txt` pins all three packages and verifies SHA-256 hashes for the Python 3.9/3.13 Linux CI wheels plus the lxml source archive.
- The optional CI matrix installs the dependency set with `pip --require-hashes`; the default Core matrix remains dependency-free.
- `uv.lock` remains unchanged because the optional capability is not yet promoted to a named project extra. A later packaging decision can integrate it into the universal lock once the supported OS/platform policy is agreed.

PyPI records no Trusted Publishing provenance for python-docx 1.2.0 and lxml 6.1.3. This is a supply-chain observation, not a claim that either package is malicious.

## Limitations

- Headers, footers, comments, tracked changes, footnotes, endnotes, text boxes, and embedded objects are not extracted in v1.
- Images and scanned pages are not OCR'd.
- Paragraph order is document XML order, not rendered page order.
- Page numbers are not inferred because DOCX pagination depends on the rendering engine.
- Tables are represented as cells; visual layout and merged-cell rendering are not reconstructed.
- Parser output is not Evidence and does not determine truth, relevance, or requirement coverage.

## Acceptance status

Generated-document extraction tests cover headings, paragraphs, tables, nested tables, locators, source hash, and the Evidence boundary. They run in the optional DOCX CI matrix. Dependency-independent tests always cover the missing-package `unavailable` response, input limits, and unsafe XML rejection. Real-world DOCX corpus testing remains outstanding.
