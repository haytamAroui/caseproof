# CaseProof — authoritative frontend foundation and M3/M4 blueprint

**Version:** 1.0 · **Date:** 1 November 2026 · **Owner:** CaseProof engineering; independent acceptance owners not yet assigned.

**Status:** Owner-requested engineering direction. The foundation is implemented in PR #162; the remaining workspace capabilities below are acceptance requirements, not delivered features. This document grants no deployment, client-data, legal or milestone approval.

**Single entry point:** Read this file before designing, implementing or reviewing the real CaseProof frontend in `frontend`. It owns frontend structure, interaction, design and acceptance rules. `AGENTS.md`, `DESIGN.md`, `UX-CONTRACT.md` and `README.md` in this directory are pointers, not competing specifications. Legacy finance/ClearBrief screens are regression references, not the new client's architecture.

## 1. Authority, scope and change protocol

Repository [CONSTITUTION.md](../CONSTITUTION.md), [ADR 0011](../docs/adr/0011-architecture-freeze-and-first-finance-slice.md), [ADR 0022](../docs/adr/0022-verification-contract-report.md), [ADR 0025](../docs/adr/0025-deployment-data-retention-and-model-authority.md), and the [roadmap](../docs/ROADMAP.md) retain authority for security, evidence and product behavior. [ADR 0026](../docs/adr/0026-frontend-foundation.md) records the frontend decision. If this file conflicts with those contracts, resolve the conflict explicitly before implementing the affected behavior.

M3 is the authenticated web review workflow. M4 is safe reviewed output and reproducible reopening. First market: Belgian post-assembly DOCX brief, inventory, text PDF and scanned exhibits; NL/FR/EN. German, legal research, filing, a general DOCX editor, public MCP hosting and a Word-mandatory product are outside this increment.

Use **MUST**, **MUST NOT** and **SHOULD** as engineering requirements. A future capability remains OPEN until its evidence passes. An agent MUST NOT invent an owner, signer, permission, measurement, legal opinion or acceptance result.

Every material change records scope, accountable owner, affected contracts, implementation, test/artifact links, limitations and rollback. Update this file when a durable UI decision changes; update runtime code and tests in the same PR. Never rewrite the blueprint merely to legitimize implementation drift. Keep versioned historical evidence distinct from current-head results.

## 2. Outcome and non-negotiable invariants

The lawyer can create an authorized matter, intake and confirm preserved files, inspect each finding against source pixels and text, record a separate human decision, preview a supported correction, recheck, export and reopen the actual bytes after restart.

| ID    | Invariant                                                                                                                                                                                       |
| ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| UI-01 | Python application services own verification, authorization, workflow transitions, audit and export. React never recomputes or upgrades a verdict.                                              |
| UI-02 | Identity, page mapping, fidelity and human support remain independent. Coverage/processing completeness is shown separately. No overall GREEN/RED verdict or blanket verified badge.            |
| UI-03 | A quotation match is not semantic support, authenticity or human approval. Zero detected references is not complete verification.                                                               |
| UI-04 | Every sensitive read/write is server-authorized for the current actor, matter, source version and applicable snapshot. Host-injected credentials are not permission proof.                      |
| UI-05 | Missing, unsupported, ambiguous, partial and unassessed remain explicit. A crop pointer does not establish page mapping.                                                                        |
| UI-06 | Human decisions change only after a durable authorized backend receipt. Local hashes, flags and timestamps cannot create a review ledger or signature.                                          |
| UI-07 | Changed draft, inventory, source, representation or review revision cannot silently reuse stale confirmation or release.                                                                        |
| UI-08 | Originals remain immutable. Corrections create a new draft version; generated previews/exports are derivatives, never primary sources.                                                          |
| UI-09 | Confidential content, bearer tokens, rationale and source quotations are absent from analytics, logs, URLs and persistent browser storage by default. Opaque IDs/hashes may still be sensitive. |
| UI-10 | A local interface, CSP or synthetic browser test does not prove whole-system zero egress or professional-secrecy compliance.                                                                    |

