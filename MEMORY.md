# CaseProof — durable project handoff

**Navigation, not authority.** Verify `main` and GitHub CI before relying on this summary. Source of truth: `CONSTITUTION.md`, code/tests, approved ADRs, then `docs/STATUS.md`.

- **Product:** ExceptionDesk, Belgian B2B invoice-versus-PO exceptions first. CaseProof dispute dossiers second. Independent from AZComply. **Frozen architecture target:** [ADR 0011](docs/adr/0011-architecture-freeze-and-first-finance-slice.md): hexagonal modular monolith, no DomainPack or universal EvidenceState now, exact v2 locator and permission vocabulary, one canonical source lifecycle.
- **Latest verified baseline (2026-10-22):** `main` `66db73667cc4932995e0376d7f1b7c9279c70041`, through PR #35; recheck after this handoff PR. CI on baseline green.
- **Implemented:** Stage 1 in-memory kernel, finance amount comparator, seven-table development tenant SQL, Auth verifier, synthetic RLS, internal audit/idempotency, disposable evidence metadata graph and Vault ledger. See [status matrix](docs/STATUS.md) for exact evidence and limitations.
- **Not yet implemented:** live signed Auth→DB role, complete durable graph, private object Storage, real human review approvals, durable workers, customer-facing invoice/PO intake/UI/export.
- **Security blocker:** issue [#5](https://github.com/haytamAroui/caseproof/issues/5). Positive CI and forbidden-import negative control are proven; owner-controlled merge protection is unverified. Do not equate green tests with a protected branch.
- **Next bounded work:** owner verifies protection [#5](https://github.com/haytamAroui/caseproof/issues/5), then genuine Auth tenant DB runtime [#37](https://github.com/haytamAroui/caseproof/issues/37), private Vault [#38](https://github.com/haytamAroui/caseproof/issues/38), durable evidence/authorized reviews [#39](https://github.com/haytamAroui/caseproof/issues/39) and the first complete finance journey [#40](https://github.com/haytamAroui/caseproof/issues/40).
- **Historical PR cleanup (2026-10-22):** #2 old memory, #7 superseded Stage 1 docs and #4 deliberate forbidden import are **closed unmerged**. #4 test run is preserved as negative-control evidence. [PR #36](https://github.com/haytamAroui/caseproof/pull/36) proposes this handoff/status reconciliation and is not merged as of this snapshot.
- **Never:** commit tokens, real customer documents, signed URLs, private user IDs or misleading approval claims to memory.

For code changes, preserve repo constitution/standards and record exact feature branch, CI link, review findings, rejected attacks and remaining release gates. This index does not add a mandatory global JSONL/change-log gate.
