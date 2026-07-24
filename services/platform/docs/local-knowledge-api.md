# Local knowledge API and intelligence indexes

The local application exposes authenticated knowledge reads at `/api/v1`. A static bearer
credential is intentionally supported only for `local` and `test`; application validation rejects
this adapter in production, where corporate OIDC must replace it.

## Authorization boundary

- The server maps the bearer credential to a subject and a server-configured project allowlist.
- Snowflake catalog reads bind that allowlist into every query.
- Retrieval and intelligence FAISS indexes are built from the allowed corpus before search. Results
  are never globally searched and filtered afterward.
- The local wildcard (`["*"]`) is resolved by the server against persisted projects.

## Endpoints

- `GET /api/v1/dashboard`
- `POST /api/v1/questions`
- `GET /api/v1/projects/{project_id}`
- `GET /api/v1/projects/{project_id}/dna`
- `GET /api/v1/projects/{project_id}/similar`
- `POST /api/v1/experts/search`

## Graph and index catch-up

Run from `services/platform`:

```bash
../../.venv/bin/uv --cache-dir /private/tmp/blend-brain-uv-cache run \
  python -m blend_brain.bootstrap.knowledge_indexing
```

The command atomically projects every current DNA record missing a completed graph projection. It
then loads the authorized Snowflake section embeddings into the hybrid FAISS index and current
Project DNA embeddings into the similarity/expert FAISS index. Rerunning it is idempotent. Use
`--rebuild-graphs` only when projection logic changes.

The API maintains process-local, authorization-scoped immutable index snapshots. Restart the API
after a bulk ingestion completes so the running process rebuilds against the final corpus. Future
distributed deployment should replace this local invalidation step with an enrichment-completed
event and versioned index registry.

## Local runtime

Backend:

```bash
cd services/platform
../../.venv/bin/uv run uvicorn blend_brain.bootstrap.application:create_app \
  --factory --reload
```

Frontend:

```bash
cd apps/web
npm run dev
```

The backend `.env` and frontend `.env.local` must contain the same local bearer credential. Both
files are ignored by source control. Never place this static credential in a deployed browser
bundle.

## Evaluation gates

Automated tests verify missing/invalid authentication, project-level denial, strict response
contracts, source-quote citation validation, confidence calculation, unanswerable responses, and
scope-isolated index caching. Live smoke evaluation should include at least two answerable business
questions and one unrelated negative control after each final index build.
