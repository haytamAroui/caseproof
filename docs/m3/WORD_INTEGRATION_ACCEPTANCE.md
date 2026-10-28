# Deferred Word companion — optional integration acceptance (not M3 or v1)

**Status:** historic read-only task-pane spike/reference only; no accepted real Word-host round trip. **Decision 28 October 2026:** [ADR 0018](../adr/0018-pre-submission-verification-freeze.md) and [ROADMAP.md](../ROADMAP.md) replace the prior “M3 = Word” product acceptance. **M3 is the independent web reviewer.** This file is a conditional **M6 Word-channel integration contract**, and cannot block v1, M1–M5, the first pilot or an independent verify-review-export release.

The previous Word-first document remains available in [Git history](https://github.com/haytamAroui/caseproof/blob/486b239926b681d76e1e3f79d30e3dc7098ab6d8/docs/m3/WORD_INTEGRATION_ACCEPTANCE.md). The existing `apps/word_addin/` is preserved for potential reuse; neither its existence nor its successful synthetic tests establishes product readiness.

## Trigger: prove Word adds customer value

Only activate the full Word track after M5 practitioner evidence, comparison with the web workflow, explicit owner scope approval and supported Office-host deployment/security review. Keep the scope narrow: start a CaseProof check from Word, inspect a source, optionally preview/insert a Stuk/Pièce pinpoint or correction, and recheck; no case-law AI or argument generator.

**No forked authority:** Word is an untrusted editing client of the same signed matter-scoped API as the web workspace; no independent source index, verification rule, reviewer grant, OCR confirmation, or evidence store. A mutable Word selection/offset is an editor-local reference and never a source anchor.

## Conditional host and API acceptance

1. Signed actor chooses only authorized matters, with token expiry, logout, offline/denied path and permission revocation tested in the actual Office host(s).
2. Capture selected draft text, document version and editor-range fingerprint; read-only lookup against pinned source/inventory/check snapshot. Preview original page and crop, not just model-generated text.
3. Before a write, revalidate current selection/paragraph, DOCX revision, exhibit revision and actor's `draft:write` authorization. Never insert into a stale range; no silent coauthor overwrite.
4. Preview citation in relevant NL/FR format with exact source version and page space, insert once via stable operation ID; handle lost acknowledgment, duplicate click, undo, comments, footnotes, lists, tables and tracked changes explicitly. Unsupported Office APIs are blocked and disclosed.
5. Save, close and reopen the **actual DOCX** in an approved Word host; source links reopen to the same preserved original; dependent check invalidation/recheck works; a user can reverse an edit.
6. Run real signed-user, synthetic-only smoke against current API with full audit, permission negative tests and supported-host matrix (Windows, Word web, macOS as actually tested). Do not claim host parity without proof.
7. Compare with the full web workflow on real lawyer time, setup/deployment friction and error rate. Word is worth shipping only if a buyer explicitly values that measured improvement.

## What this does not authorize

No legal certification, file submission, auto external share, new OAuth privileges, confidential source processing, additional law datasets or production launch merely because Word works. Deployment choices and adapter rights need independent approval.

**Exit (optional M6 channel):** reproducible real Office-host select/inspect/edit/undo/recheck/reopen via the **existing** API, with source integrity, current grants, saved DOCX formatting and evidence links verified. **Not part of v1 commercial exit.**

See [web journey](../PRODUCT_WORKFLOW.md) and [M4 document/report exit](../m4/DELIVERY_ACCEPTANCE.md).
