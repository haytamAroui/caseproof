# ADR 0026 — Structured CaseProof frontend foundation

Status: engineering candidate, owner-requested 1 November 2026; not M3/M4 acceptance or deployment permission.

Use React, Vite and strict TypeScript as a static client of the existing Python API. App owns routing/session/query composition. Features own task-specific UI/controllers/API adapters. Shared owns generated contracts, transport, session lifecycle and UI primitives. AST checks enforce import direction, feature public entry points and forbidden storage/network shortcuts. Negative controls must fail.

Verification and human decisions remain separate backend authorities (ADR 0011/0022). Python response projection generates JSON Schema and TypeScript; Ajv validates incoming reports and exact case/brief/snapshot binding. No verdict is recomputed in JavaScript. Future contract expansion must validate against canonical report fixtures. Existing routes and payloads remain compatible; no new DB, Auth or production route.

Memory-only host bridge uses the existing injected-session shape. Explicit session end and access rejection abort requests, clear query caches and unmount private screens. No service worker, remote assets, analytics or persistent token/draft cache. Reads reopen exact frozen snapshots. No consequential mutation is implemented; future writes require stable request IDs, server-confirmed receipts and uncertain-outcome behavior.

Viewer choice is deferred behind PageImageReader. Compare isolated server-rendered image overlays with current patched PDF.js on clean/scanned/rotated/CropBox files plus a separate 200-page workload. Preserve original/version/page/representation hashes and coordinate transforms. Do not accept screenshot appearance alone as mapping proof. Extend/shadcn reuse needs recorded licenses, keyboard/axe/manual screen-reader evidence.

No rewrite of temporary clients in this increment. Retain their tests until equivalent real client workflows pass. Rollback: remove the unmounted apps/web/client build and workflow; existing clients/backend unchanged. Synthetic Playwright transport, contract/import negative tests and cloud CI verify foundation only. Named security review, genuine signed browser workflow, representative accuracy and confidential-client gates remain open. Owner: frontend engineering; named independent reviewer pending.
