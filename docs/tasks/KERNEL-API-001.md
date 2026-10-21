# KERNEL-API-001 — FastAPI development adapter

Scope: expose existing immutable evidence claims via a thin FastAPI HTTP adapter. The evidence kernel itself must not import FastAPI or domain-specific modules.

Endpoints: GET /health; POST /v1/claims; GET /v1/claims/{claim_id}. OpenAPI docs at /docs.

Run: `uv run pytest -q`; `uv run python scripts/check_architecture.py`; `uv run uvicorn apps.api.main:app --reload`.

**NOT production-ready**: in-memory storage is lost on restart, supplied document hashes and quotations are not verified against uploaded bytes, and `X-Tenant-Id` is an untrusted caller-controlled development header, NOT authentication or authorization. Never expose to untrusted networks or real customer data. Next steps require authenticated tenant context, durable repository adapter, immutable source ingestion, and auditable events.