## 3. Technology decisions and dependency ownership

| Layer          | Decision                                                             | Current implementation / adoption rule                                                                                                                                             |
| -------------- | -------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Build/runtime  | Vite static build; Node is build tooling                             | Vite 8.3.5 baseline. Production does not require a frontend Node server. Static host configuration is separately accepted.                                                         |
| UI             | React + strict TypeScript                                            | React 19.3.1 / TypeScript 6.0.3 baseline. TS 7 was incompatible with the selected lint toolchain. Use latest compatible stable versions, never force peer conflicts.               |
| Routing        | React Router                                                         | 8.5.1 baseline; do not downgrade to v7 because an old example says v7.                                                                                                             |
| Server state   | TanStack Query                                                       | v5. No persistence; retries explicitly disabled in foundation. Cache is not permission or verification authority.                                                                  |
| Styling        | Canonical CSS tokens and shared primitives                           | Current owner `src/app/theme.css`. Tailwind/shadcn may be added through a documented adoption change; neither is currently installed.                                              |
| API contract   | Python projection → JSON Schema → TypeScript + precompiled validator | Existing dossier endpoint stays canonical. Unknown consumed states fail closed.                                                                                                    |
| Findings table | Native semantics first; TanStack Table if needed                     | Not installed. Add for measured filtering/sorting/paging needs, not merely because a blueprint lists it.                                                                           |
| Viewer         | Replaceable evidence adapter                                         | No engine selected. Compare bounded server-rendered images with patched raw PDF.js. EmbedPDF/Lector require the same evidence if reconsidered. Never load two engines by accident. |
| DOCX           | Read-only, explicitly derived preview                                | No engine selected. `docx-preview` cannot promise Word-identical pagination.                                                                                                       |
| Diff/icons     | Add narrowly when a feature needs them                               | A read-only redline can use semantic `del`/`ins`. Evaluate any diff library's maintenance, compatibility and license.                                                              |
| Verification   | Vitest, Playwright, axe, ESLint, TypeScript and architecture checks  | Locked versions in `package-lock.json`; no test-only bypass in product code.                                                                                                       |

`package.json` and `package-lock.json` are authoritative for installed versions. Versions above identify the tested foundation, not an instruction to freeze patches forever. Dependency updates require compatibility, security and affected regression checks. Public source is not automatically reusable. Record license/notices, origin commit and modified files for any copied source. Preserve notices and review transitive engine/assets licenses. Do not copy incompatible GPL/AGPL or commercial code; do not claim that rewriting after studying a repository automatically resolves licensing obligations.

## 4. Structure and dependency direction

| Directory                   | Owns                                                                                   | May depend on                          |
| --------------------------- | -------------------------------------------------------------------------------------- | -------------------------------------- |
| `src/app`                   | Composition, routes, providers, session/query lifecycle, app error boundary, theme     | Feature public entry points and shared |
| `src/features/matters`      | Matter selection/create workflow when implemented                                      | Its own internals and shared           |
| `src/features/intake`       | Upload/confirm/recovery workflow when implemented                                      | Its own internals and shared           |
| `src/features/verification` | Findings, dimension display, filtering and snapshot reads                              | Its own internals and shared           |
| `src/features/evidence`     | Viewer adapter, source/crop inspection and coordinate display                          | Its own internals and shared           |
| `src/features/review`       | Human decision intent/rationale and receipt display when implemented                   | Its own internals and shared           |
| `src/features/corrections`  | Preview/apply/recheck interaction when implemented                                     | Its own internals and shared           |
| `src/features/exports`      | Export/reopen interaction when implemented                                             | Its own internals and shared           |
| `src/shared/api`            | Generated contracts, runtime validation, authenticated transport, error classification | Shared only                            |
| `src/shared/session`        | Memory-only credential source, session generation, cancellation/cleanup                | Shared only                            |
| `src/shared/ui`             | Reusable accessible primitives; no business-state inference                            | Shared only                            |
| `src/shared/lib`            | Small proven cross-feature utilities when needed                                       | Shared only                            |

