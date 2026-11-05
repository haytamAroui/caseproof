# CaseProof — Document-wide DOCX authorization security review

**Review status:** UNAPPROVED · **Owner:** independent reviewer required · **Date:** 5 November 2026

**Scope:** [PR #191](https://github.com/haytamAroui/caseproof/pull/191), stacked on PR #190. The SQL lives in [DOCX_EDITOR_DOCUMENT_SCOPE_SQL_PROPOSAL.sql](DOCX_EDITOR_DOCUMENT_SCOPE_SQL_PROPOSAL.sql); **it has been installed only on the `caseproof-dev` test project (migration `20261105081249`); it is NOT installed in production and is not approved for pilot**. This file supplies repeatable independent-review criteria, not a substitute for peer/practitioner approval.

## Threat model and trust boundaries

- **Immutable source → Word candidate.** The source is an authenticated, matter-scoped frozen snapshot. The candidate is not evidence. A browser may submit arbitrary OOXML bytes, but the backend must enforce size (5 MiB), exact SHA-256, source/version binding, ZIP admission, XML safety, disabled external relationships, macros, embedded active parts and disallowed fields. Preserve the original bytes and never silently claim arbitrary formatting fidelity.
- **Candidate → approval.** A whole-document edit is *not* a citation correction. Review must persist an actor-bound, matter-bound, snapshot-bound fingerprint of original/candidate bytes, byte length and substantive rationale. Separate `draft:edit` grants are required at both organization and matter scope. Do not derive review authority from existence of a finding.
- **Approval → reservation.** A new version ID must be allocated atomically in SQL only after the exact actor/command/candidate review receipt is matched; all audit failures roll back both reservation and audit record. Reusing the idempotency ID with altered bytes or metadata must fail closed.
- **Reservation → storage → activation.** The signed transport writes privately once, reads back authorized bytes, verifies exact SHA-256 and length, then calls trusted activation. A second permission check occurs at activation, including after an unknown write outcome. A general reader must never access or activate reserved document-edit versions.
- **Reconciliation and cold reopen.** The separate document-edit status RPC checks fresh `draft:edit` and verifies the saved whole-document approval, avoiding the older reference-scoped status reader. After revocation, all reviewer-level operations, status reconciliation, and activation must fail.
- **History and evidence.** A successful activation invalidates old snapshot confirmations and human decisions. A fresh check and human review is mandatory before export or legal-use evidence claims. Existing F5 citation reference and signed export gates must not be weakened.
- **Word host import.** Users can use actual Microsoft Word (paragraphs, tables, images, fields, comments, track changes) and then import a DOCX. CaseProof admits only safe supported file content and reports package-part changes; no claim of browser Word clone or guaranteed Word/LibreOffice fidelity.

## PR #191 engineering receipts to verify

1. Inspect `apps/api/docx_native_workflow.py` and `apps/api/docx_editor_api.py` for input-size limits, source hash/version fencing, exact bytes, safe ZIP admission, signed actor, same-snapshot `If-Match`, and immutable source.
2. Inspect `docs/security/DOCX_EDITOR_DOCUMENT_SCOPE_SQL_PROPOSAL.sql` for *separate* actor-scoped review, atomic reserve, dedicated status with fresh `draft:edit`, and service-only activation. Confirm every `SECURITY DEFINER` RPC checks grants and JWT role internally, has fixed search_path, and revokes PUBLIC by function signature.
3. Require a **green exact-head** [disposable SQL acceptance workflow](../../.github/workflows/docx-editor-disposable.yml), including marker `DOCX_DOCUMENT_REVIEW_ACTOR_SCOPE_AUDIT_ROLLBACK_RESERVE_REPLAY_ACTIVATE_RECHECK_INVALIDATION_REVOKE_PASSED`. Ensure `tests/test_docx_native_workflow.py` includes malformed/active DOCX, huge uploads, revision presence, stale source, conflicting replay, approved reservation, readback, writer exceptions, and revocation.
4. Require a **green exact-head** signed browser workflow, including `DOCX_NATIVE_WORD_GENUINE_SIGNED_SOURCE_DOWNLOAD_EDIT_IMPORT_AND_PREVIEW_PASSED`, original integrity, F5 existing correction/commit/recheck, cold reopen and zero residual. Native activation **has not** been signed-live-tested while proposed SQL is uninstalled; a green candidate preview alone does not close that gap.
5. On an independently approved disposable deployment, exercise cross-org/cross-matter forged UUIDs, a reader without `draft:edit`, a reviewer whose grant is revoked before/after reservation, service-role misuse, audit-trigger rejection, stale inventory confirmation, concurrent reservations, conflicting retries, lost HTTP acknowledgment, storage success-with-no-ack and cold reopen.
6. Obtain actual Microsoft Word **and** LibreOffice DOCX round trips for simple and complex fixtures, particularly tracked changes, comments, tables, textboxes, hyperlinks and fields. Record exact package changes and intentional abstentions. Reviewer must not approve a universal compatibility claim from synthetic `python-docx` tests.
7. Run browser keyboard/screen-reader assessment, egress/network capture, retention/erase, privacy approval, long DOCX capacity and practitioner usability signoff before any legal pilot.

## Current independent evidence status

- **Automated:** PR #191 CI depends on latest head; earlier head `323a4cd1` had 20 successful workflows, four expected skips. New commit results MUST be reverified.
- **Supabase security advisors (5 November 2026):** caseproof-dev reported existing *15* `authenticated_security_definer_function_executable` WARN findings and *29* `rls_enabled_no_policy` INFO findings (primarily private tables). These are not proof of an exploitable issue, but the reviewer must triage intentional RPC exposure and check no new public privilege was introduced. An existing leaked-password-protection WARN is unrelated to editor authorization. [Supabase database lint remediation](https://supabase.com/docs/guides/observability/advisors).
- **Dev SQL installation VERIFIED:** On 5 November 2026, migration `20261105081249` was applied to `caseproof-dev` (Supabase project `ldwmocpxwskvhoojndrd`). PostgreSQL confirmed `caseproof.dossier_document_edit_reviews` with RLS enabled, zero direct `anon`/`authenticated` table grants, and no row policies (RPC-only, deny by default); four scoped review/reserve/status/activate RPCs and one service-only ephemeral owner-grant helper exist. `anon` cannot execute any new RPC, and only `service_role` can execute activation and fixture-grant RPCs. The source is retained as [a dev-only migration record](DEV_ONLY_APPLIED_DOCX_AUTH_MIGRATION_20261105081249.sql) outside the canonical migrations folder so it cannot be automatically deployed to production without approval. The signed whole-document live activation must still be verified.
- **Independent reviewer signature:** **NOT PROVIDED**. No author, AI agent or test runner should self-certify an independent review.
- **Production/pilot rollout:** **BLOCKED** pending independent approval, explicit production migration, trusted runtime private Storage review, and signed-live full-document activation evidence.

## Independent reviewer sign-off (intentionally blank)

Reviewer name / role:

Review date:

PR SHA / approved SQL hash:

Database/Storage and cross-tenant test evidence:

Identified issues / remediations:

Security decision (approve / changes requested / reject):

Signature / traceable review URL:

