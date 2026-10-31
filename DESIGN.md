---
version: alpha
colors:
  primary: "#103a4b"
  canvas: "#f4f7f9"
  surface: "#ffffff"
  text: "#172d38"
  muted: "#566f7c"
  border: "#dce5e8"
  highlight: "#fff0c2"
  danger: "#9a2727"
typography:
  sans:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
  utility:
    fontFamily: "ui-monospace, SFMono-Regular, Consolas, monospace"
rounded:
  control: "8px"
  panel: "12px"
spacing:
  compact: "8px"
  normal: "16px"
  section: "24px"
components:
  button:
    height: "44px"
  field:
    height: "44px"
---
# ExceptionDesk workbench

## Overview

Product register: a finance reviewer reconstructs a blocked invoice from sources and saves an attributable review recommendation. Extend `apps/web/prototype/finance-review.html`, not a rebrand. Refero live research was unavailable (subscription); primary evidence is the existing prototype and bundled craft guidance. Signature: linked source text and evidence highlight stay beside the selected finding and review history.

## Colors

Petrol navigation and primary actions; cool canvas, white reading surface. Amber highlights evidence/uncertainty, never approval. Red is reserved for errors; statuses also have text. CSS variables in `apps/web/review/workbench.css` implement these tokens and own all UI surfaces, controls, focus and scrollbar styling. No second theme adapter.

## Typography

Local system sans for interface and headings; monospace only for source text, hashes and references. No remote fonts or swaps. Body 16px, metadata 13px; no oversized marketing type.

## Layout

Desk layout: case summary and bounded finding queue, source viewer, review form and history. Responsive single column under 900px. Natural document scroll; panels own bounded overflow. Explicit previous/next finding navigation avoids an unbounded list. Mobile controls retain 44px targets.

## Elevation & Depth

Thin dividers and white surfaces organize evidence. No decorative gradients or repeated shadow cards; shadow only on focus/dialog surfaces when needed.

## Shapes

8px controls, 12px main work surfaces, restrained rounding. Selection uses a clear outlined/filled button state rather than a decorative accent stripe.

## Components

Use native buttons/links/labels and shared field/status helpers in workbench.js. The action selector is a native select with OS-owned popup. No date picker or bulk selection. Global scrollbar tokens cover every new overflow region; high contrast uses system colors. Reduced motion is respected; no decorative motion.

## Do's and Don'ts

Use source text and exact page/path/MIME references. Never imply that a review recommendation is approval. Keep synthetic/demo and persistence state visible. Never insert source or reviewer content as HTML. Do not invent proof, source authorship, balances or legal outcomes. Persist no drafts/tokens in localStorage; explicitly warn before abandoning unsaved edits.

## CaseProof regional fidelity extension

`apps/web/clearbrief/workspace.css` owns the existing ClearBrief dossier theme
(separate legacy client from the finance workbench); the fidelity panel reuses
that theme rather than transplanting finance tokens. Source-image/text pairing
is the signature. Conflict uses `--danger` plus warning text/icon, never color alone.
Native controls, local fonts and no remote media. Region images reserve intrinsic
geometry and reflow to one column below 760px. The canonical review panel is
`apps/web/clearbrief/fidelity-panel.js`, consuming the signed dossier API only.
