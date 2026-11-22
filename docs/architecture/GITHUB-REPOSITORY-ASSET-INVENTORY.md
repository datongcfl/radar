# GitHub Repository Asset Inventory Capability

## Purpose

Enumerate document and source-file candidates in one GitHub repository at a fixed commit. This is the repository-asset discovery layer between repository metadata search and document parsing.

## Contract

- Capability: `source/github-assets`, operation `inventory`.
- Required input: `repository` in `owner/name` form.
- Optional parameters: `ref`, `token`, `max_files` (1–10,000; default 2,000), `max_file_bytes` (1–20 MB; default 2 MB).
- Resolve the requested/default branch to a commit SHA, then inventory the recursive Git Tree for that immutable commit.
- Return typed candidate descriptors with path, blob SHA, size, media type, parser hint, and immutable GitHub blob URL.

## Classification and exclusions

The first version identifies Markdown, text, HTML, CSV, PDF, DOCX, XLSX, PPTX, common source and configuration files. It excludes generated/dependency directories (for example `node_modules`, `vendor`, `dist`, build output and virtual environments), unsupported extensions, and files above the configured size ceiling.

The extension classifier is deliberately a candidate hint, not a content assertion. The next ingestion stage must verify the bytes against the expected format before invoking a parser.

## Completeness and failure semantics

GitHub's `truncated=true` tree response yields `partial`, never complete success. API failures, invalid refs and malformed responses are explicit failures rather than empty success. A maximum-file ceiling produces a warning. No credentials are returned in records, warnings or metadata.

## Evidence boundary

Inventory records are `repository_asset_candidate` descriptors, not persisted domain Evidence. They identify a repository object at commit + path + blob SHA. No file body is fetched, no parser is invoked, and no Evidence or Assessment is created. A later ingestion stage must fetch and hash content, validate the blob/format, bind the candidate to Source/Asset records, and preserve parser-native locators.

## Limitations

The Git Trees API can truncate very large repositories. This first stage does not paginate/traverse subtrees to recover a truncated inventory, does not fetch Git LFS object contents, submodules, symlink targets, issue/PR discussions or CI records, and does not qualify repository assets against enterprise corpora.
