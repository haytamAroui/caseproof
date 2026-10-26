# Real CaseProof development test users — no frontend required

**Runbook dated 2026-10-26** · project: `caseproof-dev` / `ldwmocpxwskvhoojndrd`, EU central. **Never use AZComply's Supabase project.**

## Observed live state

Read-only Supabase inspection found **zero** real Auth users, organization memberships, cases, documents and document versions. The installed migration is only `20261022001009 caseproof_tenant_foundation`. Seven tables have RLS enabled, but installed **case/document/version SELECT predicates are organization-wide** and do not require the exact per-case private grant defined in **ADR-0017**; **no private Storage bucket** exists. Auditing and idempotency tables have RLS with no client policies (default deny), which the Security Advisor reports informationally.

**Consequence:** Existing green M1-A/M2-A engineering tests do **not** establish authenticated M1-B or M2-B. Do not use client-confidential data, authorize uploads or claim professional-secrecy protection. No real migrations, storage resources or test users were added by this audit.

## Option A — automatic ephemeral users (recommended; no password storage)

The manual GitHub Actions workflow now supports `mode: ephemeral` and uses the **supported Supabase Auth Admin API** to create **two distinct confirmed disposable users** with reserved `@example.com` test emails and cryptographically generated 36-byte random passwords. Passwords stay in runner memory only; they are **not** stored in GitHub secrets, code, job outputs, files, logs or chat. The existing genuine password sign-in/remote JWT verification/tampered-signature probe then runs, and the action **deletes both users in a `finally` cleanup**. A cleanup failure fails the job and requires manual inspection of the Supabase Auth dashboard.

**Before any live run:** Go to GitHub CaseProof → Settings → Environments → `caseproof-dev-live-auth`. Use **Deployment branches and tags → Selected branches and tags → only `main`**. Require independent environment reviewers when available, disable admin bypass, and preserve branch protection. See [the binding S2-006 security rules](../tasks/S2-006.md). **Never use repository- or organization-level Actions secrets here**: another workflow on an unreviewed branch could access them. If credentials were added there, move them into the protected environment and rotate the admin key before running.

**Two protected environment secrets are required; this connector cannot set or read GitHub secrets:**

- `CASEPROOF_DEV_PUBLISHABLE_KEY`: active `sb_publishable_` API key of **caseproof-dev**, not another project.
- `CASEPROOF_DEV_AUTH_ADMIN_KEY`: **server-side** CaseProof dev Auth-admin-capable key, preferably a new dedicated `sb_secret_` key or an appropriately scoped legacy service-role key if required by the GoTrue Admin API. **Never expose this key to frontend, PR workflows, logs or external services.**

After human review and merge of PR #72, open **GitHub → caseproof → Settings → Environments → caseproof-dev-live-auth → Environment secrets** and configure both. Then run **Actions → CaseProof dev real Auth smoke → Run workflow → main → mode: ephemeral**. It provisions, checks, and attempts to delete users in one workflow. **Do not store test-user passwords as literal YAML or repository secrets**; the workflow generates them when needed.

This verifies actual signed Auth logins only. It does NOT fix the existing organization-wide RLS, create matter grants, enable private storage or make M1-B/M2-B production-ready.

## Option B — two manually provisioned test users

1. Open the [CaseProof dev Supabase Auth Users dashboard](https://supabase.com/dashboard/project/ldwmocpxwskvhoojndrd/auth/users) (**verify** the project name is `caseproof-dev`). Use **Authentication → Users → Add user** and the supported manual create-user / invitation flow available in that dashboard. Provision **two different** test identities using email addresses you control (A: reviewer, B: same-organization ungranted reviewer); use strong distinct passwords and confirm both addresses through Supabase Auth's supported flow. If invitation flow is used, follow it to set passwords. Do not create passwords/rows through `auth.users` SQL.
2. In GitHub `haytamAroui/caseproof` use **Settings → Environments → caseproof-dev-live-auth → Environment secrets** and create these **environment-only secrets** (not repository or organization secrets) (never put these secrets in source code, issues, chat, CI logs or `.env` in git):
   - `CASEPROOF_DEV_PUBLISHABLE_KEY` — enabled **sb_publishable_** key from **CaseProof dev** project's API keys (NEVER use a secret, service-role or AZComply key).
   - `CASEPROOF_DEV_AUTH_A_EMAIL` and `CASEPROOF_DEV_AUTH_A_PASSWORD`
   - `CASEPROOF_DEV_AUTH_B_EMAIL` and `CASEPROOF_DEV_AUTH_B_PASSWORD`
3. From **GitHub Actions → CaseProof dev real Auth smoke → Run workflow → main**, run the manual workflow. It calls the existing `scripts/verify_s2_006_live_auth.py`: signs in to the **pinned dev project** with both users; makes the server verify two signed sessions and checks a tampered JWT signature is rejected. It logs **only a pass/fail receipt**, not token, subject or email. The job is manual, verifies the trusted repository and `refs/heads/main`, explicitly selects the protected environment, and checks out `main`. Verify that the environment itself restricts deployment to **main only**, too.
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
