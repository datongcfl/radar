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
- XML backend: `lxml`, a transitive dependency (BSD-3-Clause).
- Neither package is a Core dependency.
- This implementation deliberately does not add an unhashed requirements file or silently modify the universal lock. The separately tracked packaging task must lock the complete transitive wheel set and hashes for the supported platforms before the optional installation workflow is promoted to a reproducible release path.

PyPI records no Trusted Publishing provenance for python-docx 1.2.0 and lxml 6.1.3. This is a supply-chain observation, not a claim that either package is malicious.

## Limitations

- Headers, footers, comments, tracked changes, footnotes, endnotes, text boxes, and embedded objects are not extracted in v1.
- Images and scanned pages are not OCR'd.
- Paragraph order is document XML order, not rendered page order.
- Page numbers are not inferred because DOCX pagination depends on the rendering engine.
- Tables are represented as cells; visual layout and merged-cell rendering are not reconstructed.
- Parser output is not Evidence and does not determine truth, relevance, or requirement coverage.

## Acceptance status

The code includes generated-document tests for headings, paragraphs, tables, nested tables, locators, SHA-256, invalid input, ZIP limits, unsafe XML declarations, and the Evidence boundary. These tests execute only when python-docx is installed; the default Core environment remains dependency-free. Full optional-dependency CI qualification and real-world DOCX corpus testing remain outstanding.
