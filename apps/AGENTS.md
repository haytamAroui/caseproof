# Application adapter guardrails
Applies to future `apps/**` and app entrypoints.

- API and web are delivery adapters, not business-rule authorities. Do not duplicate finance or evidence validation in controllers as the only enforcement.
- All reads, writes, jobs, exports and signed URLs require server-derived tenant and actor authorization. Never trust client tenant IDs or role claims.
- Never show an unverified extraction as confirmed truth; always expose provenance, review state, missing evidence and uncertainty.
- No silent success toast, fake persistence, optimistic approval without server confirmation, or swallowed error.
- Never log raw documents, full evidence quotes, secrets or personal identifiers in telemetry.
- No new production routes, payment actions, external notifications or destructive migrations without explicit approval.
