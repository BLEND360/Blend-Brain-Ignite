# Platform backend

This package is the backend platform for Blend Knowledge Brain. It currently
provides:

- validated environment configuration;
- structured JSON or console logging;
- request correlation;
- RFC-style problem responses;
- liveness and readiness endpoints;
- optional OpenTelemetry tracing;
- Clean Architecture dependency rules;
- unit and API tests;
- a non-root production container image;
- content-aware local document ingestion for PPTX, DOCX, PDF, Markdown, and TXT;
- normalized, source-addressable extraction results and file fingerprints;
- bounded file, archive, and PDF processing with stable ingestion errors;
- deterministic metadata profiles and evidence-backed Project DNA;
- batched `text-embedding-3-large` section and Project DNA embeddings;
- atomic, idempotent Snowflake persistence with a 3,072-dimension vector schema;
- authorization-scoped FAISS and BM25 hybrid retrieval with weighted RRF;
- GPT-4.1 structured question answering with literal source citations;
- application-computed confidence with an auditable component breakdown;
- deterministic, evidence-backed Project DNA knowledge graph projection;
- authorization-scoped Project DNA similarity with graph-derived explanations;
- evidence-aware Expert Finder over explicitly named project experts;
- deterministic Project DNA knowledge-gap detection;
- scoped human knowledge capture with bounded inputs;
- independently reviewed, optimistic-lock approval and approved-fact persistence;
- grounded proposal and project one-pager generation with strict templates;
- normalized business-artifact citations and idempotent Snowflake persistence;
- draft-watermarked ReportLab PDF export to a private local directory.

It deliberately excludes OCR, semantic chunking, public question-answering routes,
authentication/authorization, conversational memory, reranking, public organizational
intelligence routes, employee identity resolution, and agent workflows belonging to
later phases. It also excludes automatic publication of approved facts until a governed
re-enrichment workflow is implemented.
Generated business collateral also remains draft-only until a human review and
publishing workflow is approved.

## Requirements

- Python 3.13
- uv

## Local setup

From `services/platform`:

1. Synchronize the locked development environment with `uv sync --all-extras`.
2. Copy `.env.example` to `.env` and adjust local non-secret settings.
3. Run the API with `uv run uvicorn blend_brain.bootstrap.application:create_app --factory --reload`.

The API exposes:

- `GET /health/live`
- `GET /health/ready`
- OpenAPI documentation at `/docs` only when `BLEND_BRAIN_DOCS_ENABLED=true`

## Verification

Run:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy src tests`
- `uv run lint-imports`
- `uv run pytest`

## Configuration

All environment variables use the `BLEND_BRAIN_` prefix. Configuration is read once
at startup and validated. Keep local secrets in the ignored `.env` file and never
commit them. A managed secret store can be selected when deployment is designed.

## Document ingestion

Phase 2 architecture, usage, limits, error behavior, testing strategy, and acceptance
criteria are documented in [`docs/phase-2-document-ingestion.md`](docs/phase-2-document-ingestion.md).

## Knowledge enrichment

Phase 3 architecture, model safeguards, Snowflake schema, configuration, testing, and
acceptance criteria are documented in
[`docs/phase-3-knowledge-enrichment.md`](docs/phase-3-knowledge-enrichment.md).

## Hybrid retrieval and question answering

Phase 4 architecture, grounding safeguards, confidence semantics, configuration,
testing, and acceptance criteria are documented in
[`docs/phase-4-hybrid-retrieval-qa.md`](docs/phase-4-hybrid-retrieval-qa.md).

## Organizational intelligence

Phase 6 knowledge graph, Similarity Engine, Expert Finder, authorization boundaries,
configuration, testing, and acceptance criteria are documented in
[`docs/phase-6-organizational-intelligence.md`](docs/phase-6-organizational-intelligence.md).

## Governed knowledge lifecycle

Phase 7 gap detection, capture, persistence, approval state machine, security boundary,
testing, and acceptance criteria are documented in
[`docs/phase-7-knowledge-lifecycle.md`](docs/phase-7-knowledge-lifecycle.md).

## Grounded business artifacts

Phase 8 proposal generation, project one-pagers, grounding, persistence, local PDF export,
security boundaries, testing, and acceptance criteria are documented in
[`docs/phase-8-business-artifacts.md`](docs/phase-8-business-artifacts.md).
