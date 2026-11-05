# Storyteller cockpit design audit

Reference: owner-provided CaseProof-Storyteller-Demo.html and app.js; inspected against main 79c6aee. The reference is a standalone synthetic simulation. This is a source-level comparison, not a visual browser or accessibility audit.

| Surface | Reference | Current frontend | Disposition |
| --- | --- | --- | --- |
| Palette | Paper #f6f6f3, ink #16181d, neutral borders | Blue-grey and petrol | Adopt neutral theme while keeping explicit status text. |
| Typography | Inter, Source Serif 4, JetBrains Mono from Google Fonts | System sans and monospace | Self-host the reference fonts with their OFL licenses and system fallbacks. |
| Workspace | Findings, draft, evidence | Findings and stacked inspection | Split existing draft and source/review into responsive panes. |
| Findings | Bordered cards and selection | Functional queue with filtering and pagination | Restyle existing buttons; retain navigation and states. |
| Inspection | Scan/OCR/diff tabs | Existing source viewer and correction/review | Offer a compact native-button switch between original pixels and available OCR positions. Keep the original visible. Source-text and correction-diff views remain separate and are not represented as a fabricated mode. |
| Intake and inventory | Cards and staged progress | Working forms | Inherit shared theme; complete layout redesign remains open. |
| Export and history | Simulated modal and timeline | Real artifact and history flows | Preserve real behavior; further visual alignment remains open. |
| Motion and dark mode | Animated transitions and dark mode | Light theme and reduced-motion support | No dark mode or decorative motion added. |

The implementation updates the theme and reading layout and applies shared surfaces to intake, inventory, exports, history and the DOCX editor. Browser comparison, responsive and keyboard review, signed workflow verification and exact reference parity remain open. No server contract or real decision behavior is changed.

## Screen-by-screen mapping

- Session and matter catalog: existing sign-in, matter list, new-matter form and report list retain their routes and access checks. Shared typography, input and list-card styling applies. The prototype does not define a complete signed-session design.
- Intake: four native file inputs retain their bounded preflight and readback; styled upload controls and grouped surfaces remain keyboard-operable. The prototype's simulated progress is not a source of transfer status.
- Inventory: confirmed sources and page-space mappings retain native controls, server confirmation and complete/incomplete disclosures. Grouped cards use the neutral surface.
- Findings: the existing bounded attention/all filters, paging, current snapshot and four separate dimensions remain unchanged. Draft and source/review panels are responsive; the selected finding and coverage remain visible.
- Source: PDF canvas, navigation, rotation, zoom, labeled OCR positions and search remain existing features; the reference's illustrative scan/OCR/diff tabs are not fabricated as a substitute for real data. Viewer canvas scroll and page-space labels use shared surfaces.
- Review and correction: receipt-bound review, exact correction preview, recovery and comparison continue to use their existing components and authorized APIs. Human and machine states remain separate.
- DOCX editor and Word handoff: existing editor-specific stylesheet adopts the shared ink, focus and neutral borders; native inputs and historical scope notices are unchanged.
- Exports and history: the real scoped release and frozen history use neutral cards and backend-provided states. Prototype hashes and fake report history are not copied.

## Remaining design decisions and validation

The uploaded prototype requests remote Google Fonts, whereas the frontend blueprint prohibits remote font services. Inter, Source Serif 4 and JetBrains Mono are served locally with their OFL licenses and system fallbacks. The reference also has dark mode and animated simulated transitions; neither is implemented in this increment. A measured browser comparison, manual accessibility and practitioner review, and the signed workflow must precede claims of full visual parity or production readiness.
