# ADR 0019 — Reusable evidence engine, Belgian litigation first

**Decision date:** 30 October 2026. **Status:** ACCEPTED product-direction clarification at the owner's instruction. No new vertical, runtime architecture, pilot, production processing or release is authorized.

## Decision

**Vision:** CaseProof helps legal professionals check that important statements and references are traceable to the right source documents, inspect uncertainty and preserve accountable human review. It starts with pre-filing exhibit verification for Belgian litigation.

One reusable kernel, one focused product today, evidence-led expansion. Litigation is already a vertical. Kernel flexibility provides options; it is not evidence of demand or domain correctness in contracts, compliance or accounting.

| Layer | Responsibility | Boundary |
|---|---|---|
| Evidence kernel | Sector-neutral source/representation identity, anchors, provenance, versions and coverage contracts | No Belgian procedure, OCR engines, business workflows or legal conclusions |
| Application and adapters | Signed authorization, persistence, processing, review records, exports and recovery | Clients never create evidence or review authority |
| First domain/product | Belgian draft + confirmed inventory + exhibits; identity, independent page mapping, fidelity and human support | No generic legal assistant or AI-native law firm |
| First experience | Web workspace using the authenticated API | Word and MCP remain optional future clients |
| Expansion | A separately approved adjacent task with its own rules, corpus and economics | No new domain or generic plugin framework merely because the kernel is reusable |

## Expansion decision gate

Before authorizing any additional commercial workflow, record all four:

1. **Customer pull:** repeated requests and permissioned representative examples from identified buyers; distinguish interview interest from purchasing intent.
2. **Technical reuse:** a fit/gap assessment of current primitives, domain-specific meanings and failure modes; keep sector rules outside the kernel and preserve isolation. No reuse percentage is assumed.
3. **Measured benefit:** independent ground truth, useful coverage as well as correctness, total reviewer time and intervention cost, and operational cost at observed dossier scale.
4. **Commercial commitment:** a priced paid or explicitly conditional commitment for the additional task, with a named buyer and conditions. A request to try a demo is insufficient.

These support an owner decision packet, not automatic permission to build or release. Record costs, security/data rights, effect on the Belgian litigation roadmap and a superseding scope ADR before implementation. Expansion within litigation can be considered before entering another sector. Existing finance code remains compatibility/reference material.

## Validation and learning

The candidate advantage is reliable, useful bundle verification under document/OCR uncertainty with less total lawyer effort. A pilot supplies initial evidence, not proof of a durable moat. Competitor announcements do not prove demand, integrations or future purchasing intent.

Practitioner failures may become synthetic regression cases or permissioned, rights-cleared examples. Do not retain client text, crops, labels linked to identifiable matters or review records for product learning without an approved lawful basis and explicit written authorization where required. A taxonomy alone is not automatically anonymous.

## Supersession

Clarifies and extends ADR 0018's long-term vision and expansion gate; preserves its Belgian litigation first-market freeze, M0–M6 milestones, web-first experience, four independent states, client-data gates and owner change control. Preserves ADR 0011's modular monolith and kernel sovereignty. No generic platform, DomainPack, extracted kernel service or mandatory MCP server is introduced.

See [roadmap](../ROADMAP.md), [workflow](../PRODUCT_WORKFLOW.md) and [engineering evidence](../STATUS.md). Synthetic signed development acceptance is separate from a usable web product, confidential-client approval and paid demand.
