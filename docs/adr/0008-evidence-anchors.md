# ADR 0008 — Versioned typed evidence anchors and finding semantics

Status: Proposed — human review required
Date: 2026-10-21

## Context
A document quote, a citation locator, a source's authenticity and a claim's evidentiary support are different properties. Existing exact-substring checks establish only text presence in a registered text snapshot.

## Decision
- An immutable document version has tenant scope, document ID, version ID and content digest. Parsed/OCR derivatives record their transformation provenance.
- An evidence anchor is a typed locator bound to that version: text offsets/passage ID, PDF page and region, structured field, spreadsheet cell/range, or extensible future type. Validate that the locator resolves to the specified version; page labels alone are not sufficient.
- A finding is initially a candidate. Candidates without anchors remain quarantined. A promoted evidence-grounded finding must reference one or more resolvable anchors and recorded support assessments.
- Store **citation resolution** (resolved/unresolved/stale/invalid), **content fidelity** (matched/mismatched/indeterminate), **semantic relation** (supports/contradicts/qualifies/inconclusive/not_assessed), and **sufficiency** (sufficient/insufficient/not_assessed) separately. No single VERIFIED flag or model confidence score can replace these checks.
- A quotation can match perfectly while contradicting the proposed finding. Authenticity and factual truth are not established by hashing or matching text.
- Preserve evidence and assessment history immutably. Sector-specific calculations and rules belong outside the kernel.
- Domain types are pure Python. Pydantic schemas belong at I/O boundaries.

## Consequences
Stage 1 defines and tests contracts using in-memory adapters; Stage 2 implements durable storage and authorization. Add negative tests for wrong offsets, page mismatch, stale versions, wrong tenant, false claims with true quotes, OCR ambiguity and contradictory passages.

## Compatibility
Do not silently change the existing v1 reference API. New breaking endpoints/schemas belong in a proposed v2 contract and need implementation-backed contract tests before adoption.
