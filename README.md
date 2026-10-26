# CaseProof — Belgian litigation writing and evidence review

**Product workflow:** [Complete lawyer journey](docs/PRODUCT_WORKFLOW.md). **Principal roadmap:** [Belgian litigation workflow and build plan](docs/ROADMAP.md). It supersedes the finance-first product order in older README/roadmap material; historical ADRs remain architecture records. The repository code has not yet completed this pivot and the litigation product is not production-ready. See [verified implementation status and release blockers](docs/STATUS.md).

## Product

CaseProof's target product is a Belgian evidence-linked workspace for lawyers to write with evidence, check their own or an opponent's brief against the exhibit bundle, review and correct findings, and deliver source-linked work. The initial factual-evidence workflow does not claim automatic legal-authority verification. The existing sector-neutral Evidence Kernel remains the foundation; the implementation plan uses `domains/disputes/`. AZComply is independent.

The product's desired outcome is a reviewed, source-linked legal work product, not generic legal AI chat. A correct quotation from a document is **not** proof of document authenticity or factual truth.

## Existing implementation (finance/reference workflow)

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

The planned first complete litigation outcome is a lawyer importing evidence, mapping exhibits, finding and inserting source support, checking/correcting a brief, reviewing changes and delivering correctly linked work. **That workflow is not built yet.**

### Evidence Intelligence (candidate runtime)

Run the **offline synthetic** finance/construction demonstration (no API key or network):

```bash
uv run --locked python -m scripts.demo_evidence_intelligence
```

The shared runtime discovers proposed entities/relationships, extracts quote-anchored candidates, checks independent entity boundaries, applies versioned observation validators and projects existing Kernel findings/coverage. Every result remains unapproved. Three bounded strategies: `global_first` (default), `segmented`, experimental `four_pass`; bounded repair, no silent fallback. Scripted demo responses are not live model evaluation.

For server-side Requesty composition use `RequestyProvider.from_environment()` and `EvidenceIntelligence(provider, journal, policy)`. Set `CASEPROOF_REQUESTY_API_KEY` (or existing `REQUESTY_API_KEY`) and `CASEPROOF_EXTRACTION_MODEL` (or existing `REQUESTY_MODEL_PAID`) to an explicitly reviewed concrete Requesty model. No implicit model, direct alternate provider or SDK integration. Review [Requesty routing](https://www.requesty.ai/product/routing) before sending documents; an EU gateway alone does not guarantee inference residency. Never put keys in browser code or source control. No live-call CLI or public route is enabled here.

`MemoryJournal` is test-only. `DisposablePostgresJournal` exercises real checkpoint/CAS/restart behavior only against disposable CI; it accepts a synthetic actor and is **not production authentication**. Source intake must supply trusted immutable representations, case scope, confirmed entity boundaries and required slots. See [ADR 0012](docs/adr/0012-evidence-intelligence-candidate-runtime.md) for remaining parsing/reviewer/export gates.

### Document intake and extraction evaluation

The internal document-to-extraction slice accepts preserved UTF-8 text, text-bearing PDF, XML/UBL and RFC5322/MIME email. It checkpoints normalized representations and maps exact text spans to PDF pages, XML paths and MIME parts. Required scans, HTML/attachments, malformed or unsupported sources block extraction; no OCR, invented bounding boxes, live mailbox or customer HTTP upload is enabled.

```bash
# Offline, repository-owned synthetic corpus; no provider call or key required
uv run --locked python -m scripts.run_document_evaluation
```

The report labels this `scripted_safety_only`; its scores are integration checks, not live extraction quality. Native XML scalar citations also feed the existing Decimal invoice/PO candidate comparison. All outputs require review.

A live Requesty evaluation is opt-in and accepts **only these synthetic files**. First provision the existing disposable PostgreSQL fixture/checkpoint schema (CI integration sequence), select a synthetic case/actor with required permissions and set `CASEPROOF_EVAL_ORG`, `CASEPROOF_EVAL_CASE`, `CASEPROOF_EVAL_ACTOR`, plus the guarded disposable `PG*`/`CASEPROOF_DISPOSABLE_DB` environment and Requesty key/model described above. Keep the same `--run-id` to resume; changing it intentionally permits a fresh paid evaluation.

```bash
uv run --locked python -m scripts.run_document_evaluation --live-requesty --run-id evaluation-001
```

Maximum 8 calls × 512 output tokens, no automatic retry/repair/fallback. Saved raw responses and parser artifacts replay from PostgreSQL; unknown dispatch requires reconciliation. Provider-reported cost remains null if missing. No Requesty key/model was configured during implementation, so live quality/cost are not measured. See [ADR 0013](docs/adr/0013-document-normalization-and-evaluation.md) for parser/security limits and remaining production gates.

### Synthetic reviewer workbench and draft pack

```bash
uv run --locked python -m scripts.run_review_workbench
# Open http://127.0.0.1:8765/demo
```

This separate loopback app loads only repository-owned synthetic sources and makes no LLM calls or uploads. Inspect exact parsed source text and competing amounts, record retain/reject/correct/qualify/request-evidence **recommendations**, and download a draft pack. The default server honestly uses session memory; restarting it clears its demo notes. Durable event/head/receipt behavior is covered with the injected disposable PostgreSQL adapter in CI. No approval, promotion or supplier message is enabled.

Keep the displayed manifest hash separately from the downloaded ZIP. Verify it offline with trusted repository code:

```bash
uv run --locked python -m scripts.verify_resolution_pack draft-evidence-review.zip --expected-manifest YOUR_RETAINED_SHA256
```

The verifier reads bounded ZIP entries without extracting or running them. It checks originals, normalized representations, exact citations and audit-chain consistency. Hash verification is not source authenticity, human identity, legal validity or approval. The readable report retains conflicts, missing evidence and unreviewed sufficiency. See [ADR 0014](docs/adr/0014-review-recommendations-and-draft-pack.md) for security, persistence and remaining production gates.

## Internal extraction worker reference

`application/runtime` and `infrastructure/execution` add an internal, case-scoped job queue with database-time leases, heartbeats, immutable inputs, attempt budgets and atomic execution events. `apps/worker` fences the existing extraction journal inside its transaction; source parsing and provider calls happen outside database transactions. Expired dispatched/unknown calls never auto-retry. A successful job stores a **review proposal**, never an approved decision.

The adapter is disposable and production-disabled. It has no mounted endpoint, live service role, deployed supervisor or provider credentials. Run its real PostgreSQL acceptance suite only in the existing disposable CI setup: `uv run --locked python -m scripts.verify_worker_integration` after the earlier database integrations. See [ADR 0015](docs/adr/0015-leased-document-jobs.md) and [EI-004](docs/tasks/EI-004.md) for setup, exact boundaries and recovery behavior. Requesty remains the configured provider port; this change makes no live LLM request.
