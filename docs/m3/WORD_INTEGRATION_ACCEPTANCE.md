# M3 — Word evidence writing and citation loop: implementation and acceptance

**Status: early read-only synthetic task-pane spike; M3 is not implemented.** The spike reads a selection and displays a fixed example; it does not insert citations or connect to the API. No Word host has yet been tested. This document is an M3 acceptance contract subordinate to [the authoritative roadmap](../ROADMAP.md), [product workflow](../PRODUCT_WORKFLOW.md), [ADR-0017](../adr/0017-default-private-litigation-matters.md) and [CONSTITUTION](../../CONSTITUTION.md). It adds no separate backlog, authorizes no deployment and does not claim tested Word-host support.

## Why Word is a launch requirement rather than a late accessory

CaseProof deliberately reproduces the **end-to-end Clearbrief-class workflow** for Belgian lawyers: find passages against a source record while writing, safely insert precise factual citations, check and correct writing, and create an authenticated, navigable final document. A stand-alone M2 factual check is a measurable **backend slice**, not the intended complete product. F01, F07, F08, F11, F15, F37 and F40 share the M3 evidence-writing contract; F30–F35 reach full product acceptance only with M4 output tests.

## Early integration proof (parallel to M1-B/M2-B; not an M3 pass)

Do an early, **synthetic-only** Office integration spike before freezing client-facing API payloads:

1. Create an installable Word task-pane shell and a documented local developer sideload path. Record precisely which Word hosts/versions and document formats were *actually tested* (desktop Windows, Word web, macOS as available). **Do not promise parity on untested hosts.**
2. Select a sentence in a synthetic DOCX; capture an editor-local selection/range fingerprint, the document revision/content identity, and the case/brief source graph reference. Round-trip to an opt-in mock authenticated API with a fixed evidence passage. Editor offsets/selection are **not** evidence anchors.
3. Preview a citation (including NL `Stuk` and FR `Pièce` formats), revalidate the selection and document revision immediately before insertion, insert once, reopen the original passage, undo, and recheck. Test a changed selection, a concurrent edit and a changed source version.
4. Validate survival through save, close/reopen and DOCX export. Record formatting, footnotes, tables, numbering, tracked changes and content-control behavior; mark unsupported combinations as blocked. Never silently flatten/redline/alter an opponent's original.
5. Prove sign-out, revoked matter grant and expired token cannot retrieve sources or write. The test uses only synthetic material until M1-C confidentiality gates are met.

This spike is a **contract-risk reduction** task under PIV-11 and can progress alongside M1/M2. It neither closes M3 nor waives review of the eventual Office permissions, network communication and document access.

## M3 minimum usable Word task pane

| User action | Required result | Negative/edge acceptance |
|---|---|---|
| Install and authenticate | Supported Office client can sign in, choose only authorized private matters and display current scope | Unsupported hosts fail visibly; no secrets/tenant grants stored in document XML; revoked actor denied |
| Select factual phrase | Identifies text/paragraph/table/footnote and current DOCX revision; links to typed assertion graph | Multi-range/no-selection, stale/edited selection and coauthor conflict never cause misplaced edits |
| Find evidence | Search indexed, authorized NL/FR/EN and mixed matter sources; rank with passage, surrounding context, document and page | Missing/OCR-failed pages disclosed; zero matches valid; no model hallucination represented as verified source |
| Inspect passage | Open original/clearly marked representation at stable source-version/locator with surrounding text | Missing/corrupt source, ambiguous or mismatched page blocks citation authority |
| Insert factual citation | Preview exact selected span, `Stuk/Pièce` alias, pinpoint and format; revalidate and insert one reversible link | Wrong alias/page, repeated click, lost ACK, changed range or revoked grant fail closed; repeat is idempotent |
| Analyze or recheck | Check current draft/revision; show separate literal fidelity, value-candidate, semantic-proposal and not-assessed results | Clean draft may have zero findings; edits invalidate only affected results; partial corpus never shown as a pass |
| Correct and undo | Show source-bound change preview, reviewer disposition and current range; reversible edit with recorded revision | Preserve footnotes, list numbering, citations, comments and tracked changes where supported; never modify opponents' preserved originals |
| Hand off to M4 | Exact saved DOCX version and source/exhibit graph transferred to render/review with a stable manifest | Edited-after-review documents and broken links cannot publish as current |

## Required technical contracts

- **Identity and case scoping:** same signed actor, current active organization membership, **exact per-matter grant**, and action-specific rights for search, citation insertion, checking, reviewing and publishing. Do not let a Word document, task-pane JavaScript or request header supply authoritative actor/org/case scope.
- **Two distinct locators:** editor-range fingerprints bind a mutable draft revision; Kernel source anchors bind immutable source bytes and representation/page provenance. Never serialize an Office character offset as a proven PDF coordinate.
- **Documents and scope:** own, opponent, response and filed copies are distinct typed roles; source universe/index completeness and draft language cannot be inferred from the UI language.
- **Editing protocol:** preview → freshness/snapshot validation → apply with stable operation ID → acknowledgment/reconciliation → undo → dependent-check invalidation → recheck. A timeout is `OUTCOME_UNKNOWN`, not approval to replay an edit blindly.
- **Secure browser/Office surface:** authenticated API calls, content-security-policy and origin rules, token lifetime/revocation tests, bounded text crossing process boundaries, sanitized diagnostics; no logging client privileged text or leaking it to LLMs/telemetry.
- **Languages:** actual keyboard text, citation labels, dialogs and error copy in NL/FR/EN. UI language, brief language, source language and output language are independently selectable.
- **Accessibility:** keyboard-only path, focus restoration from the task pane to Word, screen-reader labels, announcement of staleness/scope, contrast and error recovery. No mandatory color-only warnings.

## Release evidence and fixtures

- A reproducible Word-host matrix, install instructions, synthetic DOCX fixtures including tables/footnotes/tracked changes, pinned Office/add-in versions, screenshot/video evidence and source-insertion round-trip hashes.
- At least one full **real signed-user, safe-source** M1→M2→M3 integration on approved development staging, after M1 security gate: create matter → ingest evidence → confirm exhibits → find paragraph in Word → insert and reopen citation → check → correct and undo → recheck.
- Repeated-action, disconnected/offline, duplicate selection, source replacement, case revocation, coauthor-edit, force-close and reopen tests; no unverified host compatibility or invisible edit loss.
- A paired human task benchmark on synthetic/rights-cleared NL/FR/EN files against manual Word/PDF and authorized competitor trials, measuring complete task time including setup, corrections and false alarms.
- M3 **does not** grant a right to publish or file. M4 controls actual exports, reviewer release and recipient access.

**Exit:** a user demonstrably completes the **write-with-evidence loop inside a supported Microsoft Word host**, can open the source of every inserted evidence citation and undo/recheck safely. A generic web editor or read-only mock task pane alone does not pass M3.
