# Finance domain guardrails
Applies to `domains/finance/**`. Follow root constitution.

- Finance owns invoice/PO/delivery/payment schemas, VAT basis, currencies, rounding, matching and exception policy. Do not insert these into the kernel.
- Compare only like-for-like monetary bases; unknown VAT basis, currency conversion, credit notes, partial delivery, amendments and fees require an explicit unresolved finding, never an assumed equality or fraud label.
- Use finite `Decimal` amounts, explicit currency and documented rounding. Do not use float or invented conversion rates.
- A mismatch creates a finding, not an altered source claim, debt balance, liability or legal conclusion.
- Source references must resolve to verified, tenant-authorized document versions before an authoritative output.
- Every rule requires versioned positive, negative, edge and ambiguous fixtures. Do not silently default missing fields to zero.
- Never import `domains.disputes` or provider SDKs. Do not perform external financial actions.