Create a feature directory when implementing its first real behavior; no empty framework scaffolding. Within a feature, separate presentation, workflow coordination and API adapters as complexity requires. Do not add a repository/interface for every request. A viewer port is justified because its implementation is deliberately replaceable.

Features MUST NOT import app or another feature's internals. Cross-feature orchestration belongs in app. App imports features through `index.ts`; no wildcard exports. Shared MUST NOT import app/features. Network calls go through shared transport. AST negative-control tests enforce direction and detect common storage/evaluation/network shortcuts; static checks are not a sandbox against malicious code.

## 5. API contracts and state ownership

Python response validation/schema is the source for consumed wire fields; generated TypeScript MUST NOT be edited. Validate untrusted API responses at runtime as well as compile time. PR #162's `DossierView` is a **partial read-only projection**, not the complete M3 contract. Expand it against actual canonical fixtures before consuming additional fields.

Maintain separate per-dimension types. Do not introduce one universal state union that permits an identity state in the human-support field. Do not replace backend enum values with `IDENTITY_OK`, `PAGE_OK` or an overall color model. Unknown future enum values require an explicit compatibility path, not a success fallback.

Three page spaces are distinct: physical exhibit-PDF page, printed label and bundle-PDF page. Preserve each backend state, mapping basis and ambiguity. Null means unknown/unmapped unless the backend explicitly records not applicable. Roman printed labels are strings. Persisted exact coordinate/decimal-string contracts remain intact; numerical conversion is confined to display transforms and never changes canonical values or hashes.

| State                                                               | Owner / lifetime                                     |
| ------------------------------------------------------------------- | ---------------------------------------------------- |
| Findings, source identities, snapshots, permissions, saved reviews  | Backend authority                                    |
| Fetched report and processing state                                 | TanStack Query, memory only, scope/session-keyed     |
| Matter/brief/finding navigation and non-sensitive committed filters | Router; never quotes/rationale/tokens                |
| Unsaved rationale, active inspector mode, transient selection       | Feature-local state; explicit loss/recovery behavior |
| Credentials, cancellation, query and object-URL cleanup             | Central session boundary                             |

Every read checks exact case/brief/snapshot/source bindings before display. Requests have bounded time/size and cancellation. Reject redirects and unexpected content types. Do not display raw server error bodies. On session end or observed 401/403, abort reads, invalidate the generation, clear caches, revoke object URLs and remove private views. A late response cannot repopulate a cleared or changed session. Unobserved server revocation cannot erase information already read; do not imply continuous revocation detection unless implemented/tested.

Future writes MUST retain a stable operation/request ID for the exact submitted payload, prevent duplicate submit and classify definitive rejection versus unknown completion. Never automatically retry review, correction or release writes. An ambiguous outcome requires receipt lookup or retry of the same authorized operation through the backend contract; changed input cannot silently replace it. No optimistic confirmation ledger.

## 6. Deployment, hostile files and browser security

Use same-origin application API calls where possible. The development proxy targets the existing loopback `/v2` API; never invent a parallel `/api` contract or expose dev fixture/admin RPCs to the browser. Loopback serving is a mode choice, not proof that all processing is local. Hosted/hybrid/firm-controlled/offline modes require separate ADR 0025 evidence.

Serve production JS/CSS/workers/WASM/fonts from approved pinned assets. No CDN, analytics, session replay, remote fonts or document-bearing external URLs. No service worker, offline persistence or background synchronization without a separate retention/revocation design. Keep source downloads explicit and authorized; never treat a download as proof the human inspected it.

Production response headers MUST enforce CSP, `nosniff`, `no-referrer` and sensitive-response `no-store`. `security-headers.conf` records the intended baseline; the actual reverse proxy must be tested. Vite preview is not a production server. Prefer `default-src 'none'`, narrowly scoped `script-src`, `style-src`, `connect-src`, `img-src`, `font-src`, `worker-src`, `object-src 'none'`, `base-uri 'none'`, `form-action` and `frame-ancestors 'none'`. A meta policy is supplementary, not an equivalent replacement. Do not add `unsafe-inline`, `unsafe-eval`, blob workers or WASM permissions preemptively. Vite development/HMR permissions must be limited to development and never copied into production.

