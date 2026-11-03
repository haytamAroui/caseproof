# F6 development verification — 3 November 2026

Scope: PR #178; `caseproof-dev` project `ldwmocpxwskvhoojndrd` only.

## Installation and independent automated engineering review

The earlier absence claim was stale. Connected Supabase MCP migration history confirms:

| Migration | Version | Exact SQL SHA-256 |
| --- | --- | --- |
| f6_reviewed_release_ledger | 20261103083932 | 78e13eeaf48e4985ff4423e4c1d1c60505aa9b036b91330a675c23cc923a6741 |
| f6_reject_null_release_action | 20261103105420 | a54d5955c0612c75c3f505289361163189206e5ebaac7657f655e83fb2abb0dd |

The first hash matches `20261103080000_f6_reviewed_release_ledger.sql`; preserve its installed history. The forward migration file uses its actual generated deployment version and exact deployed SQL.

A separate read-only automated engineering reviewer identified SQL NULL fall-through into trusted release writes. The forward replacement rejects NULL before role dispatch, preserves existing grants, and otherwise leaves the function body unchanged. The reviewer approved this scoped fix for development application and independently ran the four DOCX structural tests. This is engineering review, not independent human/practitioner/security certification.

Post-application catalog evidence: ledger RLS enabled; anon and authenticated direct SELECT denied; authenticated direct INSERT denied. Export RPC: SECURITY DEFINER, empty search_path, anon EXECUTE denied, authenticated/service EXECUTE allowed; fixture grant RPC service-only. Tenant composite FK cascades matter erasure. The deployed export RPC contains the NULL guard. No customer rows or credentials were read or logged.

Security/performance advisors were checked. RLS-without-policy informational notices are expected for private RPC-only tables; authenticated SECURITY DEFINER warnings require the explicit membership/export checks reviewed here, not blanket grants. Project leaked-password protection remains disabled; this change does not alter Auth configuration. [Supabase advisor guidance](https://supabase.com/docs/guides/database/database-linter).

## Validation

- Local locked pytest: 14 passed across F6 DOCX integrity, reviewed exports and trusted transport.
- Affected Ruff checks passed.
- New disposable PostgreSQL regression requires SQLSTATE 42501 and the exact dispatch message for an authenticated exporter passing SQL NULL. Merely failing later manifest validation does not pass it.
- Signed browser [run #13](https://github.com/haytamAroui/caseproof/actions/runs/41621534188) passed at `deceb69`; newer code requires fresh cloud evidence on the PR.

## Artifact and human boundary

NL/FR real-package tests now exercise a referenced footnote with relationship/content type and preserve every original body element and non-document member. Existing signed acceptance exercises manifest/workspace finding links and physical PDF page 6, not embedded DOCX hyperlinks. DOCX annotations are plain text; embedded PDF/crop links and manual Word/LibreOffice rendering remain open. No production, customer-data or practitioner acceptance is claimed.
