# Data Rights Enforcement — PR 2 (development-only, opt-in)

**State:** DRAFT. Dormant migration `20261106105558` installed on
`caseproof-dev` on 6 November 2026 with four triggers, zero persisted
policies, no authenticated/service grants on the control, and `enabled=false`.
Based on merged PR #201 and its append-only signed
rights policy ledger. No new rights grants, default approvals, automatic
backfill, production rollout, training or RAG.

## Security requirement

An existing signed case/source authorization is a prerequisite, NOT a rights
decision. A rights policy must not expand access to a tenant or matter.
Protected source uses fail closed unless the latest, server-resolved, exact
source-version policy explicitly permits the operation.

| Action | Right | Implemented app gate |
| --- | --- | --- |
| promote parsed source / OCR | `process` | signed live ingest before parse and before trusted RPC |
| generate dossier check | `process` | all signed bundle source versions before parse and before snapshot |
| search stored representation | `indexForSearch` | signed evidence-search route before returning matches |
| create reviewed release | `export` | frozen server-receipted source bundle at preview, pre-artifact and pre-write |
| cross-matter use | `useAcrossMatters` | always denied pending exact source and destination authorization; never implicitly enabled |

`CASEPROOF_RIGHTS_ENFORCE_DEV=YES` is the ONLY opt-in in the
development composition layer. Default is disabled; no body/query/header
parameter can toggle it. The underlying policy projection is read through
the **current authenticated bearer** using a publishable key and a
server-authorized RPC, not user-supplied rights metadata.

Missing/unknown/explicitly denied policies refuse the protected operation.
Rights lookup outages return a sanitized unavailable error, never an
implicit allow. Logs contain only action, disposition and reason; no original
bytes, bearer, source ID, tenant ID or firm authorization reference.
Human original inspection and historical signed-release replay are not
reclassified as processing/export writes.

## Blocking issues before actual enforcement can be enabled

1. **Transactional SQL fence installed (DORMANT):** Private operator control defaults
   to disabled. The same-transaction triggers require an effective rights row
   for every source before derived representation insertion, dossier snapshot
   insertion or reviewed-release insertion. Case-row locks serialize policy
   changes against a protected write. A forward-only source-scope migration
   rejects omissions from the authoritative active matter version set. CI must prove both opt-in denial and
   unchanged disabled behavior. Enablement remains blocked on signed acceptance
   and independent review; do not enable the control on caseproof-dev.
2. **Complete route inventory:** Audit signed and direct SQL paths for
   processing, OCR, indexing, search, correction/recheck, exports and derived
   artifacts; do not assume one Python entry point covers all uses.
3. **Legacy source onboarding:** Missing policies remain UNKNOWN and cannot be
   silently approved. Provision explicit `rights:manage` only through an
   owner-reviewed human workflow and an allowed synthetic pilot cohort.
4. **Genuine signed-user acceptance:** Run two separate users and a revoked
   grant, verify actual JWTs, compare shadow and enforce behavior, and
   capture clean redacted logs without adding real client data.
5. **Independent security/legal review:** SECURITY DEFINER authorization,
   customer consent, cross-matter permissions, controller/processor allocation
   and right-to-erasure consequences require independent sign-off.
6. **CI:** Full regression matrix and exact PR head checks must be green.

**Activation order (pilot only):** migrate dormant schema; verify approved
legacy source rights and signed actor grants; obtain independent approval;
flip the private SQL control in an owner-controlled migration **before**
enabling `CASEPROOF_RIGHTS_ENFORCE_DEV=YES` in the loopback API. Never set
only the API flag and assume direct privileged RPCs are protected. Missing
control rows fail closed rather than silently switching enforcement off.

**Do not merge or enable this draft until the above gates are met.**
PR 3 adds rights versions and decisions to the signed reviewed-release
manifest and must be separately approved.
