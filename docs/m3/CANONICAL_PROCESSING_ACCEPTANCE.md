# Canonical report and processing acceptance — PR #150

Candidate dated 31 October 2026. CI is authoritative for its exact commit.

| Requirement | Implemented evidence | Remaining acceptance |
|---|---|---|
| Canonical REST/MCP | Shared `read_dossier_report` and application serializer; MCP requires frozen hash | Protected signed live workflow on current head |
| JSON/Markdown byte parity | Actual HTTP tests, DOCX parsing, disk reopen, language context and incomplete inventory; exact export digests | Current-head live result |
| Content release | Caller, case, brief, snapshot, destination, expiry; pre/post-read checks; model arguments closed | Real host consent resolver and approved destination |
| Matter authorization | Existing current-grant/RLS and signed original guards retained; protected owner/foreign/ungranted/revoked acceptance | External pilot security approval |
| File boundaries | DOCX bomb/traversal/duplicate/malformed archive denied before signed upload storage; parser/pack and size tests | Malware policy, quotas and independent ASVS audit |
| Provenance | Frozen report hash/HMAC, source-byte verification, no read-time reassessment, exact exported-byte digest | Production key custody/rotation |
| Large bundles | 200-page local text parser/coordinator benchmark, finite concurrency/retry, per-page checkpoints and persisted deadline | Live fenced litigation page-worker composition; realistic scan/OCR and end-to-end signed 200-page benchmark |
| PostgreSQL durability | Existing journal; CI script checks 200 pages and separate-process replay, foreign/revoked denial | Least-privilege live worker binding |
| Observability | OTel 1.45.1 locked; spans/duration; closed attributes and no automatic exception recording; in-memory SDK privacy test | Approved collector, dossier/OCR operational dashboards and load acceptance |
| Hosted MCP/OAuth/Tasks | Architectural target remains MCP 2026-07-28 | Deferred optional channel; not a deployed server |
| Word | Same authoritative report contract required | Actual Word-host adapter/acceptance deferred |

## Measurement scope

`python -m scripts.benchmark_page_processing` generates four 50-page text PDFs
(200 physical pages), runs the isolated parser with concurrency two, persists
page artifacts and replays completed checkpoints without parsing. It reports
wall time and parent/child peak RSS. It uses no external provider and no OCR.
It measures neither detection precision/recall nor lawyer effort; those must not
be inferred from processing completion. `scripts.verify_page_checkpoints` uses
real disposable PostgreSQL, synthetic actors and a separate replay process.
Neither is live signed-user or production evidence.

## Reproduction

- `uv run --locked pytest -q`
- `uv run --locked ruff check .`
- `uv run --locked python -m scripts.check_architecture`
- `uv run --locked python -m scripts.benchmark_page_processing`
- Cloud kernel-boundary workflow installs the disposable schema and invokes
  `scripts.verify_page_checkpoints`; dossier-live executes protected signed
  MCP discovery/export and access-denial tests with guaranteed fixture cleanup.

## Sources

- [MCP 2026-07-28 announcement](https://blog.modelcontextprotocol.io/posts/2026-07-28/)
- [OWASP ASVS 5.0 file handling](https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x14-V5-File-Handling.md)
- [Pinned MCP telemetry convention](https://github.com/open-telemetry/semantic-conventions/blob/v1.41.0/docs/gen-ai/mcp.md)

The matrix is intentionally explicit about engineering implementation versus
live/pilot acceptance. No claim of complete ASVS conformance or security approval.
