# Phase 2: document ingestion

## Scope

Phase 2 converts supported local files into one immutable normalized document model.
It supports PPTX, DOCX, PDF, Markdown (`.md` and `.markdown`), and TXT. Detection uses
both the filename extension and the document content or container structure.

OCR, chunking, embeddings, persistence, vector indexing, Project DNA, knowledge graph
generation, and API upload endpoints are intentionally outside this phase.

## Architecture

The `document_ingestion` bounded context follows Clean Architecture:

- `domain` owns immutable source, metadata, section, locator, warning, and error values.
- `application` owns parser, detector, and source-loader ports plus the ingestion use case.
- `infrastructure` implements bounded filesystem access, scanning, content detection,
  parser adapters, and local composition.

The application service accepts storage and parser ports. Another source adapter can
therefore replace the filesystem loader without changing extraction rules or domain
models. Import-linter contracts prevent domain and application code from depending on
parser libraries or infrastructure.

## Extraction behavior

- PPTX creates one section per slide and extracts positioned text, tables, and speaker
  notes. Slide numbers are retained for citations.
- DOCX preserves paragraph and table order and groups content under Word heading styles.
- PDF creates one section per page. Pages without digital text emit an OCR warning;
  wholly image-only PDFs fail explicitly rather than silently producing empty knowledge.
- Markdown preserves a preamble and splits sections at ATX headings.
- TXT uses UTF-8 first, supports BOMs, and falls back to bounded character-set detection.

Every result carries the original filename, storage-neutral source identifier, byte
size, SHA-256 fingerprint, normalized metadata, ordered sections, and non-fatal warnings.

## Safety and failure handling

The local adapter refuses symlinks and non-regular files. Default limits are 100 MiB per
file, 10,000 Open XML entries, 500 MiB expanded archive content, a 100:1 archive
compression ratio, and 2,000 PDF pages. Callers can inject stricter `IngestionLimits`.

Expected failures use stable typed exceptions: inaccessible, unsupported, invalid,
oversized, corrupt, encrypted, and empty documents. Parser-specific exceptions do not
escape the infrastructure boundary.

## Testing

Tests generate real Office and PDF documents in temporary memory or pytest directories.
They verify all formats end to end, metadata, tables, notes, headings, page locators,
legacy text encoding, detection mismatches, resource limits, scanning, and error mapping.
The repository continues to enforce Ruff, strict mypy, import contracts, and at least
90% branch coverage.

## Acceptance criteria

- All five requested document families are detected and extracted.
- Results use one immutable, typed model with citation-ready source locators.
- Mislabelled, corrupt, encrypted, empty, binary-text, and oversized inputs fail safely.
- Filesystem discovery is deterministic and excludes hidden files and symlinks by default.
- Dependencies are locked and all automated quality gates pass.

## Future considerations

The next ingestion phases can add OCR, semantic chunking, remote sources, malware scanning,
asynchronous job execution, durable manifests, Snowflake loading, and vector indexing
through new adapters and workflows without changing the Phase 2 domain contract.
