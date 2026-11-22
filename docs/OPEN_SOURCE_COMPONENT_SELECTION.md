

## 13. M15-D3b PDF parser decision (2026-11-22)

- **Accept / L2 optional:** pypdf 6.21.4, BSD-3-Clause, Python >=3.9, platform-independent wheel with PyPI Trusted Publishing provenance. It preserves the Radar Python 3.9 baseline and supplies page-level text extraction without native binaries or OCR models.
- **Not selected for baseline:** pypdf 7.1.1 requires Python >=3.10. It may be reconsidered after the project changes its minimum Python version.
- **Hold for layout/table-specific work:** pdfplumber 0.11.11 is MIT and exposes character/line/table geometry, but current upstream test matrix begins at Python 3.10, adds pdfminer.six, and the current PyPI release has no provenance metadata. Compare on a real layout corpus before adoption.
- The optional dependency is hash-pinned in `requirements-pdf.txt`; it is not installed by Core and is not added to `uv.lock` in this increment. A future packaging PR should add a named extra and regenerate the universal lock atomically.
- The adapter emits page-level fragments only. It does not claim OCR, table cells, bounding boxes, reading-order fidelity, or Evidence promotion.
- Source: https://pypi.org/project/pypdf/6.21.4/ ; https://pypi.org/project/pypdf/7.1.1/ ; https://pypi.org/project/pdfplumber/0.11.11/ ; https://github.com/py-pdf/pypdf/blob/main/docs/user/extract-text.md
