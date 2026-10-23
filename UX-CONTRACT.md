# Reviewer workbench interaction contract

Business authority: CONSTITUTION.md C01/C05/C07/C14/C19, ADR 0011 installed action catalog, ADRs 0012–0013. UI can record review requests/recommendations only; no installed approval permission, production upload, notification or payment action. Visual authority: DESIGN.md.

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Form | workbench.js field/status helpers | this contract + review command schema | review/correction | browser validation/save |
| Select/Listbox | native select | this contract | OS-owned popup | keyboard/open state |
| Scrollbar | workbench.css root tokens | DESIGN.md | geometry only | computed/browser |
| Toast | inline status live region | this contract | success/error/warning | browser announcements |
| CRUD | review service + same detail refresh | atomic receipt contract | append recommendation | HTTP/DB/browser |

The existing standalone prototype remains a historical local-file demo; the new workbench is the canonical connected synthetic flow. No parallel live customer route exists. Locale: en-BE copy, dates Europe/Brussels and explicit timezone; money strings come from domain output. No Japan market/locale scope.

Flow: select finding → inspect source/competing evidence/coverage → choose review action → supply rationale/correction → save → show committed receipt/history. Save remains disabled while pending; announce only after receipt. Corrections append a proposal, never overwrite originals or the extracted statement. A rejected finding remains available in the audit trail. Request-evidence records a request only, sends nothing.

Use `novalidate`, real labels, inline errors with aria references, first-error focus, stable button width. Native select is intentional. No alert/confirm/prompt. Preserve unsaved text on failures; in-app navigation with dirty edits uses an app-owned dialog, focus restoration and cancel/discard choices. Actual page unload uses beforeunload only for dirty state. No persistent client storage.

Snapshot/revision conflicts show an inline banner and a Reload case action; never silently overwrite or pretend save succeeded. A stable request ID is retained across ambiguous retries until a definitive receipt; changed input starts a new ID only after resolving the old attempt. Network loss leaves the draft intact. Abort/ignore superseded reads; no stale response may replace a newer case view.

Source text is rendered using textContent/text nodes. Server Unicode codepoint offsets are highlighted with Array.from, not UTF-16 slice offsets. Show original source version and parsed location; downloadable originals are attachments, not executable embeds. Draft export includes unresolved conflicts and missing evidence even after notes are saved. Integrity checks do not establish legal validity or approval.

Browser evidence: scripts/verify_review_browser.py. Static source/contract audit is supplementary, not a substitute for actual browser/DB checks.
