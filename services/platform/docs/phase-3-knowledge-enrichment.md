# Phase 3: knowledge enrichment and persistence

## Scope

Phase 3 enriches a completed Phase 2 document with deterministic metadata, evidence-backed
Project DNA, OpenAI embeddings, and one atomic Snowflake persistence operation. It does not
add chunking, retrieval, FAISS, knowledge graphs, API endpoints, background jobs, or agents.

## Architecture

The `knowledge_enrichment` bounded context follows the same Clean Architecture direction:

- `domain` owns immutable profiles, grounded claims, evidence references, Project DNA,
  embedding records, bundles, and stable failures.
- `application` owns metadata extraction, embedding-target construction, external ports,
  and the Phase 3 orchestration service.
- `infrastructure` owns OpenAI Structured Outputs, embeddings, exact token counting, and
  transactional Snowflake adapters.
- `bootstrap/enrichment.py` is the composition root. Phase 3 is not activated during normal
  API startup and therefore cannot make accidental external calls.

Import-linter contracts prevent domain and application code from depending on OpenAI,
Snowflake, tokenization, or infrastructure implementations.

## Metadata extraction

The metadata profile uses a deterministic UUID derived from the source identifier and
SHA-256 document fingerprint. It records native document metadata, format, size, section,
character, and word counts. Reprocessing identical content produces the same document ID.

## Project DNA

GPT-4.1 uses the pinned `gpt-4.1-2025-04-14` snapshot and the Responses API Structured
Outputs interface. The strict schema captures project identity, client, industry,
engagement, summary, challenges, use cases, capabilities, technologies, data sources,
cloud platforms, outcomes, differentiators, and named experts.

Every populated claim requires one or more exact source quotes and section numbers. The
application normalizes whitespace and verifies those quotes against Phase 2 sections.
Missing evidence must produce null or an empty collection; invented evidence fails the
whole run before embeddings or persistence. Document content is serialized as untrusted
JSON and the system prompt explicitly prevents following embedded instructions.

## Embeddings

Each non-empty Phase 2 section and the canonical Project DNA text receives a stable,
content-addressed embedding ID. Requests use `text-embedding-3-large`, 3,072 dimensions,
float encoding, exact token limits, deterministic input order, bounded batches, and strict
response-count, dimension, and finite-number validation.

Semantic chunking remains deferred. Oversized sections fail explicitly instead of being
silently truncated. The container image warms the required `tiktoken` vocabularies during
build and copies the cache into the non-root runtime image, avoiding hidden runtime
downloads.

## Snowflake persistence

Migration `migrations/003_phase_3_enrichment.sql` creates:

- `PROJECTS` for stable project identity and the current DNA pointer;
- `DOCUMENTS` for versioned document metadata and extraction warnings;
- `DOCUMENT_SECTIONS` for citation-ready source text;
- `PROJECT_DNA` for versioned JSON intelligence and model provenance;
- `EMBEDDINGS` with `VECTOR(FLOAT, 3072)` values;
- `ENRICHMENT_RUNS` for completed-run audit records.

The repository validates database and schema identifiers against an allowlist and binds
all data values. It uses `MERGE` for stable aggregates and replace-within-transaction for
derived sections and embeddings. Connections disable autocommit, set a query tag, commit
only complete bundles, roll back Snowflake failures, and always close cursors and sessions.
Snowflake does not support binding VECTOR values directly, so vectors are bound as JSON and
cast server-side to the fixed vector type.

## Configuration and secrets

All configuration uses `BLEND_BRAIN_` environment variables listed in `.env.example`.
For laptop use, OpenAI keys and Snowflake passwords or private-key passphrases belong
only in the ignored `.env` file and must never enter source control. A managed secret
store can be selected later. Key-pair authentication is supported and preferred for
service identities.

## Testing

Tests use typed fake OpenAI resources and DB-API Snowflake connections. They verify schema
parsing, prompt-injection boundaries, citation grounding, input limits, batching, ordering,
invalid vectors, error translation, deterministic IDs, composition, bound SQL, commits,
rollbacks, connection closure, identifier safety, and migration contents. No live API or
database credentials are required for the unit quality gate.

## Acceptance criteria

- Metadata identity and statistics are deterministic and typed.
- Project DNA cannot persist without verifiable section evidence.
- Every eligible section and Project DNA aggregate receives a validated embedding.
- One Snowflake transaction persists the complete bundle idempotently.
- Model, prompt, checksum, timestamps, and run provenance are retained.
- Ruff, strict mypy, architecture contracts, tests, coverage, and lockfile checks pass.

## Future considerations

Later phases can add semantic chunking, asynchronous orchestration, failed-run audit events,
multi-document Project DNA synthesis, human approval and correction history, FAISS export,
retrieval, knowledge graph construction, and evaluation datasets without changing Phase 3
ports or domain ownership.
