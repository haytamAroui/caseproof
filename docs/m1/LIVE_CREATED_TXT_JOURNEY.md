# Live created TXT journey — development acceptance

**Status: LIVE SIGNED CREATED-MATTER → TXT INGEST → AUTHORED BRIEF → REVIEW → COLD RESTART → CLEANUP PASSED on 28 October 2026 (development only).** Protected main workflow [#40657265878](https://github.com/haytamAroui/caseproof/actions/runs/40657265878), merge commit `a8fd5a85f4f4f49a8083f0da66eb815c1700b5d2`, PR [#114](https://github.com/haytamAroui/caseproof/pull/114); all eight PR checks passed.

## Acceptance boundary

- Dedicated project: `caseproof-dev` (`ldwmocpxwskvhoojndrd`).
- Test identity: three real confirmed Supabase Auth users: owner, same-org ungranted user and foreign-org ungranted user. An admin RPC provisions **organizations and memberships only**, with no matter, document, representation, exhibit, brief, check or review seeded.
- Product path: the same dev-only authenticated FastAPI routes are called by the ClearBrief workbench and protected server test. The acceptance runner drives the **HTTP/server path**, not automated browser clicks. Browser source syntax and contract tests run separately.
- Signed creation: eligible org membership requires explicit `case:create`; owner reviewer grant, matter and audit are created in the **same Postgres transaction**. Same key + same input returns same matter, conflicting request rejected, and transaction-scoped advisory lock serializes competing requests.
- Original: single `text/plain` source per matter; 1 MiB limit, strict UTF-8. Document version is registered with immutable length and digest; Storage uses owner-signed JWT, no client upsert/update/delete; signed readback validates stored SHA-256.
- Ingestion: signed server **downloads and verifies actual private original bytes** before sending them to the signed database function; the database function separately compares the decoded bytes and digest/length to the registered version and exact Storage object. It creates an immutable text representation, hashed source snapshot, audit and **unconfirmed** source mapping in one transaction; failed promotion leaves no partial representation. A registered-but-uningested source is distinct from a verified representation.
- Brief: a user-authored short draft and explicit numeric quote are bound to that exact source and snapshot; one deterministic literal quote candidate is checked and versioned in the existing private M2 run/review/audit/receipt ledger.
- Cold restart: stop and relaunch **actual uvicorn process**, sign in afresh and reopen source text/snapshot, brief graph and review.
- Denials: ungranted case enumeration, source upload/ingest, read/check/review and guessed Storage path denied; owner revocation blocks subsequent state, check, ingestion and direct original read.
- Cleanup: admin-scope exact run-ID cleanup refuses unknown/non-dev activity and requires Storage object removed through Storage API first. Inspect post-run residue independently across dev fixture, organization, memberships, cases, documents, snapshots, exhibits, briefs, reviews, audit, objects and users.
- Synthetic fixtures only; no real client documents, passwords or JWTs printed.

## Known exclusions and next acceptance

- **Not** a PDF/DOCX/scanned ingestion/OCR test. No complete multi-document collection, parser/page coverage, PDF preview, Word host, full citation/date/value or semantic verifier, legal review/approval, correction/recheck, recipient delivery or production security signoff.
- TXT processing is **synchronous** with atomic representation promotion, not a durable worker/lease recovery system. Registration can remain pending after an interrupted upload; its idempotency key should be reused on retry. Comprehensive ingestion job recovery remains an M1-B requirement.
- The browser exposes the real creation and review operations, but the accepted automated live run proves the **server path**. No automated browser-host E2E acceptance is claimed.
- The development authenticated `SECURITY DEFINER` RPCs require independent security review before any wider use.

## Observed acceptance receipt — 28 October 2026

**Protected main [GitHub Actions run #40657265878](https://github.com/haytamAroui/caseproof/actions/runs/40657265878) — SUCCESS**, commit `a8fd5a85f4f4f49a8083f0da66eb815c1700b5d2`. All eight PR #114 checks green, including browser syntax, signed API contract tests, Ruff, mypy, migration inventory, kernel and disposable database regressions.

| Stage | Observed GitHub Actions receipt |
| --- | --- |
| `LIVE_TXT_1` | Three real confirmed signed GoTrue users |
| `LIVE_TXT_2` | Signed **new** private matter, owner grant, atomic audit, replay and outsider denial |
| `LIVE_TXT_3` | Signed immutable private Storage upload, SHA-256 readback, negative content and access tests |
| `LIVE_TXT_4` | Strict UTF-8 TXT ingestion, immutable source representation/snapshot and idempotent retry |
| `LIVE_TXT_5` | User-authored versioned brief, actual ingested-source quote check, persisted human M2 review/audit |
| `LIVE_TXT_6` | Actual uvicorn stop/restart, fresh GoTrue sign-in, reopened source text, brief and persisted review |
| `LIVE_TXT_7` | Same-org/foreign-org denial and post-revocation read/write/Storage denial |
| `LIVE_TXT_8` | Scoped fixture, Storage object and journal cleanup |
 
The runner printed `LIVE_CREATED_MATTER_INGESTED_TXT_AUTHORED_REVIEW_COLD_RESTART_PASSED`.

**Independent Supabase MCP cleanup readback:** All **19** checked categories were zero: `auth.users`, organizations, memberships, matters, private grants, documents, document versions, journey fixtures, journey operations, source snapshots, exhibit heads/events, brief versions/events, check runs, review events/receipts, audit events and private original objects.

**Migration history:** **16** installed development migrations total; five new forward-only migrations with versions `20261028081227`, `20261028081347`, `20261028081408`, `20261028081528`, `20261028082143`.

**Exact acceptance level:** Signed **server/API** journey against real PostgREST/Auth/Storage with cold-process persistence and independently verified zero residue. Real browser controls are implemented and the client code passed browser grammar/contract tests; the live acceptance did **not** automate browser clicks. No preseeded matter, document, source, representation, exhibit, brief, check or review was used in this run. Security review before wider deployment, full M1-B PDF/DOCX/OCR/exhibit confirmation, M2 correction/recheck, Word and final linked deliverables remain **OPEN**.
