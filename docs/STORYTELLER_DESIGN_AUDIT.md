# Storyteller cockpit design audit

Reference: owner-provided CaseProof-Storyteller-Demo.html and app.js; inspected against main 79c6aee. The reference is a standalone synthetic simulation. This is a source-level comparison, not a visual browser or accessibility audit.

| Surface | Reference | Current frontend | Disposition |
| --- | --- | --- | --- |
| Palette | Paper #f6f6f3, ink #16181d, neutral borders | Blue-grey and petrol | Adopt neutral theme while keeping explicit status text. |
| Typography | Inter, Source Serif 4, JetBrains Mono from Google Fonts | System sans and monospace | Use system fonts and local serif fallback. Exact self-hosted fonts remain open. |
| Workspace | Findings, draft, evidence | Findings and stacked inspection | Split existing draft and source/review into responsive panes. |
| Findings | Bordered cards and selection | Functional queue with filtering and pagination | Restyle existing buttons; retain navigation and states. |
| Inspection | Scan/OCR/diff tabs | Existing source viewer and correction/review | Keep real modes; exact tab parity requires further design work. |
| Intake and inventory | Cards and staged progress | Working forms | Inherit shared theme; complete layout redesign remains open. |
| Export and history | Simulated modal and timeline | Real artifact and history flows | Preserve real behavior; further visual alignment remains open. |
| Motion and dark mode | Animated transitions and dark mode | Light theme and reduced-motion support | No dark mode or decorative motion added. |

This initial implementation changes the theme and reading layout only. Browser comparison, responsive and keyboard review, signed workflow verification and remaining screens are open. No server contract or real decision behavior is changed.
