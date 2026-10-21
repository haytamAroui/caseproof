# ExceptionDesk — Evidence-backed financial exception resolution

**Status:** initial runnable Python domain slice; not production-ready. Existing GitHub repository remains `caseproof` until a separately approved rename.

ExceptionDesk is one Belgian-first B2B finance operations product with two connected workflows:
1. **Finance (first):** supplier invoice versus purchase order discrepancies, reviewer resolution and evidence-backed records.
2. **Disputes (later):** CaseProof factual chronology and professional dispute dossiers, reusing the same evidence references.

The reusable **evidence kernel** owns provenance, source verification, immutable claims and review records. Finance owns amounts, matching, VAT treatment, tolerances and financial findings. Disputes owns chronology and dossier policy. A source quote is **not** proof of real-world truth.

## First runnable slice
Requires Python 3.11+. No database, cloud account, LLM or customer data is required for the deterministic first tests.

```sh
python -m unittest discover -s tests -v
```

See [the architecture](docs/architecture/EXCEPTIONDESK_HEXAGONAL.md), [execution roadmap](docs/ROADMAP.md), and [first task](docs/tasks/EXD-001.md). This is an **initial finance reconciliation kernel**, not an upload-to-PDF MVP.

## Directory ownership
- `packages/evidence_kernel/`: source/evidence primitives and ports; no finance or dispute imports.
- `domains/finance/`: money and invoice-to-PO reconciliation.
- `domains/disputes/`: reserved for the later CaseProof workflow.
- `apps/api/`, `apps/web/`: planned FastAPI and Next.js adapters; not yet implemented.
- `tests/`: executable contract and domain tests.

AZComply remains an independent product and database. Only port domain-neutral algorithms after review and regression tests. No automatic collection, legal filing or unsupported compliance claim.
