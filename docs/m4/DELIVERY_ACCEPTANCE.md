# M4 — Review, dynamic exhibits, verified artifacts and controlled delivery

**Status (2026-10-27): proposed acceptance; not product-complete.** This is a child specification of [ROADMAP.md](../ROADMAP.md) and [PRODUCT_WORKFLOW.md](../PRODUCT_WORKFLOW.md), not a new roadmap. No approved professional publication, court filing, recipient sharing or customer data use is inferred from existing synthetic export/review components.

## Product outcome

The lawyer can take an **exact reviewed Word draft version** and a confirmed matter exhibit register to a **usable, verifiable delivery package**:

1. source-linked DOCX/brief with precise NL `Stuk` and FR `Pièce` references;
2. generated exhibit index and deterministic bundle (with selected manually included exhibits);
3. hyperlinked PDF courtesy copy with resolvable internal/external references;
4. clear **Cite Check / Verification Run Record**, displaying checked scope, exclusions, status of every action, unresolved findings and provenance;
5. an immutable output manifest, recoverable release decision, and separately authorized download/share receipt.

The result is a complete **Clearbrief-style writing-to-delivery** path, not a claim of feature parity with US-specific legal databases, court-certified compliance or automatic filing.

## Review-and-release gate (F28, F35, PIV-08, 14–16)

- Review exact `case / draft revision / exhibit register revision / source universe / check run / candidate and correction history`. The reviewer inspects passage context and chooses keep/reject/qualify/correct/needs-evidence with rationale where required.
- Permit a firm reviewer or the explicit **solo practice** policy; label solo review as such, never independent review. Reviewer action is authorization/audit, not substantive judicial/legal correctness.
- Recheck after any dependent change; changed draft/source/exhibit/register/permissions/reviewer policy must invalidate affected release. Reject stale release even if the UI still shows a prior success.
- Require explicit **action-specific** publication permission distinct from read, evidence mapping and draft check. Authorization + manifest freeze + event ledger + stable operation receipt must be atomic; unknown acknowledgment must be reconciled before retry.
- Block publication on corrupt original bytes, unprocessed mandatory source, unresolved conflict, invalid output links, stale review, revoked access, failed rendering or absent audit receipt. Permit explicit *scoped* omissions only where reviewed output states them transparently and the release policy allows them.
- Final outputs are immutable, versioned and hashable; a newer output supersedes, never overwrites, an older one.

## Document and exhibit rendering contract (F30–F33, F35, PIV-14)

| Output | Required acceptance | Adversarial case |
|---|---|---|
| **Linked DOCX** | Preserve body/tables/footnotes/track-changes semantics where supported, exact citations, source/version links, saved Word roundtrip | Unsupported markup, reordered section, broken footnote, changed link after edit must be reported |
| **Hyperlinked PDF** | Same frozen draft and exhibit graph; navigate from fact citation to correct source/page and back where supported | PDF page vs printed page vs bundle page mismatch, rotated/cropped pages, missing target and duplicate labels |
| **Exhibit index** | Stable internal identity, displayed `Stuk/Pièce` numbering, aliases, annexes, ranges, selected order mode, optional uncited inclusion | Label collisions, insert/delete/reorder, manually included uncited exhibit and repeated cite |
| **Dynamic exhibit bundle** | Generated from one immutable ordered graph, correct thumbnails/bookmarks/page offsets, open every source | Multi-file exhibit, unsupported scan, source replacement and superseded index |
| **Verification report** | Exact scope denominator, source/representation hashes and versions, warnings/unknowns, reviewer dispositions, check version and timestamp | A clean check legitimately returns zero alerts; missing OCR pages never shown as fully checked |
| **Courtesy package/share** | Recipient-specific files and access, explicit redaction, expires/revokes hosted permission, bound release receipt | Revoked actor/recipient, wrong matter attachment, expired URL, stale download; downloaded copies cannot be remotely recalled |

**Freeze once, render many:** numbering, links, page offsets, index and bundle derive from one manifest; no separate Word/PDF/list numbering authority. Reopen **actual generated DOCX/PDF bytes** using a second reader, check hyperlink destinations, indexes, ordering, fonts where material, and SHA/digest against the release manifest. A unit test inspecting just JSON does not satisfy output integrity.

## Mandatory changing-dossier regression (CP-01 + DE-01)

Start from original E at V1, quote/citation A in draft D1, independent unrelated source U and released output O1. Simultaneously (a) replace E with immutable V2, (b) revise A while another reviewer holds D1, (c) remove one citation, (d) reorder exhibits and retain U manually.

Acceptance:
- O1 immutable and attributable to the old manifest; E V1 remains preserved.
- A-related check and review become stale, and the stale reviewer cannot publish.
- U and unrelated check records remain valid where their declared source scope is unchanged; a whole-corpus counterevidence search does become stale if its universe changed.
- The exhibit register remains independent of citation usage; removing a cite never silently removes a manual exhibit.
- New D2/E V2/current mappings produce fresh check C2 and release O2; every DOCX/PDF/index/bundle link is recalculated and validated.
- Concurrent release, crash after render, missing receipt or lost delivery ACK is idempotently reconciled without double publication; history stays intact.

## Real M4 end-to-end product acceptance

**No closed milestone without a live, completed user journey.** On an approved synthetic/rights-cleared staging dossier with genuine signed users:
1. Create private Belgian matter and preserve actual NL/FR/EN PDF/DOCX/scans; show failures and unprocessed-page denominators.
2. Confirm `Stuk/Pièce` mapping and select own/opponent document roles.
3. **Inside Word**, search evidence, inspect, insert and reopen at least one pinpoint; show partial/no-match scenarios.
4. Check full draft for exhibit, quote and same-role value mismatch; let a clean control produce zero findings.
5. Human reviewer decides, edits current DOCX reversibly, rechecks and signs off exact scope.
6. Generate real linked DOCX, PDF, index, bundle and verification record; verify all links with reopened bytes and exact manifest.
7. Release under explicit permission; download or share with designated recipient; test revoke/expiry. **Do not claim court filing** unless separate official receipt/integration exists.
8. Restore from interruption and show the same versions, decisions, history and output receipts after process restart.

A lawyer must be able to perform that journey with keyboard and screen reader accommodations appropriate to the supported surface, with NL/FR/EN labels and recoverable errors. Measure setup, complete task and correction time, false-alert review time and repeated use. Only approved security/privacy/customer gates permit non-synthetic client material.

## M4 exit and explicit exclusions

**Pass M4:** integrated M1–M4 lawyer-facing workflow, reviewed immutable artifact and safe delivery verified on actual generated files with repeatable regression and real signed staging actors. **Not required for M4:** a legal research database license, semantically complete legal citation validation, automatic procedural admissibility, actual e-Deposit submission or Falcon-style lawyer-as-service signoff. Those remain independently scoped PIV-17–19, partner and licensing decisions.

See [M3 Word acceptance](../m3/WORD_INTEGRATION_ACCEPTANCE.md) and [the Clearbrief feature matrix](../FEATURE_DELIVERY_MATRIX.md).
