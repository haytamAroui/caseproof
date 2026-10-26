# Real CaseProof development test users — no frontend required

**Runbook dated 2026-10-26** · project: `caseproof-dev` / `ldwmocpxwskvhoojndrd`, EU central. **Never use AZComply's Supabase project.**

## Observed live state

Read-only Supabase inspection found **zero** real Auth users, organization memberships, cases, documents and document versions. The installed migration is only `20261022001009 caseproof_tenant_foundation`. Seven tables have RLS enabled, but installed **case/document/version SELECT predicates are organization-wide** and do not require the exact per-case private grant defined in **ADR-0017**; **no private Storage bucket** exists. Auditing and idempotency tables have RLS with no client policies (default deny), which the Security Advisor reports informationally.

**Consequence:** Existing green M1-A/M2-A engineering tests do **not** establish authenticated M1-B or M2-B. Do not use client-confidential data, authorize uploads or claim professional-secrecy protection. No real migrations, storage resources or test users were added by this audit.

## Provision two REAL dev-only users, without SQL shortcuts

1. Open the [CaseProof dev Supabase Auth Users dashboard](https://supabase.com/dashboard/project/ldwmocpxwskvhoojndrd/auth/users) (**verify** the project name is `caseproof-dev`). Use **Authentication → Users → Add user** and the supported manual create-user / invitation flow available in that dashboard. Provision **two different** test identities using email addresses you control (A: reviewer, B: same-organization ungranted reviewer); use strong distinct passwords and confirm both addresses through Supabase Auth's supported flow. If invitation flow is used, follow it to set passwords. Do not create passwords/rows through `auth.users` SQL.
2. In GitHub `haytamAroui/caseproof` use **Settings → Secrets and variables → Actions** and create these **repository or protected environment secrets** for the reviewed main branch only (never put these secrets in source code, issues, chat, CI logs or `.env` in git):
   - `CASEPROOF_DEV_PUBLISHABLE_KEY` — enabled **sb_publishable_** key from **CaseProof dev** project's API keys (NEVER use a secret, service-role or AZComply key).
   - `CASEPROOF_DEV_AUTH_A_EMAIL` and `CASEPROOF_DEV_AUTH_A_PASSWORD`
   - `CASEPROOF_DEV_AUTH_B_EMAIL` and `CASEPROOF_DEV_AUTH_B_PASSWORD`
3. From **GitHub Actions → CaseProof dev real Auth smoke → Run workflow → main**, run the manual workflow. It calls the existing `scripts/verify_s2_006_live_auth.py`: signs in to the **pinned dev project** with both users; makes the server verify two signed sessions and checks a tampered JWT signature is rejected. It logs **only a pass/fail receipt**, not token, subject or email. The job is manual **and restricted to `refs/heads/main`** so PR branches cannot execute it with secrets.
4. If the action fails, inspect the high-level failure category only; do **not** print JWTs, passwords, provider JSON, or full requests. Check both emails are confirmed and credential names/keys match. The script refuses legacy JWT anon keys and privileged secret keys by design. Rotate these disposable passwords after tests.

## Gates this DOES and DOES NOT satisfy

| Gate | Successful result establishes | Still separately open |
|---|---|---|
| Real signed session smoke, S2-006 | 2 *actual dev Supabase Auth* password logins, correct issuer, distinct subjects, remote signature validation and tamper rejection | No database membership, RLS, storage, service sessions, audited review or tenant isolation |
| M1-A | Engineering-policy tests already pass on main | ADR-0017 private-case transition human review |
| M1-B | **NOT YET PASS** | Canonical reviewed matter-grant / case-document-version RLS, real DB-backed identity and grants, private immutable bucket, worker/persistence, OCR, atomic exhibits, signed multi-user negative tests and recovery |
| M2-A | Engineering tests already pass on main | No real client storage or legal conclusion authorized |
| M2-B | **NOT YET PASS** | Authenticated persisted brief/check/reviewer CAS plus end-to-end recheck in real isolation |
| M1-C / M2-C | Nothing new | Operational security/customer release and later UX; not required for the engineering milestones |

**Next security acceptance after real logins:** review/install a canonical **litigation-only default-private** grant policy on dev (issue [#64](https://github.com/haytamAroui/caseproof/issues/64)) and test **A-only vs B-ungranted matters within one org**, an unrelated org, revocation, missing actions, denied evidence URLs, atomic audit failure, revoked/stale sessions and worker delegation with real signed identities; use [#68](https://github.com/haytamAroui/caseproof/issues/68) for the complete headless M1-B gate. Do not assume the present organization-only policies become private merely by creating two users.

**Security rules:** No service-role secrets in the client/test JWT path. No direct `auth.users` insert, no seeded privileges without approved audit, no production migrations, no fake `SET request.jwt.claim.sub` test passed off as signed identity. A frontend is not needed for these headless tests.

**Supabase references:** [User management](https://supabase.com/docs/guides/auth/users), [password-based Auth](https://supabase.com/docs/guides/auth/passwords), [Admin create user](https://supabase.com/docs/reference/javascript/auth-admin-createuser).
