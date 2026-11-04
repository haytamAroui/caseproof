# Structured DOCX editing — CaseProof scope and safe extension

**4 November 2026.** This record distinguishes implemented editing, unsupported DOCX
structures, and the separately proposed rich-editor integration. It is not a pilot
release approval or legal/security sign-off.

## Implementation in this branch

The existing F5 correction flow is **finding-bound**, not arbitrary text editing:
a signed user's current report finding, source version, immutable snapshot,
saved review receipt and verified locator must all agree. The preview is a
derived DOCX digest and bounded before/after summary, not full document bytes.
Commit preserves the original, creates a new activated derivative, and requires
fresh verification with no transfer of old human approvals.

This branch extends **plain single-run and multi-run reference replacement** from
direct main-body paragraphs to **simple paragraphs directly inside table cells
in top-level Word tables**. The original paragraph-index contract remains
backward compatible: indices 0–49,999 address direct body paragraphs; 50,000–
99,999 address top-level table-cell paragraphs in document order. These are
opaque selectors, never authority on their own. On every mutation the backend
reopens the exact original, checks frozen offsets, reference text, source hash,
snapshot, actor/matter and paragraph identity, then reruns the resolver. Forged,
stale, nested, unsupported or ambiguous targets fail closed. No migration or
external document service is introduced.

The XML writer preserves all original ZIP members except `word/document.xml`
and keeps unaffected run properties. This does **not** claim full round-trip
formatting fidelity; actual Word host testing remains a separate requirement.

| Requested ability | Status after this branch | Boundary |
| --- | --- | --- |
| General main-body paragraph editing | **Not implemented** | Only an exact already-detected and reviewed citation can change |
| Simple top-level table-cell citation editing | **Implemented pending CI/acceptance** | Exact frozen finding and source-bound locator; no nested tables |
| Textboxes/drawings/headers arbitrary editing | **Not implemented** | Unscanned/unsupported story and shape semantics must not be inferred from flattened text |
| Native tracked-changes edits/accept/reject | **Not implemented** | Unresolved tracked changes continue to abstain |
| Full Word-like ribbon, pagination, undo, rich layout | **Not implemented** | Requires a separate editor engine and editable-document workflow |

## Rich-editor integration decision gates

**Do not embed a library as a shortcut around the evidence engine.** A full
Word-style UI would require separate role-scoped edit authorization, immutable
source and derivative manifests, validated import/export, loss/round-trip
diagnostics, preserved revision provenance, durable unknown-outcome recovery,
new version activation, fresh recheck and independent privacy/security review.

Vendor findings current at this date:

- [SuperDoc](https://docs.superdoc.dev/editor/) is a DOCX-backed editor, but
  its public license is AGPLv3 unless a commercial license is obtained. Do not
  add it to the existing no-AGPL product dependency graph.
- [ONLYOFFICE](https://helpcenter.onlyoffice.com/docs/faq/docs-community.aspx)
  Community Edition is AGPLv3; a commercial integration license is a separate
  decision.
- [OpenDoc](https://github.com/CasualOffice/opendoc) is Apache-2.0 and supports
  a browser editing experience, including tables and revision UI, but its
  embed package is pre-release and the published host integration explicitly
  does not yet accept document bytes/URLs from the host. It is not a working
  authenticated CaseProof integration today. Reassess the stable API and
  container/network behavior before adding any dependency.

No dependency added, no AGPL license accepted, no external egress enabled.

## Acceptance to extend further

1. Final-head Python, frontend, signed-journey and CI checks must be green.
   Run an actual signed table-cell edit → preview → commit → recheck journey
   before declaring the expanded table scope live-accepted; unit/router
   tests are not a signed browser substitute.
2. Independent reviewer must assess table selector, source authorization,
   immutable bytes and unknown-outcome recovery. Test hostile OOXML, nested
   tables, fields, textboxes, tracked revisions and styling in desktop Word.
3. For unrestricted editing, approve a separate product architecture and
   editor-engine license first. Preserve all authoritative CaseProof integrity
   gates. Until then **do not** label this a complete Word editor.
