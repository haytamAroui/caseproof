# ADR 0036 — Firm-controlled pilot profile

**Date:** 6 November 2026. **Status:** Proposed. Haytam recorded the owner
decisions below. Profile acceptance, pilot approval and deployment authorization
remain pending. Extends [ADR 0025](0025-deployment-data-retention-and-model-authority.md).
[ADR 0034](0034-release-completeness-policy.md) governs reviewed-release completeness.

## Current implementation

At `79c6aee`, `git grep -il supabase 79c6aee -- '*.py'` finds 116 Python
files (32 in `apps/`, 46 in `scripts/`, 37 in `tests/`, and one kernel
docstring). The apparent Supabase package import is a source string passed to
the architecture scanner by `tests/test_hexagonal_boundaries.py`. Runtime
coupling comes from direct HTTPS calls, application adapter imports,
`CASEPROOF_DEV_*` configuration, and SQL role and grant contracts.

At that commit, the same search finds no matches under `application/`,
`domains/` or `infrastructure/`. The disposable filesystem, Postgres evidence
reader and vault ledger are scaffolding. A firm-controlled runtime still needs
adapter wiring, end-to-end verification and independent review.

## Proposed boundaries

- Define application-owned ports for storage (originals and derivatives),
  relational persistence and identity. Supabase remains the development and
  test default. The firm-controlled profile adds PostgreSQL and filesystem
  adapters behind those ports.
- Require a synthetic end-to-end CI run with no `SUPABASE_*` or
  `CASEPROOF_DEV_*` credentials. Run the services inside a network-isolated
  boundary and record outbound connection attempts at socket level, failing
  the check on any unexpected attempt. Use Unix sockets for internal service
  communication where needed. Test login, processing, retry, correction,
  export and reopen. The isolated test establishes connection behavior within
  its perimeter. Field-level egress evidence requires a separate test.
- Make the development and local profile checks required on `main` when
  available. Phase in an architecture guard for new Supabase SDK imports and
  new direct Auth, REST or Storage endpoint calls outside designated adapters.
- Specify retention transitions, legal holds and deletion for originals,
  derivatives, OCR output and backups. Document and test backup, restore and
  re-deletion procedures before re-enabling scheduled dev purging.

## Owner decisions recorded on 6 November 2026

| Decision | Disposition |
| --- | --- |
| Dev reaper | Remove the daily 02:43 UTC trigger and keep manual dispatch against `caseproof-dev`. Re-enable scheduling only after retention and recovery approval. |
| Pilot identity | Supabase Auth is accepted for synthetic or rights-cleared pilots with written disclosure of identity, membership and grant data. Keep matter names and grants outside Supabase or pseudonymize them. Prioritize a firm-controlled identity adapter if a firm declines hosted identity. |
| Security owner | Haytam is accountable. Real client evidence requires independent review. |
| Client uploads | Classify as `CLIENT_UPLOAD` and `CLIENT_CONFIDENTIAL`. Permit `process` only with a recorded reference to firm authorization, such as a contract or data processing agreement. Default `indexForSearch` and `useAcrossMatters` to false. Restrict export to the matter's own dossier. Obtain Belgian legal review of controller and processor allocation. |
| Rights changes | Use a server-checked typed `rights:manage` permission. Record a new policy version and audit event on each change. Pilot changes require one authorized actor. |

## Real client evidence gates

Use synthetic or rights-cleared material until the local profile check is green
and required on `main`, the firm approves the deployment and identity boundary
in writing, a Belgian lawyer reviews the data terms, an independent reviewer
assesses authentication, storage, access and backups, and retention, end-of-pilot
deletion and incident notification are documented and tested. Scope the first
real-client pilot to one team, one or two firm-selected matters, named users,
an immediate access cut-off and written deletion confirmation.

## Module appendix

| Boundary | Current code |
| --- | --- |
| App composition | [Development entry](../../apps/api/dev_live_entry.py) and [router wiring](../../apps/api/litigation_development_app.py) |
| Identity | [Workspace auth](../../apps/api/workspace_auth.py) and [Auth user verification](../../apps/api/supabase_auth_verifier.py) |
| Storage | [Signed originals](../../apps/api/signed_supabase_originals.py) and [source library](../../apps/api/signed_supabase_source_library.py) |
| Persistence | [Dossier journey and RPC client](../../apps/api/dossier_journey.py) and [headless matter store](../../apps/api/supabase_headless_matter_store.py) |
| Deployment and retention evidence | [Evidence runbook](../security/DEPLOYMENT_EVIDENCE_RUNBOOK.md) and [retention design](../security/RETENTION_DESIGN.md) |

### HTTP endpoint inventory at `79c6aee`

The following 15 API modules contain literal Supabase Auth, REST or Storage
endpoint paths. Review each before forming the guard allowlist.

`dossier_draft_revisions`, `dossier_journey`, `litigation_live_journey`,
`litigation_live_roundtrip`, `signed_page_jobs`,
`signed_supabase_matter_catalog`, `signed_supabase_originals`,
`signed_supabase_source_library`, `supabase_auth_verifier`,
`supabase_headless_matter_store`, `supabase_oauth_mcp_verifier`,
`supabase_password_signin`, `workspace_auth`, `workspace_intake`,
`workspace_reports`.

`litigation_development_app` also couples to Supabase through adapter wiring,
browser configuration and content-security-policy destinations. The other 16
API files with mentions need individual review. The 46 script and 37 test
matches identify inventory scope. Existing dev acceptance stays on Supabase.
The SQL audit still needs to cover provider-specific assumptions beyond roles
and grants.

## Reviewed export integrity audit

The [reviewed release router](../../apps/api/dossier_export_release.py) creates
one manifest for DOCX, JSON and Markdown. It covers each artifact's digest and
length, then records `manifest_sha256` and an HMAC-SHA256 receipt. Release replay,
listing, status and downloads recheck the manifest and receipt. Downloads also
check the artifact bytes against the manifest.

The [dossier journey](../../apps/api/dossier_journey.py) has a separate direct
export endpoint for all three formats and a historical snapshot endpoint. The
direct endpoint generates artifact checksums without creating a reviewed release.
Historical snapshot reopening verifies its own frozen report and receipt.
Reopening an already released artifact uses the reviewed release router.

The development entry supplies `CASEPROOF_DEV_AUTH_ADMIN_KEY` as the trusted
ingest secret. The dossier store derives the receipt key in process using a
domain-separated HMAC. Verification uses one configured key and the manifest
carries no key ID. The audited code has no old-key verification path, so rotating
the configured secret would invalidate existing receipt verification. Before
pilot operation, define dedicated receipt-key custody and rotation with retained
verification keys and backward-compatible reopening. The current receipt provides
shared-secret integrity verification by the service.
