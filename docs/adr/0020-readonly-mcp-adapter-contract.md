# ADR 0020 — Read-only MCP adapter contract and local-engine path

Status: proposal for owner review; 31 October 2026. The owner asked for the MCP and
packaged-local-engine item identified in the competitor and market review.

## Context

[ROADMAP](../ROADMAP.md) makes an MCP adapter contract first-class but states that a
deployed MCP server is not a pilot prerequisite, and it describes firm-controlled or
offline deployment as a research option that is not built or approved. ADR 0018
requires an explicit owner decision and an ADR before scope grows. This ADR records
the smallest increment that respects those limits.

## Decision (this increment only)

1. `apps/api/mcp_adapter_contract.py` defines two **read-only** tools over the existing
   headless ports: discover the exhibit references of one brief, and export the current
   report with recorded human decisions. It starts no server, adds no dependency, mounts
   no route and changes no permission or migration.
2. **Identity never comes from the model.** The host supplies the signed user's bearer
   out of band. Tool arguments are a closed schema (`case_id`, `brief_id`, optional
   `format`); any other argument, including bearer, tenant or organization values, is
   rejected before data access. Authorization stays in `HeadlessMatterStore`.
3. **No write tools.** Recording `CONFIRMED_SUPPORTED`, `CONFIRMED_QUALIFIED` or
   `CONFIRMED_CONTRADICTED` is an authorized human act. A future write tool needs its own
   ADR, a host-side human confirmation design and acceptance tests.
4. `load_snapshot` and `export_report` are extracted from the HTTP router into module
   functions so both adapters produce the same snapshot hash and report. Router
   behaviour and responses are unchanged.
5. Access failures return an opaque `access_rejected` result; contract violations raise
   `McpContractError`.

## Not decided here

- MCP transport, SDK choice and hosting.
- What a model provider may see. Results contain reference literals, region names and
  OCR crop metadata. A firm's MCP host and model provider must satisfy professional
  secrecy and the pilot data security gate before any real matter is connected.
- The packaged local engine below.

## Local-engine path (design only; nothing is built)

Goal: let a firm run the engine inside its own perimeter. Candidate acceptance for a
later ADR and PR:

- Reproducible, signed releases and signed updates, with a documented licence model.
- A test that proves the engine makes no outbound network connection in local mode,
  extending the existing isolated-OCR network probe.
- The same API and MCP contract as the hosted engine.
- A one-page data-flow diagram per deployment mode.
- Key custody for the review ledger decided before any signing feature ships.

Open and unverified: whether the bars or insurers accept a local engine as a "closed
environment" under the 2025 OVB and Avocats.be guidelines, and whether small firms can
operate it without IT staff.

## Acceptance and limits for this increment

Unit tests use a fake matter store and cover the closed tool list, rejected identity and
write arguments, malformed identifiers, parity with the HTTP report, and opaque failure.
Not tested: a real MCP host or SDK, a live signed user, or the deployed API. CI results
belong to the pull request. No client-data, security or commercial claim follows.
