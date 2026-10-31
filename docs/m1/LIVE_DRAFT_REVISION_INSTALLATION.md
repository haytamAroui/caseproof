# Development draft revision installation receipt

Owner explicitly requested applying the migration on 1 November 2026 (Brussels).
Connected Supabase MCP applied `dossier_draft_revisions` to `caseproof-dev`, project
`ldwmocpxwskvhoojndrd`, as migration **20261031234906**. The exact applied SQL is
`supabase/migrations/20261031234906_dossier_draft_revisions.sql`; it matches the
reviewed/tested proposal byte for byte, including its historical proposal header.

Post-install catalog checks established:

- Revision table RLS enabled; authenticated SELECT and INSERT are denied.
- Activation: anon and authenticated EXECUTE denied; service_role allowed.
- Reservation: anon EXECUTE denied; authenticated allowed behind in-function guards.
- Original manifest implementation: authenticated EXECUTE denied.
- All inspected privileged functions retain an empty search_path.
- No revision rows were created by this deployment.

Security advisors report 28 informational RLS-without-policy tables (including the
new private RPC-only table), 11 authenticated SECURITY DEFINER warnings (including
the intentionally guarded reservation RPC), and existing disabled leaked-password
protection. These are recorded findings, not an independent security approval.
See [function warning](https://supabase.com/docs/guides/database/database-linter?lint=0029_authenticated_security_definer_function_executable)
and [password protection](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).

This is deployment/catalog evidence, **not genuine signed-user acceptance**.
The opt-in protected dossier correction workflow still needs execution. Independent
review, representative accuracy and formal M1/M2 acceptance remain open.
