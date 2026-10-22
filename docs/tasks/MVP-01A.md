# MVP-01A — Synthetic finance discrepancy candidate and local reviewer workbench

**Status:** Draft PR #42. No customer release or production approval.

## Purpose and architecture scope

Demonstrate one bounded, reproducible synthetic UBL Invoice/Order comparison in
ExceptionDesk without modifying the CaseProof Evidence Kernel or deploying an
invoice-approval service. `apps/api/synthetic_finance.py` is a parser/serializing
application adapter. Domain-level match eligibility is in
`domains/finance/candidate_policy.py`; immutable source locator contracts are
reused from `packages/evidence_kernel`.

## Acceptance

- Real-format **synthetic** UBL 2.1-shaped Invoice and Order fixtures; no actual
  customer data, full XSD/Peppol validation or general-purpose XML ingestion.
- Strict UTF-8 input, bounded sizes/nodes, DTD/entities refused, scalar fields
  cannot contain nested markup, single declared net total and explicit currency.
- Exact, nonnegative, finite `Decimal` with explicit 18 integral/6 fractional
  digit bounds; both invoice and PO match eligibility are domain-owned and
  independent of ambient Decimal precision and exponent/trap settings.
- Same PO identity and currency required for comparison; blank/missing/mismatched
  references and unsupported precision become unresolved, never false matches.
- Versioned hashes for original bytes and a parser-derived structured
  representation, with **UNVERIFIED** typed evidence locator and explicit
  investigation gaps. The parser output is not an EvidenceAnchor fidelity proof.
- Reviewer UI loads only local JSON, rejects non-demo and approval-like statuses,
  displays sources and gaps, and permits local draft notes without a backend,
  audit event, customer upload, permission elevation or approval.
- Golden positive/negative, ambiguous and malformed fixtures; architecture
  boundary, whole repository pytest, Ruff, strict mypy, and affected disposable
  PostgreSQL regression suites pass in cloud CI.

## Test and demonstration

```sh
uv run --locked pytest -q tests/test_synthetic_finance.py tests/test_finance_candidate_policy.py
uv run --locked python -m scripts.demo_synthetic_finance > synthetic_packet.json
```

Open `apps/web/prototype/finance-review.html` locally and select the generated
`synthetic_packet.json`. No requests are sent and draft notes are not persisted.

## Deliberate non-goals

No tenant-authenticated upload, certified Peppol validation, per-line VAT or
quantity matching, account ledger, confirmed business decision, supplier
communication, durable audit, privacy guarantee for customer data, ERP write
back, external payment, or approval export. `/v2` routes remain disabled.
This demonstration is not a substitute for S2-004/007/008/009 security gates.

## Follow-on acceptance gate

After independent code review, owner-confirmed branch protection, successful
exact-head CI and explicit human merge approval, implement the next bounded
finance slice only as justified by the chosen market hypothesis.
