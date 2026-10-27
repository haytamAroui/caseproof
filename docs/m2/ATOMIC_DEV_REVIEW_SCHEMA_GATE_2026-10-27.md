# M2 private check/review/correction schema — atomic dev candidate

**27 October 2026 · SECURITY-REVIEW CANDIDATE ONLY · NOT DEPLOYED**

## Exact live Supabase MCP inventory

Project: `caseproof-dev` / `ldwmocpxwskvhoojndrd`.

A read-only Supabase MCP query on 27 October confirmed:
- M1 private matter migration `20261027160745`: **installed**.
- Four expected private M1 SELECT policies: **present**.
- M2 tables (`caseproof._m2_*`): **zero**, not deployed.
- Auth users, private case rows: **zero**.
- Two existing INFO security lints (`audit_events`, `idempotency_records`) report no client policies, consistent with deliberate deny-by-default. No new policies were added.

**This PR does not create users, tables, storage resources, RLS changes, roles or records in live Supabase.** It only creates code and disposable CI.

## What the candidate installs, if independently approved later

[Single transaction](../../db/proposals/PIV-M2_DEV_atomic_private_review_candidate.sql) assembles the **existing** M2 disposable schema packets without rewriting their table or trigger bodies:

1. `_m2_check_runs`, `_m2_review_heads`, `_m2_review_events`, `_m2_review_receipts`: immutable source-bound check/run/reviewer events, replay receipts and CAS head.
2. `_m2_brief_versions`, `_m2_brief_references`, `_m2_brief_assertions`, `_m2_brief_heads`, `_m2_brief_events`: exact pinned brief graph, immutable version/references/assertions/events and CAS head.
3. `_m2_correction_plans`, `_m2_correction_events`: audited, append-only correction/recheck journal.

There are **11 tables**, all RLS enabled, **zero direct client privileges**, no authenticated write, no public API route, no client-executable trigger helpers, no new `SECURITY DEFINER`, no private Storage access grant. All source FK boundaries remain. The proposal is **not yet a canonical Supabase migration**.

Before creating anything, the candidate requires exact M1 private foundation and RLS policy names, empty development data and no existing `_m2_` relations. Rogue permissive private-case policy, missing M1, nonempty data and duplicate installation must roll back the **whole transaction**, with no data backfill assumed. It also checks generated tables and client privileges before COMMIT.

### Disposable test workflow

[`m2b-private-schema-acceptance.yml`](../../.github/workflows/m2b-private-schema-acceptance.yml) boots a **fresh ephemeral PostgreSQL 17 job** with no remote Supabase credentials and invokes `scripts.verify_m2_dev_private_schema`. It validates pinned-source drift, missing/unsafe M1 rollback, nonempty Auth refusal, full installation, RLS/no table access for `anon` or `authenticated`, duplicate rejection and row-history immutability. This is schema acceptance, **not** M2-B live integration.

### Deployment decision still required

After green CI and independent M1/M2 schema/permission review, use **Supabase MCP** to apply the **approved canonical** migration to the dedicated dev project and read back policy/catalog shape. Do **not** attempt manual GitHub Action owner-DB connections, add `CASEPROOF_DEV_DB_ADMIN_DSN` or `CASEPROOF_DEV_DB_CA_PEM`, grant clients broad access, insert into real `auth.users`, or misrepresent privileged MCP SQL as a real signed-user read.

**M1-B remains open** until genuine verified signed-user→non-BYPASSRLS matter/source reads, actor-audited grants, private immutable originals, process/OCR recovery and exhibit-register confirmation. **M2-B remains open** until these M2 tables are approved/installed, those adapters are mounted under genuine auth, an actual verified source + versioned brief is checked and reviewed, and a restart/recheck and cross-matter negative acceptance run passes. **M1-C/M2-C** additionally require independent human security/release review. M3 Word and M4 delivered DOCX/PDF are separate commercial requirements.

No production, professional document or tenant scope is approved by this candidate.