PDF/DOCX bytes are hostile input even after backend acceptance. Browser preview does not bypass bounded intake. PDF.js options must disable unnecessary scripting/evaluation and external resource behavior for the pinned version; terminate loading/render tasks and destroy documents/workers on switch/signout. Prevent untrusted links, attachments or active annotations from executing. Test hostile-file/resource limits and patch advisories. Workers isolate work but are not an automatic hostile-content security boundary.

Server-rendered images reduce browser PDF parsing exposure but retain renderer and image-decoding risks. Rendering must stay isolated, resource-bounded, hash/version-bound and server-authorized. Accessible extracted text must accompany pixels. No rendering path gets an exemption from source/representation provenance.

Do not display “0 bytes external egress”, “compliant with OVB/Avocats.be” or “secure because local”. A deployment badge may describe configured mode and link to a dated measured receipt with its scope/limits. Browser-request monitoring is one test, not whole-process/OS/network proof. Security/privacy/professional-secrecy acceptance remains independently owned.

## 7. Evidence viewer and coordinate acceptance

Default inspection pairs preserved pixels, separately labelled extracted text and provenance. A PDF canvas/text/overlay stack is an implementation candidate, not a mandated engine. Layer ordering and pointer behavior must preserve selection and keyboard access without letting overlays hide uncertainty or capture every interaction.

A coordinate record MUST identify original/representation hashes, physical page, coordinate space, origin, units, page bounds, rotation and relevant CropBox/MediaBox. Reject missing/inconsistent geometry; do not guess. Transform the box using the actual rendered viewport (including page origin, CropBox offset, units, rotation and scale), then project into the CSS overlay space. Percentage coordinates are valid **after** this transformation, not a substitute for it. Account for device-pixel-ratio canvas scaling separately from CSS geometry.

On document/reference change, cancel obsolete loading/render tasks and bind the pending target to exact source version, snapshot and selection generation. Wait for the correct page/render to become ready, revalidate the target, then focus/scroll. No stale render can replace the current document or scroll a newly selected finding. Smooth motion respects reduced-motion preferences. Keyboard users can reach the same target without hover or dragging.

| Fixture/workload                           | Required evidence                                                                                                                                |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Clean text PDF                             | Exact target box and matching source/version; native text remains selectable where offered                                                       |
| Image-only scan                            | Pixels visible; absent OCR remains unassessed; crop matches preserved image                                                                      |
| Rotated pages 90/180/270 degrees           | Expected target stays aligned after rotation, zoom and pane resize                                                                               |
| Non-zero CropBox origin / mixed page sizes | Explicit transforms align to the right content; no percentage-only shortcut                                                                      |
| Repeated quotations / multiple boxes       | No ambiguous selection promoted to a unique match                                                                                                |
| 200-page file                              | Bounded rendering/virtualization, measured load/navigation/memory, cancellation and cleanup; no claim that a UI test proves 200-page backend OCR |
| Hostile/oversized/corrupt input            | Bounded failure; no script/external resource execution; useful error without private-data logging                                                |
| Switch/signout/revocation race             | No wrong-source overlay, delayed page or retained private object URL                                                                             |

Compare server-image and patched raw-PDF.js candidates using the same fixtures and expected transforms. Record pinned engines/assets, browser, hardware/runner, pixel/CSS error tolerance, performance budget, actual measurements and reviewer. Define tolerances/budgets before measurement; do not invent passing numbers afterward. Viewer adoption requires the recorded comparison. Its absence keeps the engine unselected.

## 8. DOCX preview, anchors and corrections

A browser DOCX rendering is a derived representation, not Word layout or filing proof. `docx-preview` page-break options cannot establish true Word pagination. Unsupported fields, headers/footers, tables, text boxes, tracked changes, notes and missing regions must remain disclosed according to the backend coverage manifest. Sanitize/disable active/external/HTML-part content and impose input/DOM/image/font limits before any DOM-rendering adapter is accepted.

