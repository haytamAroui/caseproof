# PR204 Release acknowledgement — deployment preflight

**Status: TEST-ONLY / NOT DEPLOYED**, 12 November 2026. Issue #216.

The main repository includes the genuine migration
`20261106210000_caseproof_release_acknowledgement_fence.sql` and the matching
API `release_acknowledged: true` and server-verified actor contract.
Read-only Supabase MCP inspection confirms that `caseproof-dev` **does not**
have its release acknowledgement function or trigger. There are currently
zero release rows in the development table.

## New independent PostgreSQL acceptance

This PR does not modify the historical SQL migration. It uses a **fresh
isolated PostgreSQL 17 service** to execute its exact SQL against a minimal
synthetic `caseproof.dossier_releases` table. The acceptance requires:

- One valid release with an exact 10-field signed-actor acknowledgement.
- All 14 invalid synthetic releases rejected with **SQLSTATE 42501**,
  including missing acknowledgement, wrong actor, wrong release ID,
  changed snapshot, release scope, expiry/future timestamp, forged label
  type, and unexpected fields.
- Only the original valid row persists, and both `anon` and
  `authenticated` lack direct EXECUTE on the trigger function.

Generic SQL errors or other SQLSTATEs cannot stand in for authorization
rejection. The same untouched SQL file is used by the acceptance and any
later approved deployment; no insecure test-only variation is substituted.

## Remaining blockers

This is a synthetic fence test, **not** a genuine signed-user browser
acceptance, professional approval, court signature, or hosted deployment.
Do not apply this SQL through Supabase MCP until:

1. The reviewed API/frontend release acknowledgement contract is deployed
   together with this trigger, not ahead of or behind it.
2. Live current objects, RLS, grants and migration ledgers are read-only
   snapshotted and independently reviewed; no timestamp/history repair.
3. The protected genuine-JWT workflow is approved and the valid release,
   foreign-actor/manifest mismatch, revocation, and historical readbacks pass.
4. The pilot deployment owner and security reviewer approve the activation.

If these conditions are not met, the dev database remains unchanged and
pilot release is blocked. The P0-3 migration-history reconciliation is
separate and still open.

Sources: PR #204, ADR 0037 and official Supabase migration guidance:
https://supabase.com/docs/guides/deployment/database-migrations
