# ADR 0019 — Reusable evidence engine, Belgian litigation first

**Decision date:** 30 October 2026. **Status:** ACCEPTED product-direction clarification at the owner's instruction. No new vertical, runtime architecture, pilot, production processing or release is authorized.

## Decision

**Vision:** make evidence-backed professional work inspectable: trace an important statement to an exact preserved source, expose incomplete or unreliable coverage, and preserve an accountable human review. **First market:** independent pre-filing Stuk/Pièce exhibit-reference verification for Belgian FR/NL civil/commercial litigation, not a general citation checker or an exhibit-assembly product.

One reusable kernel, one focused product today, evidence-led expansion. Litigation is already a vertical. Kernel flexibility provides options; it is not evidence of demand or domain correctness in contracts, compliance or accounting.

| Layer | Responsibility | Boundary |
|---|---|---|
| Evidence kernel | Sector-neutral source/representation identity, anchors, provenance, versions and coverage contracts | No Belgian procedure, OCR engines, business workflows or legal conclusions |
| Application and adapters | Signed authorization, persistence, processing, review records, exports and recovery | Clients never create evidence or review authority |
| First domain/product | Belgian draft + confirmed inventory + exhibits; identity, independent page mapping, fidelity and human support | No generic legal assistant or AI-native law firm |
| First experience | Web workspace using the authenticated API | Word and MCP remain optional future clients |
| Expansion | A separately approved adjacent task with its own rules, corpus and economics | No new domain or generic plugin framework merely because the kernel is reusable |

## 31 October positioning and delivery clarification

**The job is independent post-assembly verification.** Lawyers may already number, stamp and organize their pieces using Word, a DMS or an exhibit-assembly product. CaseProof checks the resulting *supplied* conclusion draft and confirmed inventory against the *preserved original* documents with four separate dimensions: identity, independent PDF/printed/bundle page positions, literal/visual/value fidelity, and authorized human semantic support. Never collapse dimensions into one verified badge. Human decisions and checks are frozen to source, draft, inventory, processing and rule versions. Hashes prove byte continuity, not authenticity or that anything was filed.

**First commercial experience:** authenticated **web** upload → confirm → check → source/crop inspection → human review and safe correction proposal → scoped DOCX/report export → reopen. The kernel/headless API is not a second sellable platform or an excuse for framework work. Word and a publicly hosted MCP client remain optional channels; the MCP host implementation in merged PR #153 has **not** passed production deployment/live OAuth/host consent acceptance.

**Potential differentiation, not a uniqueness claim:** useful independent verification of Belgian exhibits, three non-interchangeable page spaces, OCR/text-layer disagreements, explicit abstention and durable source-linked review at lower measured total lawyer effort. Competing products may offer assembly **and** verification; direct workflow comparisons are required. No factual exclusivity or commercial moat is established.

**Deployment is not the interface:** web-first does not imply remote processing. Original-byte custody, OCR/processing location and audit/provenance remain separate ports. Hosted, hybrid and firm-controlled deployment require documented outbound fields, backup/log retention, security/professional-secrecy review and buyer evidence before choosing or marketing them. A deterministic core is not a legal clearance; even reference strings, hashes and timing may be sensitive.

**Commercial and naming limits:** first five disconfirming interviews, two observed manual workflows and a conditional priced commitment request precede any product-family pivot. Synthetic/sample trial first; confidential client evidence only after the approved SEC-01–16 controls. CaseProof is a provisional public name pending EUIPO/BOIP clearance. Do not sell authority research, court-filing automation, legal certification, signed-lawyer attestation or qualified timestamps as current features.

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


## 31 October owner-requested refinement

Adopt the detailed [product definition and prioritized delivery](../PRODUCT_DEFINITION_2026-10-31.md): supplied snapshot wording, independent four-dimensional report, consolidated bundle intake, version-bound review, measured reference recall and conditional deployment/signature/channel expansion. Preserve current gates and web-first delivery. The owner authorizes this planning update, not implementation or release of every proposed option.