Citation anchors bind to backend draft version, part/region, declared offset encoding, range and reference ID. Backend bookmarks may assist only after validating their bindings. Literal-text search is a navigation convenience; repeated or split-run text cannot authorize a correction. Ambiguous or unsupported anchoring must stop and show why. Never mutate the preserved DOCX to make navigation work.

A correction preview shows original and replacement strings with semantic `del`/`ins`, scope and downstream effects. The backend validates the supported range and creates the derivative. Apply uses the existing preview/reserve/upload/fresh-readback/activate contract; refresh/recheck the new draft and keep prior originals/reports. Do not promise arbitrary Word comments or tracked changes beyond actual export support. Preview similarity alone is not an accepted corrected DOCX.

## 9. Findings, inspection modes and human review

Use a bounded queue/table with explicit dataset navigation. If adopting TanStack Table, retain semantic table/button controls; an ARIA grid requires its full keyboard model. Filters operate on server-supplied states and disclose scope/count denominators. Prefer “Needs review”, “Page unmapped”, “Source missing” and specific dimension labels over a global red/yellow/green classification. Four compact cells are acceptable when full text and explanations remain accessible. Coverage is never compressed away.

`NOT_IN_INVENTORY` requires confirmed-complete inventory. An inventory entry with no supplied source is `SOURCE_MISSING`. “Uncited inventory item” requires sufficiently complete draft discovery; otherwise label it as not detected in the assessed regions. Neither condition is silently assigned a legal consequence. English Exhibit references remain unsupported human-review items; PR #160's six notices are not successful matches.

Show PDF/printed/bundle page states together, including unknown, conflicting and not-applicable distinctions. Display draft quotation, original-language context, extracted text and image separately. “Scan / OCR layer / Quote diff” is a useful candidate, but OCR overlays must be labelled derived, preserve geometry/line wrapping and never obscure the original irretrievably. Provide a side-by-side alternative and plain text for assistive technology. Diff highlights character differences only; it does not decide legal or semantic support.

A human review requires current server-bound scope, source/snapshot inspection, an explicit disposition and rationale. UI reports “saved” only after the durable receipt. It cannot turn a deterministic conflict into agreement. Show actor/time/revision from the backend receipt, not browser assertions. Stale state is server-derived and considers all relevant versions; show persistent text/reason and required reinspection, never flashing badges. A hash is integrity evidence, not a qualified lawyer signature.

Shortcuts SHOULD include J/K or arrows for finding navigation, Space for inspection and E for correction preview when available. Single-character shortcuts need discoverability and a way to disable/remap or constrain them to the focused component. Ignore editable targets, IME composition and conflicting browser/assistive commands. C/X MUST NOT silently create a confirmation. They may open the relevant action; committing still follows explicit inspection/rationale/permission rules. Advance only after receipt, preserving the prior finding/history and recoverable failures.

## 10. UI ownership and accessibility contract

| Capability     | Canonical owner                                        | Source of truth                             | Allowed variants                                                     | Verification                                                       |
| -------------- | ------------------------------------------------------ | ------------------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------ |
| Form           | shared primitives + feature form                       | This blueprint and generated request schema | Open report / intake / review / correction as implemented            | Labels, inline errors, first invalid focus, duplicate-submit tests |
| Select/Listbox | shared/ui when introduced                              | Deliberately native or authored per feature | Native platform popup / accessible authored listbox                  | Keyboard, open popup, focus, locale and narrow viewport            |
| Scrollbar      | src/app/theme.css                                      | Section 11 runtime tokens                   | Geometry only                                                        | Visible global baseline, forced colors, narrow/reflow              |
| Toast          | shared/ui/Notice or accepted shared notification owner | Server outcome and this blueprint           | Inline status / alert; transient notification only where appropriate | Live-region and failure-state tests                                |
| CRUD           | Feature workflow + backend service                     | Canonical application contracts             | Only installed operations                                            | Authorized end-to-end receipt/reopen/retry tests                   |

