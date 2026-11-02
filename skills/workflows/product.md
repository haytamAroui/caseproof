# CaseProof product-engineering workflow

1. Read `AGENTS.md`, `CONSTITUTION.md`, `frontend/BLUEPRINT.md`, the nearest ADR and generated API schema.
2. Map user intent to a complete thin slice: finding → preserved original source → page/passage → separate dimensions → authorized human decision → durable readback.
3. Show identity, page mapping, fidelity, support and coverage/processing separately. Never infer verdicts or approval in React.
4. Bind every read to actor, matter, snapshot, source version and hash. Handle 401/403 by invalidating session, aborting requests, clearing private caches and object URLs.
5. For writes use stable operation IDs, explicit pending/unknown/confirmed states and authorized receipt readback. No optimistic saved review or duplicate retry.
6. Treat corrected DOCX as a new derived draft, leaving originals immutable. Require recheck before release.
7. Test happy path plus ambiguous outcome, session expiry, stale revision, OCR ambiguity, denial and cold reopen.
8. Record actual tests, CI, browser evidence and remaining legal/security gates. Do not imply synthetic acceptance equals production acceptance.

Relevant skills when installed: `caseproof-foundation`, `caseproof-frontend-engineering`, `caseproof-evidence-ui`, `caseproof-verification-workflow`, `caseproof-recovery-session`, `caseproof-report-export`, `caseproof-product-qa`.
