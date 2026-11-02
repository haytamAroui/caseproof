# F3 browser intake — engineering acceptance

Scope: P03 creation, P05 preservation/reconciliation and P06 inventory/source/page confirmation in the signed loopback workspace. P04 preserved-report navigation links to intake. Canonical backend services remain authoritative. [ADR 0029](../adr/0029-workspace-intake.md) records permission, transaction and recovery boundaries.

## Implemented surfaces

| Surface | Mounted application API | Authority and receipt |
| --- | --- | --- |
| P03 create | GET `/v2/workspace/intake/organizations`; POST `/v2/workspace/intake/matters` | Existing signed organization membership/create permission and durable journey operation. Current actor/org resolved by installed RPC; no free-text tenant/role input. |
| P05 sources | GET `/v2/workspace/intake/matters/{case}`; POST suffix `/reservations` then `/sources` | Every original passes container/format/hash/size validation before metadata or object writes. Reservation is not preservation. Registered case/version/org/digest bindings checked before writes; exact fresh signed readback required. |
| P06 inventory | Same GET intake context; existing POST `/v2/matters/{case}/briefs/{brief}/dossier/confirmation` | Current bundle signature, explicit completeness and missing/ambiguous bindings; separate physical/printed/bundle page spaces. Backend receipt and fresh confirmation/entry/page-map readback control saved state. |
| Explicit check | Existing POST dossier `/checks` → frozen report route | No automatic verification on intake or confirmation. Backend returns snapshot and separate verification dimensions; browser validates case/brief binding. |

Generated organization/create/intake/confirmation schemas and precompiled validators reject unknown or foreign consumed contracts. React uses only same-origin authenticated transport; no direct database/Storage SDK, persisted bearer or client approval authority. Creation retains only an opaque operation UUID in permitted URL state. Original file identity drives deterministic server-side bundle replay after cold restart.

## Executed evidence

Code head `35cf08946bbdaac138ceac19d579269d06dc2a67` passed **all 19 checks: 18 ordinary jobs and the protected genuine signed-browser run** on [PR #167](https://github.com/haytamAroui/caseproof/pull/167). Before the final receipt-only update, the full local locked Python suite passed **1,943 tests, four separate live gates skipped**. Frontend unit/architecture suite passed **40 tests**; contracts, ESLint/hooks, strict TypeScript, build, M3 policy, architecture and strict UI audit passed. Local Chromium download returned truncated archives; browser execution evidence comes from actual cloud runners, not an inferred local pass.

Protected real-Auth acceptance on code `5a7307083c2e59de89765c551a1892c9e3b6d86b` passed browser-created matter, actual DOCX/inventory/text PDF/scan, corrupted final PDF rejection, lost upload acknowledgement, exact-original retry without new versions, fresh process/relogin, inventory/page mapping save/readback/reopen, explicit check, ungranted/foreign/revoked denial and zero-residual teardown. The subsequent code adds explicit existing parser-limit copy and a definite-422 confirmation correction path. Review fixes reject inventories above 512 distinct candidates before registration and allow removal of alternative bindings without removing the inventory identity. Final head `35cf089` passed the extended protected journey and all ordinary checks, including **16 production-build browser tests**.

Recovery debugging found an actual integration gap: a committed duplicate object can produce Supabase HTTP 400, while the older transport's duplicate exception covered HTTP 409. F3 now first reads existing immutable originals and reconciles any racing/denied/unknown write only by a fresh authorized byte-for-byte read. Corruption, wrong organization, revoked access or missing readback never becomes success. No overwrite or policy relaxation was introduced. Failed protected attempts also emitted `ZERO_RESIDUAL_VERIFIED`.

Synthetic browser coverage includes unknown upload outcome/retry, canonical page-map field order, saved receipt, stale-409 rejection, definite-422 correction/new operation, dirty-form leave/stay, session clearing, axe and narrow layout. Review findings discussion_r4438964591 and discussion_r4438964596 are fixed with 512/513 preflight boundary tests and synthetic/genuine browser alternative-binding add/remove coverage. Python boundaries cover corrupt final original before any registration/write, duplicate filenames, traversal, hash/size/role mismatch, cross-organization refs, revocation, oversized HTTP body, real parser projection and unknown/denied/duplicate reconciliation, and protected-test exception redaction so a failed browser fill cannot enter the outer fixture log.

## Limits and remaining gates

The installed development bundle contract accepts **exactly one DOCX, one UTF-8 text inventory and two PDFs**, at most **5 MiB each, 12 MB combined, 64 pages per PDF**, with a **1 MiB/512-identity inventory** and at most **512 confirmation bindings**. It does not import arbitrary N exhibits, PDF/DOCX inventories or an optional fifth bundle. Scans remain visibly partial without OCR; this screen does not claim completion of the independently configured page worker. Stops abort the browser request but may leave a partial remote outcome; reselect identical originals and reconcile. No browser delete/admin cleanup action is exposed.

F3 engineering evidence is distinct from independent security/privacy, representative legal-source/language/manual accessibility, professional-secrecy and production acceptance. No whole-system zero-egress, qualified signature, legal accuracy or deployment claim. No schema/migration, RLS/grant change, provider, production mounting or customer data was introduced. F4 review, F5 correction and F6 artifact delivery remain open.

Rollback removes the new loopback router and React routes/contracts. Existing original bytes, grants, snapshots, confirmations and compatibility clients remain intact.

## Final code receipt — 2 November 2026

Protected genuine signed-browser run: [41390550091](https://github.com/haytamAroui/caseproof/actions/runs/41390550091), code `35cf08946bbdaac138ceac19d579269d06dc2a67`. Fixed milestones emitted:

- `F3_BROWSER_CORRUPT_FINAL_PREFLIGHT_REJECTED`
- `F3_RESERVATION_HTTP_200` / `F3_FIRST_TRANSFER_HTTP_200` / `F3_REPEATED_TRANSFER_HTTP_200`
- `F3_REAL_UPLOAD_LOST_ACK_EXACT_READBACK_REPLAY_PASSED`
- `F3_BROWSER_COLD_PROCESS_SIGNIN_INVENTORY_RECEIPT_REOPEN_EXPLICIT_CHECK_PASSED`
- `F3_GENUINE_BROWSER_CREATE_INTAKE_CONFIRM_COLD_RESUME_DENIAL_REVOCATION_PASSED`
- `M05_STORAGE_EMPTY_VERIFIED` / `ZERO_RESIDUAL_VERIFIED`

These close the stated four-original F3 engineering exits. PR/human review and the independent release gates above remain open. The final receipt-only documentation changes no executable code, configuration, SQL or dependency; it intentionally reuses this genuine run instead of creating duplicate live fixtures to append a receipt. Ordinary final-documentation-head CI is checked separately.

Final code frontend/browser receipt: [41390553320](https://github.com/haytamAroui/caseproof/actions/runs/41390553320). Kernel/disposable PostgreSQL receipt: [41390553322](https://github.com/haytamAroui/caseproof/actions/runs/41390553322). All 19 code-head checks passed with zero failures or pending jobs.
