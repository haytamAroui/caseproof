# Bounded locator and finding correspondence — implementation gates

Base: merged PR #183. This document is an implementation checklist, not acceptance evidence.

## Stage 1 — Contracts
- Audit existing correction target and receipt DTOs before altering them.
- Introduce version-bound locator identity: stable paragraph identifier where present, exact text, prefix/suffix, occurrence disambiguator, paragraph content hash, and source version identity.
- Require If-Match and Idempotency-Key as HTTP headers on mutation routes, not JSON body fields.
- Regenerate JSON Schema and TypeScript; enforce drift checks. Preserve compatibility only where safe.
- Gate: Python contract tests, generated contract check.

## Stage 2 — Resolver
- Resolve against the exact versioned DOCX bytes. Never use paragraph ordinal as sole authority.
- Match stable ID and validated text context; fallback only to uniquely resolvable context and verified hash.
- Reject ambiguous, missing, changed, unsupported, or stale targets without mutation.
- Gate: insertion/reorder, duplicate text, Unicode, split runs, stale hash and unsupported-structure tests.

## Stage 3 — API correspondence
- Validate If-Match against the authoritative current snapshot inside the same transactional boundary as the write; mismatch => 412.
- Persist idempotency by organization, authenticated actor, operation, key and request fingerprint. Identical retries replay the durable result; differing payloads reject.
- Verify authorization on every replay and reject revoked or cross-matter access. Cover races and unknown outcomes.
- Gate: PostgreSQL concurrent-writer, 412, replay, revoked actor, cross-org and restart tests.

## Stage 4 — Frontend
- Track active snapshot scoped to session, matter and draft; clear it on context switch.
- Send precondition and idempotency headers on review and correction mutations. Reuse keys only for identical retries.
- Keep DOCX locator resolution separate from PDF page-space bounded geometry. No text-search highlighting masquerading as verified location.
- Show RecoveryBanner on stale/unknown outcome; fail closed.
- Gate: generated types, TypeScript, frontend unit tests, production build.

## Stage 5 — Signed-browser acceptance
- Load real DOCX, select a finding, mutate persisted source/version concurrently, then preview correction.
- Assert stale/ambiguous rejection (412 or typed locator failure), RecoveryBanner, and zero unauthorized writes.
- Also verify harmless paragraph insertion behavior: safely resolve the unchanged target if version policy allows, otherwise reject; never silently retarget.
- Verify signed session, idempotent retry, reload, revocation, and cold reopen.
- Gate: genuine Playwright + backend + database run and final-head CI; only then ready for review.

Commit and push after each completed stage. Keep PR draft until all five gates pass. Do not merge without final-head evidence.
