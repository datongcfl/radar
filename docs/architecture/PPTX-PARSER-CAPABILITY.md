# PPTX Parser Capability

## Decision
Implement an independent optional parser using the official python-pptx 1.0.2 distribution. PyPI identifies 1.0.2 as the latest release for the python-pptx project, MIT licensed, requiring Python >=3.8. This is distinct from similarly named third-party packages and forks.

The isolated, hash-locked dependency set is python-pptx 1.0.2 (MIT), lxml 6.1.3 (BSD-3-Clause), Pillow 11.3.0 (MIT-CMU), typing-extensions 4.16.0 (PSF-2.0), and XlsxWriter 3.3.3 (BSD-2-Clause). Pillow 11.3.0 is the shared Python 3.9/3.13-compatible release. XlsxWriter is included because it is a declared upstream dependency, but this parser does not create or calculate charts. PyPI release files for python-pptx 1.0.2 have no Trusted Publishing provenance; this is a recorded supply-chain limitation.

## First increment
- Presentation and slide count.
- Text-frame paragraphs with shape and paragraph locators.
- Table cells with slide, shape, row, and cell locators.
- Speaker notes as separate fragments.
- Grouped-shape recursion preserving shape path.
- Source SHA-256 and stable fragment indices.

## Safety
PPTX is a ZIP/XML package. The adapter streams entries and counts actual decompressed bytes, bounding input size, entry count, per-entry and aggregate size, XML size, compression ratio, slides, shapes, cells, fragments, and extracted characters. It rejects path traversal, duplicate entries, encrypted entries, DTD/entity declarations, malformed packages, macro-bearing packages, and .pptm files. External relationships are never dereferenced. Macros, embedded scripts, formula-like text, and linked resources are not executed or fetched.

## Locators
Slide number is 1-based and slide index 0-based. Shape, paragraph, row, and cell indices are 0-based. Grouped shapes preserve a shape_path. Speaker notes use a separate locator namespace. Shape order is source order, not guaranteed visual reading order.

## Evidence boundary and non-goals
All outputs are document_fragment observations; no automatic Evidence or Assessment promotion. OCR, image captioning, chart-data extraction, SmartArt reconstruction, animations, transitions, comments, handout/master parsing, visual-layout reconstruction, and guaranteed reading order are out of scope.

## Acceptance
The optional CI matrix installs the exact dependency set with pip --require-hashes and runs the full suite on Python 3.9 and 3.13. Fixtures cover text, tables, notes, locators, malformed ZIP packages, macro content, DTD/entity rejection, resource limits, and missing dependencies. Generated fixtures do not qualify the parser against real enterprise presentation corpora; that remains outstanding.
