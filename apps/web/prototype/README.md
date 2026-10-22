# MVP-01A — Synthetic invoice/PO candidate workbench

This is **not** a customer-facing feature and does not accept customer data.

## Try the working vertical slice

From the repository root:

```sh
uv run --locked pytest -q tests/test_synthetic_finance.py
uv run --locked python -m scripts.demo_synthetic_finance > synthetic_packet.json
```

Open `apps/web/prototype/finance-review.html` in a browser and choose the generated
`synthetic_packet.json`. The HTML app does not send requests or save reviewer notes.

## Contract and scope

- Input: fixed, synthetic UBL 2.1-shaped Invoice and Order XML fixtures under
  `tests/fixtures/finance/` with declared net `LineExtensionAmount`, source
  currency and invoice OrderReference. **This is not an XSD-complete UBL/Peppol
  validator**, line-item parser, VAT calculator, PDF/OCR intake or protected upload.
- Parsing: bounded bytes/nodes, no DTD/entities, strict document kind, one amount,
  matching line amount currency, no missing-to-zero and exact `Decimal`.
- Candidate: compare only like-for-like net amounts and only when the invoice
  references the supplied PO and currency matches. Missing PO or conflicting
  reference/currency produces an **unresolved** packet with no invented delta.
- Provenance: a raw source SHA-256 and versioned *parser-derived JSON representation*
  SHA-256 + typed `StructuredField` locator. These are **draft references**;
  neither SHA authenticates the source or resolves a verified evidence anchor.
  Original XML text highlighting and production Evidence Vault verification are
  explicitly not implemented.
- Human: local-only prototype notes and labels. No real login, role, approval,
  upload, persisted coverage, revision head, audit event, immutable decision or
  approved report. The JSON packet is a **draft export design**, not a resolution.
- Safety: only synthetic fixture bytes are read by the CLI; the browser reads a
  local JSON file and renders plain text with `textContent`. No external
  network calls or plugins. Never put confidential invoices into this demo.

## Next increment

Add line-item matching (quantity, unit price, VAT basis, freight and amendments)
under explicit versioned finance policies and golden tests. Then connect reviewed
Auth, private source bytes, durable evidence provenance and human decision API
as separate audited engineering steps. Do not turn this demo into public /v2
routes or treat parser output as verified evidence.
