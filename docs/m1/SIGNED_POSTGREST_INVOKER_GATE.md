# M1 — signed Supabase Auth → limited private matter PostgREST reads

**27 October 2026. Engineering proposal; NOT installed on `caseproof-dev`.**

## Why this is necessary

The signed `SignedPrivateMatterReader` currently expects a permanent database login. The owner explicitly rejected putting database-owner DSN/password/CA secrets into GitHub Actions. We can instead use Supabase's **existing authenticated PostgREST endpoint**, which performs trusted JWT verification and sets the Postgres `authenticated` role and `auth.uid()`. The live M1 exact-grant RLS policies can then apply through a narrow **`security_invoker` view** on PostgreSQL 17. No new GitHub owner/administrator password or `service_role` read is introduced.

This must **not** be confused with signed live acceptance before actually installing and running it with genuine users and positive/negative seeded grants. The candidate is an authorization surface increase and requires independent security review.

## Read-only proposed API

[Candidate SQL](../../db/proposals/PIV-M1_signed_invoker_read_api_candidate.sql) creates exactly two views in already exposed `public`:

| View | Response | Permission enforcement |
| --- | --- | --- |
| `public.caseproof_private_matters` | Case UUID, org, revision, scope revision, manifest revision, state | Underlying `caseproof.cases` current actor + current exact-case grant RLS |
| `public.caseproof_private_source_versions` | Org/case/document/version IDs, SHA-256 digest, original byte count, MIME type, version | Both `documents` and `document_versions` per-matter evidence read RLS |

Both use `WITH (security_invoker=true, security_barrier=true)`, grant **SELECT only** to `authenticated`, and explicitly revoke all from `anon` and `PUBLIC`. They cannot write a case, fetch an original byte, create a grant, list other organizations' cases or read M2 privileged review/audit journals. We **never expose** the full private `caseproof` schema via the Data API.

Before installation the candidate checks the exact recognized M1 policy **(table, name)** pairs, RLS and client table privileges. If private grants are absent, rogue policy added, or a view name already exists, the entire transaction fails.

## Normal signed-user flow after review/installation

1. User signs in via the normal pinned **CaseProof-dev Supabase Auth** provider and obtains an actual access token.
2. App/Word component makes ordinary `GET /rest/v1/caseproof_private_matters?select=*` or `GET /rest/v1/caseproof_private_source_versions?case_id=eq.<uuid>&select=*` with the project's public/publishable API key and `Authorization: Bearer <user_access_token>`.
3. Supabase validates JWT and invokes PostgreSQL under `authenticated`; `security_invoker` forces the user's RLS onto the underlying `caseproof` relations. No `SET request.jwt.claim.sub` is submitted by the app. Only a currently active case grant yields a result.
4. The app must separately authorize and resolve **immutable original bytes** via an approved private Storage pathway and recheck scope/revisions. This read-only API only lists metadata.

## Testing status

- [Disposable PostgreSQL workflow](../../.github/workflows/m1b-signed-invoker-views.yml) actually tests the SECURITY INVOKER RLS behavior, allowed matter/versions, same-org private case denial, foreign-org denial, missing subject, revoke case/evidence actions, no anon reads and no mutations.
- **That CI sets synthetic SQL claim context** to test RLS and is NOT a signed Supabase Auth test. Use the existing protected real Auth workflow later to test signed PostgREST, after independently reviewed deployment and actor-audited grants. **No customer evidence** is permitted by this candidate.
- Live verification in the same conversation through connected **Supabase MCP** found `20261027160745` installed, four private M1 SELECT policies, zero Auth users/matters, and zero M2 tables. Nothing was changed on `caseproof-dev`.

Sources: [Supabase Views — security_invoker](https://supabase.com/docs/guides/database/views), [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security).

## Explicitly not finished

Approved human actor matter-grant issuance/audit, real signed Auth integration against these *live* views, actual private object Storage source readback, real PDF/DOCX/OCR, durable authenticated exhibit confirmation, M2 persisted correction/recheck and independent security review are still required. M1-B/M2-B and M1-C/M2-C cannot be marked complete based on this PR.