Target WCAG 2.2 AA. Use native semantics, real labels, visible focus, sufficient contrast, logical headings/landmarks and skip navigation. Meaning never depends on color, hover, flashing, dragging or a keyboard shortcut alone. Every drag/resize action needs a keyboard alternative. Modal primitives need title/description, focus placement/trapping/restoration, Escape and reachable actions. Shared controls cover hover, focus, pending, disabled and error states.

Forms use noValidate with owned inline errors, aria-invalid/aria-describedby, preserved input and first-invalid focus. Avoid browser alert/confirm/prompt. Stable control geometry and meaningful busy state prevent accidental double actions. Loss of unsaved work uses a scoped accessible confirmation; no persistent recovery cache is introduced silently. Search is cancelable/stale-safe and IME-safe; clear is immediate and keyboard accessible. Non-empty search has a clear action.

Verify loading, empty, no-results, errors, slow requests, timeout, 401/403, stale 409, unknown completion, long localized text, narrow layout, 200% zoom/reflow, high contrast and reduced motion as applicable. NL/FR/EN copy, aria labels and date/number formatting must follow locale. Use Europe/Brussels for human event display with explicit timezone; preserve server timestamps. Automated axe checks do not establish manual screen-reader or practitioner acceptance.

## 11. Visual design and runtime tokens

The reviewer should feel they are inspecting a preserved dossier, not conversing with an AI or reading a finance dashboard. Document evidence dominates; selection and four independent dimension cells are the visual signature. No marketing hero, decorative score or repeated ornamental cards in the review workspace. Root finance design files do not govern this client's future workflow.

Canonical token owner: `src/app/theme.css`. Keep this table and runtime values synchronized when changing the design; do not create a parallel theme in copied components.

| Token/role              | Baseline value                                                     |
| ----------------------- | ------------------------------------------------------------------ |
| Accent / primary action | `--accent: #103a4b`                                                |
| Primary text            | `--ink: #172d38`                                                   |
| Secondary text          | `--muted: #435e6b`                                                 |
| Reading surface         | `--surface: #ffffff`                                               |
| Dividers                | `--line: #c7d4db`                                                  |
| Error                   | `--danger: #9a2727` plus text                                      |
| Focus                   | `--focus: #126a9b`                                                 |
| Canvas                  | `#f4f7f9`                                                          |
| Typography              | Local system sans; local monospace for hashes/technical provenance |
| Scale                   | 16px body; 12px metadata; 20–38px headings in the foundation       |
| Shape / targets         | 6px controls/cells; minimum 44px foundation controls               |

Header/content/footer; bounded finding queue beside a dominant inspection area. Foundation stacks below 760px. A later brief/source split uses accessible resizable panels and preserves reading space rather than squeezing three unusable columns. Natural document scroll remains available; each bounded panel owns its scrolling. Reserve image geometry and error/loading footprints; no layout jumps or hidden scrollbars. Global standards-based scrollbar styling includes engine fallback and forced-colors behavior. Avoid decorative motion; respect reduced motion. Shared primitives own consistent labels, spacing, intent and feedback.

Reference repositories supply ideas, not authority or automatic adoption: OpenContracts for evidence workflows, Extend UI for source-linked inspection, tablecn/data-table-filters for data navigation, and Mozilla's own API/examples for PDF transforms. Verify repository, license, branch, source paths and commit before use. `sec-insights` is archived; old AllenAI/Extend file paths in prior proposals are not executable instructions. Prefer a reviewed small permissive component over maintaining unnecessary custom infrastructure; never import a whole product backend or incompatible workflow.

## 12. Verification, CI and commands

From repository root:

```bash
uv run --locked python -m scripts.generate_frontend_contract --check
uv run --locked pytest -q tests/test_frontend_contract.py
uv run --locked ruff check application/litigation/frontend_contract.py scripts/generate_frontend_contract.py tests/test_frontend_contract.py
uv run --locked mypy --explicit-package-bases application/litigation/frontend_contract.py scripts/generate_frontend_contract.py
```

From `frontend`:

