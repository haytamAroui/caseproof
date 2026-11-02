# ADR 0030 — F2 v3.1 inspection, page spaces and recovery

2 November 2026. Engineering implementation candidate; owner requested a single F2 retrofit PR under workflow v3.1. Existing ADR 0028, constitution, generated contracts and frontend blueprint remain authoritative. No new verification authority, engine, public enum, schema field, route, provider, database or permission.

## Confirmed gaps and decisions

- The viewer did not show canonical printed/bundle labels. Display the existing dossier finding's `page_spaces` extension emitted by `domains/disputes/dossier_verification.py`. This is presentation of server metadata, never client offset calculation. Consume bounded numeric-string labels only when the extension's physical PDF target agrees with the authorized ViewerContext. Missing/malformed/conflicting metadata remains explicit. Keep reference labels distinct from the physical page currently being explored.
- A `mapped` ViewerContext without a physical page previously fell back to page 1. Reject that inconsistency at the existing source route and client parser. The wire shape/version stays unchanged. Unmapped/conflicting sources retain an explicit page-1 exploration start. No mapping or verdict is calculated in React.
- A render deadline could close the engine while a late completion still updated text/result state. A shared bounded-operation fence rejects timeout or selection cancellation and consumes late completion without publishing it. Existing 15-second open/render limits and bounded worker destruction remain unchanged.
- Source reopening was not directly available after an error. An explicit reopen remounts private inspection state and freshly reads authorized context and digest-bound original bytes. No automatic retry, write, receipt or inspection attestation. Scope changes remount the same component, independent of caller key conventions.
- Show specific OCR-unreliable/representation-conflict explanations from canonical fidelity, plus version/reference/hash provenance. Preserved pixels and derived search boxes remain separate; no visual match or page visit changes findings/human decisions.

## Compatibility and retained boundaries

The ReportScreen render callback now carries the generated FindingView to composition; its only production consumer is App, which passes it to the evidence feature. Features do not import one another. FindingView's intentional extra-field compatibility remains unchanged; page_spaces is inspected defensively, not added as a speculative contract. Older reports without it remain inspectable with unavailable labels.

Legacy raster crop geometry is still unprojected. Full crop attestation/review writes, general DOCX preview, automatic page offsets and verdict computation remain outside F2. Existing source/crop APIs are retained. Renderer comparison budgets, hostile-file defenses, one-page rendering, original SHA/readback and session cleanup must continue to pass.

## Evidence and rollback

Unit tests cover late completion/cancellation/deadline cleanup and invalid/mismatched page-space data. Viewer API/client tests reject mapped-without-page. Production-build real-worker tests cover printed p.4 → PDF p.6 at 200%, reference return navigation, representation conflict, scan/no-text uncertainty, explicit reopen, delayed old-source bytes, denial and worker cleanup. Existing 200-page/geometry/hostile comparator remains required. The existing protected F2 workflow is explicitly enabled for this branch with unchanged environment and zero-residual teardown.

Cloud/signed results must be recorded in [F2 v3.1 audit](../m3/F2_V3_1_AUDIT.md) before readiness. Synthetic browser routes do not prove signed RLS. Independent privacy/security/manual screen-reader/representative-source and deployment acceptance remain separate. Rollback reverts this PR; no migration or stored-data repair.
