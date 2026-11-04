# CaseProof P6 — actual development security catalog read-only inspection

**Observed:** 2026-11-04 10:31–10:40 UTC · **Project:** `caseproof-dev` (`ldwmocpxwskvhoojndrd`).
**Method:** Supabase connected service `get_advisors(type=security)`, `list_migrations`, and read-only SQL catalog metadata. No migrations, grants, policies, roles, customer data, production environment or passwords were changed or retrieved.

## Observations (scoped — not a vulnerability confirmation)

- Dev Supabase security adviser returned **29 INFO** notices `rls_enabled_no_policy` for tables including `caseproof.dossier_releases`, `caseproof.dossier_snapshots`, `caseproof.audit_events` and internal fixture tables. Catalog query confirmed RLS enabled on observed private caseproof tables; policies were absent for many private tables. This can be an intentional default-deny design. Independent grant/use review is required; **do not infer that policy absence permits access**. [Supabase rule](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy).
- Adviser returned **15 WARN** notices `authenticated_security_definer_function_executable` for public functions, including `public.caseproof_dev_bundle_manifest` and `public.caseproof_dev_correct_brief`. Executability alone is not proof of an exploit. Each exposed RPC requires independent review of effective actor checks, scoped grants, `search_path`, revocation, and concurrent access. Never blanket-convert to invoker or revoke without contract review. [Supabase rule](https://supabase.com/docs/guides/database/database-linter?lint=0029_authenticated_security_definer_function_executable).
- Adviser returned **one WARN** `auth_leaked_password_protection`: leaked-password checks are reported not enabled. Confirm feature availability and dev-versus-production policy with the auth owner. [Supabase password security](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).
- Catalog query for functions **inside `caseproof` schema** observed private internal functions, including `register_fixture_draft_derivative` and retention guards. In this query, none of the listed private functions granted direct `EXECUTE` to `anon` or `authenticated`. Many were owned by `postgres`. This is not a comprehensive execution-path audit and does not determine public RPC safety.
- `list_migrations` returned a populated development migration history. No repository-versus-deployment migration diff was computed as part of this limited read-only inspection.

## Raw query scopes (reproduce with authorized read-only access)

1. `pg_class` + `pg_namespace` + `pg_policy`: `n.nspname LIKE 'caseproof%'`, ordinary/partitioned tables and views; group by relation, `relrowsecurity`, `relforcerowsecurity` and policy count; max 150 rows.
2. `pg_proc` + `pg_namespace`: `n.nspname LIKE 'caseproof%'`, owner, `prosecdef`, `proconfig`, `has_function_privilege` for `anon`/`authenticated`; max 100 rows.
3. Supabase security advisers on the pinned dev project.

## T70 closure remains OPEN

Require a second read-only **public RPC** owner/search-path/grant/function-body inspection with security reviewer, real signed-user cross-matter/revoked-role negative tests through least-privilege ingress, migration parity, and decisions for each finding. Privileged SQL catalog inspection must never be described as genuine signed RLS acceptance.

**Status:** partial factual security discovery, no approval. **Rollback:** none; reads only. **Operational owner:** not yet assigned. **Signed reviewer:** not yet assigned.
