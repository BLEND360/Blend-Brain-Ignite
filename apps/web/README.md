# Blend Knowledge Brain web application

Production React frontend for the Blend Knowledge Brain organizational intelligence
platform.

## Requirements

- Node.js 22.12 or newer
- npm 11 or newer

## Local development

1. Run `npm ci`.
2. Copy `.env.example` to `.env.local`.
3. Start the backend on the configured `VITE_API_PROXY_TARGET`.
4. Run `npm run dev`.

The application never falls back to embedded organizational data. Until the Phase 5
read APIs are exposed behind trusted authentication and authorization, affected views
show their designed unavailable state.

## Verification

- `npm run typecheck`
- `npm run lint`
- `npm test`
- `npm run build`

Architecture, API contracts, testing, acceptance criteria, and future considerations
are documented in [`docs/phase-5-react-frontend.md`](docs/phase-5-react-frontend.md).
