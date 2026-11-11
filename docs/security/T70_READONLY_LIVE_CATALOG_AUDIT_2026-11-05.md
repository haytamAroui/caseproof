# T70 — caseproof-dev live security catalog (read-only, not sign-off)

**Observed:** 5 November 2026, ~19:52 UTC, connected Supabase project
\`caseproof-dev\` (project ref \`ldwmocpxwskvhoojndrd\`).
**Database:** PostgreSQL 17.11, project reported region \`eu-central-1\`.
**Scope:** Security Advisor results plus **SELECT-only** pg_catalog and
PostgreSQL permission queries. No DDL, auth settings, grants, policies, data
rows, credentials, Storage files, network traffic, or production changes.

## Actual findings — independently verifiable metadata

| Observation | Read-only result | Interpretation |
|---|---:|---|
| Authenticated-callable \`public.caseproof_%\` SECURITY DEFINER RPCs | **19** | Real privileged API attack surface; intentional callable RPCs still need independent function-body and actor-boundary audit |
| Anonymous-callable \`public.caseproof_%\` SECURITY DEFINER RPCs | **0** | Catalog result only; not pen-test or blanket access guarantee |
| SECURITY DEFINER functions without pinned \`search_path=""\` | **0** | Search-path hardening present in observed catalog; not proof of safe dynamic SQL |
| Private RLS tables without policies | **33** | Mostly privileged/private RPC-owned data; inspect grants and expected access one-by-one, do not auto-add permissive policies |
| Private caseproof tables with direct \`authenticated\` table privileges | **7** | All seven have RLS and at least one policy; observed grants are SELECT, no anonymous SELECT or client INSERT/UPDATE |
| Security Advisor authentication | **Leaked-password protection warning** | An auth-configuration decision requiring review; not evidence that passwords have leaked |

The seven direct authenticated SELECT tables are:
\`_m1_matter_grants\`, \`cases\`, \`document_versions\`, \`documents\`,
\`ocr_geometry_sidecars\`, \`organization_members\` and \`organizations\`.
Their observed RLS policy counts are respectively 1, 2, 1, 2, 1, 1, 1.

At the observation time, the 19 external-facing privileged RPCs were:
\`caseproof_dev_bundle_manifest\`, \`caseproof_dev_correct_brief\`,
\`caseproof_dev_journey\`, \`caseproof_dev_journey_organizations\`,
\`caseproof_dev_live_review\`, \`caseproof_dev_register_bundle\`,
\`caseproof_dossier\`, \`caseproof_dossier_document_edit_reserve\`,
\`caseproof_dossier_document_edit_review\`,
\`caseproof_dossier_document_edit_status\`,
\`caseproof_dossier_draft_recovery\`,
\`caseproof_dossier_draft_reserve\`,
\`caseproof_dossier_export_release\`,
\`caseproof_dossier_historical_read\`,
\`caseproof_dossier_snapshot_read\`,
\`caseproof_page_job\`, \`caseproof_phase4_review\`,
\`caseproof_soft_delete_matter\`, \`caseproof_workspace_reports\`.

## Reproducible read-only assertions

The audit used \`pg_proc\`/\`pg_namespace\` metadata,
\`has_function_privilege('anon'|'authenticated', oid, 'EXECUTE')\`,
\`pg_class.relrowsecurity\`, \`pg_policy\` counts, and
\`has_table_privilege\` checks. This is an observational snapshot, not an
authorization test under a genuine signed user session.

The live project currently has server-side metadata corresponding to repo
migrations, but migration history includes the known signed-page-worker
timestamp divergence (\`20261105104752\` deployed versus repo migration
\`20261031112127\`). Review functional equivalence before altering history.

## Required independent review before T70 closure

1. Independently read every exposed SECURITY DEFINER function body for
   \`auth.uid()\`/session, organization/matter/action checks, identifier
   binding, safe search paths, safe dynamic SQL, audit and replay guards.
2. Repeat actor/cross-organization/revoked-session adversarial tests against
   the **exact** deployment candidate, including the seven RLS SELECT
   policies and any source/Storage links.
3. Review each of the 33 no-policy private tables: demonstrate intended
   denial and privileged entry points; do not grant anonymous or universal
   authenticated rights just to silence INFO findings.
4. Confirm Auth leaked-password-protection availability, configuration,
   account policy and exceptions with the authorized auth/security owner.
5. Review advisor findings again after approved remediations, confirm
   exact deployment commit and independently sign the scoped T70 receipt.

**Decision:** **OPEN — independent review and signed actor tests pending.**
No vulnerability is declared solely from an advisor warning. No security
attestation, production permission or permission to upload client documents
has been granted.

Official Supabase references:
[authenticated-callable definer functions](https://supabase.com/docs/guides/database/database-linter?lint=0029_authenticated_security_definer_function_executable),
[RLS without policy](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy),
[leaked-password protection](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).


## Supabase MCP continuation — actual function and Storage policy examination

**Evidence:** Read-only \`execute_sql\`, project metadata and Security
Advisor through the connected Supabase MCP on the same development project,
5 November 2026. Reproduction: [catalog SQL](T70_SUPABASE_MCP_CATALOG_RECHECK.sql).
No table rows, object bodies, user credentials or customer data were read.
No migrations, writes or changes to grants or authentication settings.

All **19** authenticated-callable privileged CaseProof RPCs have a pinned
empty \`search_path\`. A code-shape scan found **17** referencing
\`auth.uid()\` directly and two wrappers that delegate checks:

- \`caseproof_dev_bundle_manifest\` calls
  \`caseproof_dev_bundle_manifest_original\`. That callee's live body
  checks \`auth.uid()\`, authenticated/non-anonymous role, active
  organization membership, active matter grants and evidence-read action,
  before fetching the matter's source manifest.
- \`caseproof_dossier_snapshot_read\` calls
  \`caseproof_dossier(p_case, 'decisions', ...)\` first. The callee's
  live body checks \`auth.uid()\`, role, active membership and matter
  grants, a non-deleted case, bundle signature and snapshot before
  reading frozen data.

No dynamic SQL pattern was detected by the limited static scan. This
**does not** prove the 19 function bodies or their delegates safe:
the independent reviewer must inspect the complete call graph,
operation authorization, race conditions, impersonation, stale sessions
and actual cross-matter/revocation behavior.

The seven directly readable CaseProof tables have authenticated-only
\`SELECT\` policies and no anonymous \`SELECT\` grants in the observed
catalog. In particular, the soft-delete guard policies
\`retention_case_deny\` and \`retention_document_deny\` are **RESTRICTIVE**,
rather than extra PERMISSIVE conditions that could inadvertently broaden
access. Re-run this assertion after any policy migration. The 33
RLS-with-no-policy private tables still require case-by-case review;
their state must not be "fixed" by adding unrestricted policies.

**Storage-specific observations:**

- Bucket \`caseproof-originals-dev\`: \`public=false\`; configured
  \`file_size_limit=20971520\` (20 MiB); accepted MIME types PDF,
  DOCX, text/plain, PNG and JPEG. The application still enforces
  a **5 MiB per-original development intake ceiling**; the larger
  Storage limit is **not** a product promise.
- \`storage.objects\` has the scoped \`caseproof_m1_original_put_once\`
  \`INSERT\` policy and \`caseproof_m1_original_read\` \`SELECT\`
  policy for authenticated identities. Both include active membership
  and active matter-grant predicates, a private bucket ID, and structured
  object keys tied to the registered source version.
- No CaseProof-specific \`UPDATE\` or \`DELETE\` Storage policy was
  observed. Storage operation-specific RLS and effective cross-tenant
  revocation still require signed-client negative tests.
  [Supabase Storage access controls](https://supabase.com/docs/guides/storage/security/access-control).

**Supabase Security Advisor remains unresolved:** 19 callable definer
warnings, 33 private no-policy notices and leaked-password-protection
configuration warning. Advisor output is an observation, not
an independent exploit finding or a certification.

**Disposition:** \`T70=EVIDENCED\` (preliminary live catalog, external
independent reviewer still **OPEN**). No claim of production-ready
security or permission for actual confidential legal records.
