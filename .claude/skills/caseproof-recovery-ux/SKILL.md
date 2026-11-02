---
name: caseproof-recovery-ux
description: Implement safe recovery and permission-aware UI for legal-document operations with ambiguous outcomes, partial failure, and revocation.
---
# Recovery and authorization UX
Read `frontend/BLUEPRINT.md` first. Apply to signed intake, grants, review decisions, corrections, exports, and any multi-step workflow. Patterns are independently specified; do not copy AGPL Mike source.

## Operation model
Track stable operation ID, exact payload identity, actor/matter/version, and authoritative backend receipt. Distinguish idle, pending, definitely rejected, outcome unknown, confirmed committed, and committed-but-dependent-step-failed. Do not invent new backend statuses: UI labels describe known transport state and verified receipts.

## Partial failure
If a create succeeds and later access grant fails, preserve created resource ID and its confirmed receipt. Retry only failed grant when server permits, never recreate the resource. If the creation outcome is unknown, perform authorized readback/receipt reconciliation before any retry. An HTTP 409 is not itself proof of ownership or successful upload.

## Permission denial
Unknown permission is denied for action purposes. A stale loaded row or pending authentication cannot authorize bulk operations. For unpaged selections require authoritative server-scoped selection/authorization; otherwise block and explain. Only show a named owner/contact if current user is permitted to see that identity; otherwise provide a generic authorized escalation path. On 401/403 clear scoped private state, abort late requests, revoke object URLs and require re-authentication.

## Optimism policy
Never optimistically mark immutable evidence deleted, a human decision signed, a correction activated, or an export released. Optimistic presentation may be used for reversible non-authoritative UI state only, with exact rollback and no misleading saved indicator. Destructive actions need explicit confirmation and backend receipt.

## Accessibility and language
Focus error summaries and actionable retry controls; announce pending, unknown and denied states without color alone. Provide NL/FR/EN terminology review; never put confidential document text in telemetry, URL or toast logs.

## Required tests
Unknown response after commit; created-but-ungranted; duplicate retry; 409 with wrong source hash; session expiry during upload; late response after logout; partial bulk denial; revoked access; interrupted correction activation; restart reopens saved receipt; no persisted private browser state.
