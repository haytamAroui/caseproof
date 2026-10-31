# PostgreSQL recovery and hosted MCP/OAuth — engineering acceptance

Date: 31 October 2026. Scope: additive optional read-only MCP host and an actual two-process PostgreSQL worker acceptance. **Neither component has been approved or deployed in production.**

## 1. Real PostgreSQL process recovery

Run `scripts.verify_page_worker_postgres_process` **only** after initializing the disposable CI database with `scripts.verify_dossier_disposable`. The harness refuses any non-localhost connection, any database other than `caseproof_s2_ci`, or a missing `CASEPROOF_DISPOSABLE_DB=YES` flag.

The harness creates four independently identified, hash-bound PDF sources (50 pages each; 100 normal PDF pages, 100 image-only), an authorized synthetic actor/matter grant, and the actual canonical page-job SQL RPC. It launches Worker A as an operating-system process; the 120th committed PostgreSQL artifact forces `os._exit(137)`, leaving the lease owned by a dead worker. The parent confirms that a second claim is denied before expiration. **Only in the disposable fixture**, it advances the database lease expiry, claims with a fresh token, and verifies that the stale token cannot write, heartbeat, finish, or yield. Worker B starts as another OS process and resumes the **same actual PostgreSQL job**, without repeating the committed checkpoints. It must validate all 200 source/page identities, state/OCR-path flags, sealed receipt readbacks, exactly 200 committed results and put-audit rows, exactly three claim transitions (A, explicit fenced takeover, B), active lease denial, and loss of read access after the grant is revoked.

**Boundaries:** This uses synthetic actor claims injected under PostgreSQL's `authenticated` role, not genuine live OAuth or Supabase Auth. The test deliberately manipulates its **isolated disposable lease clock**, not a live database. OCR may return an explicit `ocr_unavailable` state; this proves safe processing/recovery, not OCR quality or legal accuracy. No production scaling, live queue orchestration, external tenant load, independent security audit, or live service proof is claimed.

## 2. Hosted stateless MCP resource-server integration

`apps/api/hosted_mcp_app.py` is an independent FastAPI factory rather than a route silently exposed by the existing loopback development API. It implements a bounded JSON-RPC POST `/mcp` with the July 2026 MCP stateless protocol version, tool discovery, a closed list of exactly two read-only canonical tools, protocol/version/method/name header binding, strict argument validation, no session identifier or GET stream, no cookies or query credentials, and a pinned `Origin` allowlist. The public OAuth resource discovery endpoint is `/.well-known/oauth-protected-resource`; missing or rejected credentials receive a resource-metadata `WWW-Authenticate` challenge. Responses are private and `no-store`.

`apps/api/supabase_oauth_mcp_verifier.py` uses a project-pinned `/auth/v1/user` verification call for **every** bearer. It requires the signed `client_id` to be in an explicit, non-empty host allowlist of approved OAuth clients, plus the actual Supabase token's `aud='authenticated'`, original issuer and an asymmetric algorithm. It rejects wrong token kind, unknown OAuth clients, mismatched/anonymous/deleted user and invalid lifetime. Signature validation is provided by the project Auth service, **not** by locally decoding claims. The original bearer is passed to the Supabase RLS boundary **unchanged**.

**Supabase compatibility correction:** Its OAuth authorization server currently supports `openid`, `email`, `profile` and `phone` standard scopes; it does **not** yet support arbitrary `caseproof:reports:read` OAuth scopes. The CaseProof read permission and MCP resource binding are **host policy-derived**, after signature-verified approved `client_id`, not claims asserted to originate from Supabase. Standard OAuth scopes do not grant legal matter access. OAuth client consent/registration and CaseProof document disclosure are **separate** gates.

The deployment must inject a trusted, server-side `HostContentGate` which checks *current* actor, **OAuth client**, matter, brief, snapshot, approved destination, and revocation **for every tool call**, returning a short-lived `ContentRelease` bound to the exact bearer and destination. `CallbackHostContentGate` is a concrete adapter with a short (60-second) release, accepting a trusted, fresh per-call consent lookup; no built-in durable registry or open grant is assumed. There is intentionally **no global consent boolean**, no model-selected user/tenant or destination, no write/approval tool, no anonymous access, and no bypass of downstream current dossier grants. Missing host consent or missing dossier store denies content. The host factory can be composed and tested without exposing it or issuing real OAuth credentials.

## 3. Required acceptance and release gates

- Disposable CI `postgres-real-process` and `hosted-mcp` jobs must pass against the **exact PR head**, along with existing locked full suite, Ruff, architecture, canonical REST/MCP parity, and page-worker regressions. Capture the uploaded `postgres-real-process-recovery-receipt` JSON.
- Configure a real Supabase OAuth 2.1 authorization server, consent UI and client registration. Confirm the JWT issuer, `aud='authenticated'`, signed `client_id`, expiration and revocation semantics, and verify the pinned Auth endpoint proves its signature. Approve each client ID in the host-side CaseProof MCP read-only policy and in existing RLS policies as appropriate; avoid unsupported custom scopes. **This compatibility has not been demonstrated** on a hosted issuer.
- Implement, approve and audit the real per-matter/per-destination `HostContentGate` policy backed by current host permission state. Test consent granting/revoking, ungranted/foreign owner, same-organization different matter, expired release, stale snapshot and real signed Auth-to-Supabase RLS access using only least-privilege runtimes.
- Run external HTTPS hosting acceptance behind an approved reverse proxy with correct public canonical URL, origin limits, security headers, hostile clients, rate limits, capacity, network egress and backpressure. Verify no raw document bytes, tokens or user identifiers enter logs, traces, artifacts or model providers without explicit lawyer authorization.
- Independent bar/professional secrecy, privacy, security, and deployment review are required before real client documents or public hosting. No production migration, customer-data permission or commercial release is made by this change.

## Authoritative references

- [MCP Streamable HTTP transport, 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports)
- [MCP authorization and OAuth protected resource metadata](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization)
- [Supabase OAuth server setup](https://supabase.com/docs/guides/auth/oauth-server/getting-started)
- [Supabase Auth JWT signing and verification](https://supabase.com/docs/guides/auth/jwts)
- [RFC 9728 — OAuth 2.0 Protected Resource Metadata](https://www.rfc-editor.org/rfc/rfc9728)

- [Supabase OAuth scopes, client_id and RLS](https://supabase.com/docs/guides/auth/oauth-server/token-security)
