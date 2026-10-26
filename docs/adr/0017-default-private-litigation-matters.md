# ADR-0017 — Default-private litigation matters and action-scoped grants

**Decision:** ACCEPTED FOR ENGINEERING CONTRACTS, 2026-10-26; **live RLS/auth/storage rollout remains unapproved** under CONSTITUTION C13. This is a deliberately narrow product-domain security policy, not a retroactive rewrite of ADR-0011's finance test evidence.

## Context and chosen policy

ADR-0011/S2-002 installed a **same-organization org-wide case read** policy. That is unsuitable as the default for confidential Belgian litigation, where two lawyers in one firm may represent different clients or parties with conflicting interests. M1 #63 proposed private matter grants, but left their action/role semantics inconsistent with org-wide RLS. Issue #64 records that conflict.

**Choose default-private for `domains/disputes` litigation matters.** A user must be both a currently active organization member **and** hold a currently active, explicit grant for the exact matter/action. No same-organization implicit visibility or owner-only shortcut. Org permissions constrain the maximum capabilities; case-grant capabilities narrow them further. Cases are not enumerated to ungranted members. A firm may share a matter with another member via an explicit audited invitation/grant, not by changing organization-wide rights. No wildcard or cross-organization grants.

**Existing installed org-wide RLS is not changed by this ADR or by PR #63.** It remains a known defense-in-depth gap for litigation until an independently reviewed transition policy is tested and installed. **No confidential client upload** is permitted in this state. The existing finance adapters keep their prior behavior.

## Frozen M1-A action contract (`application/litigation/matter_policy.py`)

| Scope | Permissions | Governing checks |
|---|---|---|
| Organization | `case:list`, `case:create` | Current active member with explicit org action; do not expose cases to anyone merely from org membership |
| Per-matter | `case:read` | Current signed actor, active organization membership with `case:read`, active exact-case grant containing `case:read` |
| Per-matter evidence | `evidence:read`, `evidence:upload`, `evidence:index` | The exact matter grant and org `case:read + evidence:read` required; upload/index never inferred from read |
| Per-matter exhibit decision | `exhibit:confirm` | Exact grant + org `case:read + review:request`; explicit interactive command and persisted audit; **not approval of legal conclusions** |
| Per-matter checking | `draft:check` | Exact grant + org `case:read + finding:write`; read-only check alone never mutates evidence |
| Worker delegated | `worker:process` | Not directly granted by ordinary user authorization: application must mint scoped short-lived job delegation fenced to case/source/version and lease; no worker identity forging |

Do not treat `role=reviewer` as implicit `exhibit:confirm` permission. Enforce **explicit** grant actions and audit mutations atomically in the eventual approved SQL adapter. A signer/owner is not implicitly a qualified court filing/collection approver. The existing Supabase `human_authenticated=False` on a signed password login means only that **legal approval attestation has not been established**. A signed session plus explicit `exhibit:confirm` and user intent may confirm bookkeeping mappings; it never grants legal approval.

## Migration/security plan (not executed)

1. Design canonical additive org/case-scoped grants including exact actions, revisions and active flags; case-invitation audit and revocation audit. Backfill legitimate memberships **only after explicit owner decision**, never broad automatic org-wide backfill.
2. Install updated private-matter RLS for **cases, documents, document_versions and all newly referenced evidence/review/job records in one reviewed change**; ensure document_version policies resolve the exact case via parent document. Existing S2-002 policies are not adequate until replaced. Ensure all service/worker pools have independently checked actor and case scope with RLS defense in depth.
3. Verify signed Auth subject + reviewed least-privilege Postgres principal, independent same-org private cases A/B, cross-org case C, grant mutation/revocation and pooled connection recycling, plus race/snapshot lock tests. Unknown and ungranted cases both mask existence.
4. Exhibit confirmation: update the SQL transaction to check `exhibit:confirm` grant **inside row lock**, current source versions and audit, not synthetic `p_actor`. An explicit user POST action is not automatic legal approval. Signed user does not create a legal filing receipt.
5. CI must exercise pure policy tests, SQL disposable RLS negatives, data authorization checks and recovery; release approval remains separate, M1-B/C open until integration evidence passes.

## Backward compatibility and M2 gate

Keep `apps/api/postgres_case_repository.py` and finance consumers unchanged. Litigation must opt into restricted policy; it may **not** use the legacy org-only repository to authorize case documents or M2 checking. M2 deterministic citation checks consume exact source/version/representation and a **confirmed** exhibit mapping; they cannot silently authorize through a client-provided tenant, mutable Word selection or model output. To begin M2 implementation, the **contract and negative tests** may be frozen here, but M1-B signed live Auth/storage/worker verification is still outstanding.

**Rollout owner/signoff:** human security reviewer for auth, RLS and migrations (C13/C16). Neither this ADR nor green synthetic CI is production authorization.
