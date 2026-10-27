# M1 + M2 live acceptance — integrated delivery contract

Status: implementation gate; **not a claim of completed live acceptance**.

## Goal
Demonstrate one private Belgian litigation matter from signed-in users to source custody, verified exhibits, factual checking, reviewer correction, recheck and immutable history. Do not start M3 until this gate passes.

## Workstreams bundled in one implementation PR
1. **Security:** approved canonical private-grant migration based on PIV-M1_DEV; restricted non-BYPASSRLS application role; actor-bound audited grant issuance/revocation. Never use a client-supplied actor or tenant identity. Explicit security-owner approval is required before any live migration.
2. **Users:** three independent real Supabase Auth sessions A/B/C, with A reviewer, B permitted viewer and C unauthorized. Check same-organization and cross-organization isolation, revocation, and session freshness.
3. **Custody:** private PDF/DOCX upload and retrieval, content hashes, immutable originals, representation/page/anchor lineage, deterministic ingestion IDs, job checkpoint/restart recovery and failure diagnostics.
4. **Review:** confirmed exhibits → persisted brief/assertion graph → NL/FR/EN deterministic checks → reviewer decisions → corrected immutable version → second check; no silent overwrite or implicit promotion.
5. **Acceptance:** run an end-to-end fixture against real development infrastructure; include negative access, wrong-tenant, forged JWT, missing anchor, conflicting amounts, crash/restart, revoked grant and inaccessible Storage tests.
6. **Evidence:** capture redacted run IDs, database migration IDs, CI links, pass/fail counts, timing, check fidelity, and known limitations. Never upload credentials or sensitive professional documents to CI.

## Merge and deployment gates
- Full unit/architecture/Postgres CI passes.
- All privileged operations audited and fail closed.
- Security owner reviews SQL and permissions; merge alone does not authorize installation.
- Explicitly separate disposable test success from genuine signed-user live acceptance.
- No legacy organization-wide SELECT policy remains after approved installation.
- Word add-in and controlled delivery remain M3/M4; do not mark them complete.

## Acceptance record
| Gate | Evidence required | Status |
| --- | --- | --- |
| Reviewed migration | Security sign-off and migration checksum | Pending |
| Private live database | Applied migration and inspected RLS | Pending |
| Three genuine users | Signed session isolation and revocation logs | Pending |
| Real private source | Original hash, Storage readback, PDF/DOCX anchors | Pending |
| Durable check/review | Check → decision → correction → recheck run IDs | Pending |
| Recovery | Restart/replay trace, no duplicated effects | Pending |
| Product walkthrough | Recorded complete development dossier walkthrough | Pending |

Reference: docs/m1/EXACT_DEV_PRIVATE_SCHEMA_ROLLOUT.md, docs/ROADMAP.md, PRs #82–#88.
