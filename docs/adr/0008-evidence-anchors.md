# ADR 0008 — Typed evidence anchors and independent verification
Status: Proposed — human review required
Date: 2026-10-21

## Decision
An immutable source version is identified by tenant-scoped document ID, version ID, content digest, and a recorded representation/derivation identity. A typed evidence anchor locates evidence within that exact version. Supported kinds initially include text span, PDF page/region, structured field and spreadsheet cell/range; audio/time and image/region are extensible future kinds. Stable anchor IDs must be deterministic within a version, with explicit coordinate systems and parser/OCR provenance. Display strings such as "page 4 paragraph 2" are not authoritative locators.

A candidate finding may exist without verified evidence but must remain ungrounded and unpromotable. A promoted evidence-backed finding must have resolvable anchor references. Separate checks:
1. integrity of source version;
2. citation resolution to the claimed location;
3. fidelity of quoted/extracted content to that location;
4. semantic relationship: SUPPORTS, CONTRADICTS, QUALIFIES, INCONCLUSIVE, NOT_ASSESSED;
5. sufficiency against the investigation's stated requirements.

A successful quote match never implies support, authenticity, or truth. OCR uncertainty is explicit; no automatic VERIFIED status on fuzzy matches. Confidence scores are optional model metadata, not proof. Preserve existing v1 contracts; any breaking API shape requires versioned v2 draft and migration review.

## Boundaries
Pure Python domain types and ports in evidence_kernel; Pydantic only at transport/adapters. Sector rules remain outside the kernel. Tenant and authorization context comes from trusted application boundaries.

## Required tests
Wrong document version; correct quote at wrong page; fabricated locator; duplicate passage; OCR mismatch; quoted passage contradicts finding; multi-source conflicting evidence; unsupported candidate blocked; cross-tenant references denied.
