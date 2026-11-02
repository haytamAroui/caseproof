# F4 v3.1 reviewer workspace acceptance — PR #176

**Scope:** S4–S8, S11, S12. F4 is not a new verification engine or a second persistence ledger.

## Traceability and implementation

| Stage | Existing backend authority | F4 UI | Exit evidence |
| --- | --- | --- | --- |
| S4 reference discovery | canonical `discover_docx_references` and per-story coverage | exceptions-first filtered queue; all-results escape | synthetic original and unsupported notices |
| S5 frozen verification | `DossierStore.reopen`, `DossierView` | four separate dimensions; coverage denominator | snapshot-bound read and wrong-scope denial |
| S7 source inspection | existing signed viewer and raster endpoints | source pixels, page spaces, bounded anchored DOCX excerpt | 200% zoom, page-6 alignment, no fabricated DOCX page |
| S8 signed human review | `POST /dossier/reviews`, reviewed regions, Postgres decision rows | explicit region confirmation, required rationale, canonical disposition, durable ledger GET | lost acknowledgment, exact request reconciliation, cold resume |
| S11 history | report catalog + historical read-only routes | source pixels and report, no review write | old snapshot remains read-only, deny stale review |
| S12 unknown outcomes | stable `request_id`, source authorization, durable ledger | never optimistic saved; explicit reconciliation and same request replay | real signed browser lost-ACK and restart |
| S13 confidentiality | current grants, no browser token/quote persistence | in-memory forms, denial cleanup | protected zero-residual fixture; independent gate open |

**Boundaries:** The DOCX excerpt is derived parsed plain text from a specific
preserved original version. It does not claim Word pagination, editable OOXML
offsets, or fully supported Office story types. Unsupported/split/ambiguous
anchors fail closed. Visual-region checkboxes are human inputs, never computed
review outcomes.

**Current backend request:** canonical `VisualDecisionBody`; only three
canonical `CONFIRMED_*` decisions. Existing signed RPC is the sole review
write authority. The strict ledger GET requires a current snapshot; past
snapshots are read-only and prior decision rows are not re-certified.

**Testing:** Python strict models/negative contracts, generated JSON Schema /
TypeScript / AJV parity, Playwright actual PDF.js worker, signed browser
synthetic intake through actual Supabase Auth/Storage/RLS, review receipt
lost-ACK and cold reopen, revocation and teardown. CI success alone does
not grant production release.

**Separate open gates:** real-format NL/FR/EN representative independent
legal review, manual keyboard/screen-reader assessment, customer data handling
and processing-location/egress/retention signoff, and production hosting.
