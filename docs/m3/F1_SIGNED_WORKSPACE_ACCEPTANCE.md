# F1 signed workspace acceptance record

1 November 2026. Engineering candidate in PR #165. No independent security,
client-data, production or full M3 acceptance is implied.

## Development installation

Connected Supabase MCP installed `workspace_f1_report_catalog` in **caseproof-dev**
(`ldwmocpxwskvhoojndrd`) as `20261101205446`. Exact applied SQL is retained in
`supabase/migrations/20261101205446_workspace_f1_report_catalog.sql` and matches
`db/proposals/PIV-F1_workspace_report_catalog.sql` byte for byte. No table,
index, role, source data, existing grant or production project changed.

Native read-only inspection confirmed existing case/member/grant/snapshot RLS and
the snapshot `(org_id,case_id,snapshot_hash)` primary key. After installation,
`prosecdef=true`, empty search_path, anon EXECUTE=false, authenticated EXECUTE=true,
and authenticated direct snapshot SELECT=false. This privileged catalog inspection
is not genuine signed-RLS acceptance.

Security advisor delta: existing 28 no-policy INFOs and disabled leaked-password
protection warning unchanged; authenticated SECURITY DEFINER warnings increased
from 11 to 12 for the explicitly scoped read-only catalog. This requires independent
review, not a claim of zero advisories. See [Supabase function advisory](https://supabase.com/docs/guides/database/database-linter?lint=0029_authenticated_security_definer_function_executable)
and [password protection](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).
No existing policy was weakened to silence warnings.

## Measured implementation evidence

Initial code head `c848ac166bcdc0ded915beb41a7a294ed79d9a5f` passed the new
[disposable PostgreSQL catalog job](https://github.com/haytamAroui/caseproof/actions/runs/41349126638)
and production-build browser checks in the
[frontend job](https://github.com/haytamAroui/caseproof/actions/runs/41349126502).
Disposable SQL checks cover bounded/disjoint paging, ungranted same-org, foreign,
anonymous, revoked membership/grant, deleted parent and denied direct snapshot reads.
These SQL tests simulate identity only inside disposable PostgreSQL.

Local full suite: 1,924 passed, four live gates skipped. Frontend: 34 unit/architecture
tests, locked contract generation, lint/type/build/policy; strict UI audit zero
findings. Exact final-head cloud and protected genuine-browser receipts remain
pending at this entry; record them before marking F1 accepted.

The protected genuine workflow serves the built React application from the actual
loopback Python API, signs real ephemeral users in via the password adapter and
uses real signed PostgREST grant reads. Browser expiry advances the browser clock
against the real verified provider expiry; it does not prove wall-clock provider
expiry. No credential-bearing browser screenshots/traces are created. Existing
M0.5 fixture registration, finally cleanup and independent zero-residual check apply.
