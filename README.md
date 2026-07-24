# Blend Knowledge Brain

Enterprise organizational intelligence platform for Blend360.

Implemented phases currently include the production backend foundation, document
ingestion, metadata extraction, evidence-backed Project DNA, OpenAI embeddings,
Snowflake persistence, scoped hybrid retrieval, grounded question answering, and the
professional React intelligence workspace. Phase 6 adds a deterministic evidence-backed
knowledge graph, scoped Project DNA similarity, and evidence-aware Expert Finder. Agent
workflows remain deferred to their approved phase. Phase 7 adds deterministic knowledge
gap detection and a scoped, independently reviewed knowledge-capture lifecycle with
durable approved facts. Phase 8 adds grounded proposal and project one-pager generation
with durable citations and private draft-watermarked PDF export.

See [`services/platform/README.md`](services/platform/README.md) for backend setup and
verification instructions and [`apps/web/README.md`](apps/web/README.md) for frontend
setup and verification instructions.

## Run locally

Prerequisites: Python 3.13, [uv](https://docs.astral.sh/uv/), Node.js 22.12 or newer,
and npm 11 or newer.

Start the backend in one terminal:

```bash
cd services/platform
uv sync --all-extras
cp .env.example .env
uv run uvicorn blend_brain.bootstrap.application:create_app --factory --reload
```

Start the frontend in a second terminal:

```bash
cd apps/web
npm ci
cp .env.example .env.local
npm run dev
```

Open `http://localhost:5173`. Backend health is available at
`http://localhost:8000/health/live`, and API documentation is available at
`http://localhost:8000/docs` with the example local configuration.

Snowflake is disabled by default, so the API foundation runs without cloud credentials.
Features that use organizational data continue to show their designed unavailable state
until Snowflake is configured and authenticated read APIs are exposed. Generated PDFs
are written beneath `services/platform/.local/artifacts` by default.
