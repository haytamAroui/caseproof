# CaseProof frontend foundation

Real client foundation: React, Vite and strict TypeScript, composed around existing Python application services. Temporary finance/ClearBrief clients are retained as regressions; no production route is enabled.

Run npm ci, npm run dev (loopback only). Vite proxies /v2 to 127.0.0.1:8000 in development. A trusted host supplies window.caseproofSession with getBearer(): Promise<string>; no token paste, browser storage or mock session fallback exists. Connect session only enables requests; the backend decides authorization. No actual authentication provider or confidential-client deployment is installed.

Production build: npm run build. Deploy dist at /workspace/ with SPA fallback and the response headers in security-headers.conf; proxy /v2 to the existing API. Vite preview headers test the built app but are not a production server configuration. No Python dev API is exposed automatically.

App composes features. Features expose index.ts; shared code depends inward. npm run lint includes AST import-boundary checks with deliberate negative controls. No cross-feature internals, persistent storage, eval or ad-hoc fetch. Query defaults disable retries, persistence and focus refetch; session invalidation clears queries and cancels fetches.

Generate schema: from repo root, uv run --locked python -m scripts.generate_frontend_contract. Then here npm run contracts:generate. CI checks both outputs. The Python projection is additive validation for fields consumed by this client, not a replacement verifier or complete schema for all legacy dossier fields. Unknown enum values fail closed. Future fields must be added to this contract before UI use.

First slice: read-only frozen report route /workspace/matters/:case/briefs/:brief?snapshot=:sha. Selection and four dimension displays consume existing values; no verification, review, correction or export business logic is copied. Viewer engine remains unselected; PageImageReader isolates the later adapter. No React UI kit source has been copied yet.

Checks: npm run contracts:check; npm run lint; npm test; npm run build; npm run test:e2e. Browser tests use explicit synthetic transport fixtures: not live Auth, independent screen-reader testing or whole M3 acceptance. Next slices: signed host integration, viewer hard-case comparison, user-created matter/intake, review/correction/export workflows. See docs/adr/0026-frontend-foundation.md.
