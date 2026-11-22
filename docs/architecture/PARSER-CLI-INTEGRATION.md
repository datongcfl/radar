# Local Document Parser CLI

The `radar parse` command invokes one parser capability against a local file and writes a JSON result to stdout.

```bash
radar parse --file ./requirements.docx
radar parse --file ./workbook.xlsx
radar parse --file ./deck.pptx
radar parse --file ./architecture.md
```

Use `--format` to override extension-based selection (`auto`, `text`, `pdf`, `docx`, `xlsx`, or `pptx`). Optional Office/PDF dependencies remain lazy: selecting one parser does not import or install the others. If its dependency is absent, the result is `unavailable` with an install hint.

Each output contains a status, parser name, document fragments, warnings, optional error, and parser metadata. The default source URI is the resolved local `file://` URI; use `--uri` to supply a stable external URI. `--max-bytes` enforces a file-size limit before reading bytes into memory.

This is a local parse operation, not a repository crawler or an evidence decision. It does not create Asset/Evidence/Assessment records, infer business relationships, or persist the output. All parser results remain `document_fragment` observations. The caller must separately validate source identity, persist provenance, and apply Evidence policy.
