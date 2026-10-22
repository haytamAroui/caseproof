# ExceptionDesk — evidence-backed invoice/PO exception resolution

**Repository:** `caseproof`. **Status:** engineering reference and Stage 2 development infrastructure; **not yet a production-ready or end-to-end sellable application**. See [verified status and blockers](docs/STATUS.md) and [execution roadmap](docs/ROADMAP.md).

## Product

ExceptionDesk targets Belgian B2B finance operations, initially **supplier invoice versus purchase-order discrepancies**. A later CaseProof factual dispute-dossier workflow may reuse its sector-neutral Evidence Kernel after the finance use case is validated. AZComply is independent.

The product's desired outcome is a trusted, human-reviewed resolution package, not generic legal AI chat. A correct quotation from a document is **not** proof of document authenticity or factual truth.

## What runs today

- Pure Python `packages/evidence_kernel` reference contracts (KRN-101–109): immutable sources/representations, typed anchors, fidelity vs semantic support, coverage and gated findings.
- `domains/finance/reconciliation.py` compares **like-for-like totals** using `Decimal` and emits an unreviewed discrepancy; line items/VAT/fees are not yet implemented.
- Development-only FastAPI `apps/api/main.py` mounts `/health` and in-memory `/v1/claims`; `X-Tenant-Id` is **caller-controlled** and does not authenticate users. Do not expose this API as a real secure tenant service.
- Seven-table foundational SQL was installed in a dedicated development Supabase project. **Further evidence/Vault schemas under `db/proposals/` run only on disposable PostgreSQL 17.** They are not installed cloud migrations.
- Strictly scoped Auth, tenant RLS, atomic audit/idempotency, typed evidence reader, immutable Vault protocol and recovery have automated tests. Genuine signed-user→DB connectivity and real private object Storage are **not** integrated.

## Tests

Prerequisite: Python 3.11+ and the checked-in `uv.lock`.

```sh
uv sync --locked
uv run --locked pytest -q
uv run --locked python scripts/check_architecture.py
```

Cloud CI also tests disposable PostgreSQL 17 transaction and tenant-isolation invariants; review the actual [GitHub Actions results](https://github.com/haytamAroui/caseproof/actions) for the SHA being assessed.

The root `MEMORY.md` and `docs/STATUS.md` are handoff aids, not trust authorities. `CONSTITUTION.md` and owner-controlled release gates still apply. Real Auth, private Storage, a safe /v2 app and an invoice/PO reviewer journey are outstanding.

## Source layout

- `packages/evidence_kernel/` — sector-neutral pure domain semantics
- `domains/finance/` — initial reconciliation domain
- `apps/api/` — development FastAPI and unmounted Stage 2 ports
- `db/proposals/` — **disposable, not deployable** verification-only schema contracts
- `supabase/migrations/` — existing canonical baseline only
- `docs/tasks/` — staged engineering tasks and design proposals

For the first product milestone, a genuine user must be able to securely upload an invoice and PO, inspect source-backed discrepancies, make an authorized decision and export a reproducible package. **That workflow is not built yet.**
