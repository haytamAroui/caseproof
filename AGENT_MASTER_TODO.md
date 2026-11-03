# CaseProof — Agent Master TODO

**Date:** 2026-11-03  
**Status:** Execution tracker; unchecked items are not claims of missing implementation.  
**Authority:** CONSTITUTION.md and security ADRs > backend contracts and ROADMAP > frontend/BLUEPRINT.md for UI architecture > workflow v3.1 for stage acceptance. Resolve conflicts explicitly; do not silently rewrite sources.

## Agent execution protocol
1. Before editing, inspect current main, open PRs, docs/STATUS.md, frontend/BLUEPRINT.md, workflow v3.1, and relevant ADRs. Record exact SHA and links.
2. For every item classify VERIFIED COMPLETE / PARTIAL / MISSING / BLOCKED, with code paths, tests and evidence. Do not infer completion from a PR title or green CI.
3. Implement bounded vertical slices using existing FastAPI + React/Vite architecture; preserve Pydantic → JSON Schema → generated TS + AJV contracts.
4. One coherent PR per slice; include backend, frontend, migrations, tests, documentation, rollback, and contract drift checks where applicable. Avoid speculative rewrites.
5. Require tenant isolation, signed-user authorization, revocation, stale-write handling, deterministic replay, restart/cold reopen and actual bytes where relevant.
6. Run targeted tests, applicable CI and genuine signed-browser acceptance. Record run URLs, final SHA, failures, skips, independent approvals and residual risks.
7. Never mark a task complete without direct evidence. Never merge on CI green alone if required independent legal/security/privacy review or live gates remain open.

## P0 — Reconcile baseline and unblock safe work
- [ ] P0.1 Audit current main and open PRs; record F1–F6 status, final SHAs, CI run links and remaining gates in docs/STATUS.md.
- [ ] P0.2 Compare blueprint and workflow v3.1 against code and tests; create a traceability matrix with acceptance IDs, implementation locations and evidence.
- [ ] P0.3 Review any pending F5/F6 blockers, including permission-scoped recovery, bounded DOCX previews, saved human review before commit, superseded recheck, and changed-intake inventory rendering. Verify before changing.
- [ ] P0.4 Confirm dependency versions, licensing and zero-egress policy; do not add AGPL dependencies.

## P1 — Security, intake and deterministic evidence
- [ ] P1.1 Harden XML discovery using defusedxml; prohibit DTD, entities and external references; test malicious DOCX/XML and safe fixtures.
- [ ] P1.2 Audit file intake, SHA-256 and size checks, org isolation, corruption rejection, retries and authorized readback.
- [ ] P1.3 Audit inventory preservation, changed-intake confirmation, identity mapping and cross-source coverage with real backend + browser.
- [ ] P1.4 Verify page-space transforms and raster overlay alignment on scanned/rotated/cropped PDFs; never treat OCR crops as proven location.
- [ ] P1.5 Confirm uncertainty states, unsupported-language handling, deterministic findings and no false NOT_IN_INVENTORY before confirmation.

## P2 — Reviewer workspace (F4)
- [ ] P2.1 Audit findings table, filters, keyboard actions, accessibility, locale NL/FR/EN and honest status semantics.
- [ ] P2.2 Verify split DOCX/PDF viewer, source pixels, selectable crops, OCR X-ray and legal redline with precise provenance.
- [ ] P2.3 Verify independent human decisions, durable receipts, lost-ack reconciliation, permission/revocation and cold reopening.
- [ ] P2.4 Run genuine signed-browser acceptance and record exact evidence.

## P3 — Correction and recheck (F5)
- [ ] P3.1 Exact DOCX anchors and bounded before/after previews; fail closed on unsupported or ambiguous edits.
- [ ] P3.2 Require saved human review before commit; permission-scoped recovery; suppress recheck for superseded drafts.
- [ ] P3.3 Durable commit, activation, recheck bound to activated version and old/new report comparison.
- [ ] P3.4 Test interrupted commits, unknown outcomes, derivative cleanup, concurrent writes, stale versions, restart and revocation.
- [ ] P3.5 Genuine signed-browser preview → review → commit → activate → recheck → compare → cold reopen.

## P4 — Export and historical reopening (F6)
- [ ] P4.1 Backend reviewed export: authorization, manifest, hashes, signatures and deterministic artifact integrity.
- [ ] P4.2 Frontend export workspace: explicit provenance, limitations, review state and download authorization.
- [ ] P4.3 Historical snapshots and originals: SQL authorization, signed access, revocation and cold reopening of exact bytes.
- [ ] P4.4 Full signed-browser export/reopen acceptance, including changed intake and failure cases.

## P5 — Selective SetDoc / Vaquill-inspired usability (not feature parity)
- [ ] P5.1 Research exact features and licenses against primary sources before adopting; document suitability and security boundaries.
- [ ] P5.2 Improve document navigation: synchronized outline, page jumps, citation-to-evidence focus and stable deep links.
- [ ] P5.3 Add safe reviewer ergonomics: side-by-side comparison, annotation affordances and structured evidence notes, with human-owned decisions.
- [ ] P5.4 Assess optional document assembly/templates only where they support bounded CaseProof corrections; exclude general-purpose editing and unverified AI claims.
- [ ] P5.5 Accessibility, performance and large-document resilience acceptance for every adopted feature.

## P6 — Pilot and release gates
- [ ] P6.1 Execute 3–5 authorized synthetic or consented NL/FR dossiers with seeded errors and two independent reviewers.
- [ ] P6.2 Record false positives, missed findings, time-to-review, uncertainty, usability and failure recovery.
- [ ] P6.3 Complete legal, security, privacy and retention reviews; validate no mandatory model and no unauthorized egress.
- [ ] P6.4 Publish deployment/rollback/runbook and signed evidence index; obtain required independent approvals.
- [ ] P6.5 Only then decide pilot release; no automatic production authorization from a merged PR.

## Required task record
For each task: **ID | owner (if assigned) | baseline SHA | state | scope | affected contracts | backend/frontend paths | tests | CI URL | browser evidence | risk | rollback | reviewer decision**.

## Definition of done
Code merged into intended branch; generated contracts consistent; applicable tests and CI green with skips explained; negative authorization and lifecycle tests passing; real signed-browser journey where required; exact final SHA and evidence links recorded; independent gates explicitly approved. Otherwise remain OPEN or BLOCKED.

## PR batching and CI efficiency policy
- Prefer **large, cohesive milestone PRs** over small PRs: batch P0+P1, P2+P3, P4+P5, and P6 where dependencies and current repository state permit. Do not reopen already accepted functionality merely to fit a batch.
- Complete related backend, frontend, generated contracts, tests, documentation and rollback notes together before pushing. Use local targeted checks first; consolidate fixes into a small number of commits and pushes.
- Run expensive full CI after the coherent change set is ready; avoid repeated pushes solely to trigger CI. Never suppress mandatory branch protection, security, contract, or signed-browser acceptance checks to save time.
- Keep each PR independently reviewable, revertible and bounded by one milestone outcome. Split only when security risk, dependency order or reviewability requires it.
- Merge only after final-head CI and applicable independent acceptance gates; update docs/STATUS.md with the final SHA and run links.