```bash
npm ci
npm run contracts:check
npm run lint
npm test
npm run build
npx playwright install --with-deps chromium
npm run test:e2e
```

When deliberately changing contracts: run `uv run --locked python -m scripts.generate_frontend_contract` at root, then `npm run contracts:generate` here. Commit both generated outputs and changes to compatibility tests. CI must reject drift, unknown states and architecture sabotage. Review network/storage shortcuts and security-sensitive changes; static checks alone are insufficient.

The frontend workflow tests the built static application under production CSP. Keep synthetic transport fixtures explicit and isolated to tests; no in-product fake session/data fallback. Browser request assertions cover browser traffic only. Never use user documents or real credentials in public artifacts. Retain synthetic screenshots/traces for the configured limited duration, with access/retention reviewed for any future private evidence.

| Required evidence            | Negative/control cases                                                                                                |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Dependency boundaries        | shared→feature, feature→app, feature-internal imports, unapproved persistence/network shortcuts must fail             |
| Contract compatibility       | Actual backend fixtures, unknown states, duplicate IDs, malformed or oversized payloads, wrong matter/brief/snapshot  |
| Session lifecycle            | Signout/access denial, old token resolution, late response, cancellation, route switch and resource cleanup           |
| UI behavior                  | Empty/partial report, escaped hostile strings, bounded paging, labels, error focus, keyboard selection, narrow layout |
| Review/write path when built | Revocation, stale revision, audit rollback, duplicate/unknown outcome, reload and cold reopen                         |
| Viewer when built            | Section 7 hard-case matrix, annotated expected transforms and measured performance                                    |
| M4 when built                | Actual exported bytes reopened; hashes, corrected scope, source links, stale/foreign/revoked denial                   |

**Recorded foundation baseline:** code `d41ccca768d492f95917d170bc7639ab88d2c755` in [PR #162](https://github.com/haytamAroui/caseproof/pull/162): [frontend CI](https://github.com/haytamAroui/caseproof/actions/runs/41294319977) passed 15 unit/architecture tests, two Python projection tests and five Chromium browser tests; [kernel/integration CI](https://github.com/haytamAroui/caseproof/actions/runs/41294319980) passed 1,902 Python tests with four live gates intentionally skipped. All 16 automatic runs passed. This is dated foundation evidence, not a substitute for checks on later commits. No manual screen-reader, real signed React-browser, viewer or full M3/M4 acceptance follows from it.

### Local operation and host integration

Use Node 24 and the locked dependency tree. From `frontend`, run `npm ci` then `npm run dev`. The development URL is `http://127.0.0.1:5173/workspace/`; Vite binds loopback and proxies `/v2` to `http://127.0.0.1:8000`. The existing backend must be started through its authorized injected development composition. Do not expose its fixture/admin interfaces. This foundation does not start the backend or create users/matters automatically.

The current credential-source shape is the existing host bridge:

```ts
interface SessionHost {
  getBearer(): Promise<string>;
  clear?(): void;
}
// Current composition reads window.caseproofSession from a trusted host.
// It is not accepted from a document, URL, localStorage or model output.
```

Clicking Connect session only attaches that credential source; the API still decides every permission. Without a configured host, the client displays an actionable unavailable state, not a sample login or fake dossier. Actual host/authentication-provider installation is F1. Developers MUST NOT paste tokens into committed code, product inputs, URLs or logs.

An existing report can be opened at `/workspace/matters/:caseId/briefs/:briefId?snapshot=:snapshotHash`; the exact frozen snapshot must already exist and be authorized. `finding` and bounded `page` navigation are optional URL state. The foundation form takes these opaque report identifiers only; manual IDs are a foundation limitation, not the eventual intake experience.

For an authorized build inspection, run `npm run build` then `npm run preview -- --port 4173`; open `http://127.0.0.1:4173/workspace/`. Preview enforces its configured response headers but is not a production hosting approval. A real deployment serves `dist` at `/workspace/`, gives that route an SPA fallback, keeps `/v2` on the existing API without an SPA fallback, and independently verifies headers, session routing, asset egress, revocation and rollback. No frontend environment variable may contain a service key or backend secret.

## 13. Build sequence and exit gates

| Slice                      | Deliverable                                                                                                      | Exit evidence                                                                                                 | Current state                                     |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| F0 Foundation              | Structured client, generated projection, transport/session lifecycle, shared primitives, read-only frozen report | Architecture negatives; contract checks; unit/build/browser/axe; clear scope and rollback                     | Implemented in PR #162, not merged at this record |
| F1 Signed host integration | Reviewed authentication/session adapter and authorized matter/report navigation                                  | Genuine signed browser grant/foreign/revoked/expiry tests; no token persistence                               | OPEN                                              |
| F2 Viewer decision         | Same-fixture server-image/PDF.js comparison through the evidence port                                            | Section 7 matrix and accepted engine/asset/security record                                                    | OPEN                                              |
| F3 Intake                  | User-created matter, full DOCX/inventory/text-PDF/scan upload, confirm and recovery                              | Browser journey without manually seeded identifiers; fresh original hash readback; interrupted/denied cleanup | OPEN                                              |
| F4 Review workspace        | Source/brief navigation, page-space display, uncertainty/coverage, human rationale and durable receipt           | Genuine browser review, stale/revoked/unknown-outcome/restart tests; accessibility and language checks        | OPEN                                              |
| F5 Correction/recheck      | Supported redline preview, new draft activation and canonical recheck                                            | Original unchanged; stale/competing/retry rejection; actual new draft/report reopened                         | OPEN                                              |
| F6 M4 delivery             | Scoped report and supported corrected/annotated DOCX; actual source navigation                                   | Download/reopen/link/hash/permission tests on actual bytes; limitations disclosed                             | OPEN                                              |

Do not block the evidence spike on a complete shell, or replace working backend services to suit a UI library. Practitioner interviews and representative review proceed independently of this engineering sequence. No practitioner findings are fabricated by tests.

M3/M4 are accepted only through their roadmap/acceptance contracts and named owners. Independent M0 gold, representative M2 accuracy, deployment/retention/security/professional-secrecy gates remain separately open. A foundation PR merge does not close them.

## 14. Delivery and rollback rules

Every frontend PR states: concrete user outcome, changed paths/contracts, tested commit, exact cloud results/artifacts, security/permission impact, untested claims, open gates and next bounded slice. Do not present a draft or mocked interaction as deployed behavior. Do not merge or deploy autonomously without user authorization and applicable review controls.

The foundation is unmounted. Rollback removes/disables its static build/workflow without changing backend storage or existing clients. Later production mounting needs an explicit route/proxy/header/session plan and rollback test. Retire a temporary client only after equivalent real-client workflows pass; do not keep it as a second authoritative verification engine.

## 15. Primary references

- [CaseProof frontend ADR](../docs/adr/0026-frontend-foundation.md), [canonical report contract](../docs/adr/0022-verification-contract-report.md), [deployment evidence](../docs/security/DEPLOYMENT_EVIDENCE_RUNBOOK.md).
- [React application setup and tradeoffs](https://react.dev/learn/build-a-react-app-from-scratch), [Vite backend integration](https://vite.dev/guide/backend-integration), [React Router modes](https://reactrouter.com/start/modes), [TanStack Query](https://tanstack.com/query/latest/docs/framework/react/overview).
- [PDF.js API](https://mozilla.github.io/pdf.js/api/draft/module-pdfjsLib.html), [Mozilla PDF.js security advisories](https://github.com/mozilla/pdf.js/security/advisories).
- [docx-preview limitations and break behavior](https://github.com/VolodymyrBaydalka/docxjs/blob/master/README.md).
- [CSP reference](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy), [frame-ancestors header limitation](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/frame-ancestors).
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/).
- [OVB/OBFG AI guidance](https://www.ordevanvlaamsebalies.be/nl/kennisbank/digitalisering/richtlijnen-voor-advocaten-rond-gebruik-van-artificiele-intelligentie): relevant safeguards, not certification of this product.
