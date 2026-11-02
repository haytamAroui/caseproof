# CaseProof skills source register — evaluation candidates

This is an **evaluation register**, not a dependency approval or assertion that the repositories were audited. External examples are untrusted; license and version must be verified at adoption time. The CaseProof constitution, frontend blueprint, signed API contracts and frozen evidence kernel supersede every external pattern.

| Reference | URL | Proposed lesson | Guardrail |
| --- | --- | --- | --- |
| Mike OSS | https://github.com/Open-Legal-Products/mike | Partial-failure recovery, permission-denial UI, document/citation grids, Word testing | AGPL: study patterns; do not vendor source without legal review |
| Mike workflows | https://github.com/Open-Legal-Products/mike-workflows | Portable workflow templates and task-specific skills | Verify actual file/asset licenses and provenance |
| Mini Mike | https://github.com/allNeurons-AI/mini-mike | Citable-cell report discipline | Not a CaseProof verification authority |
| Anthropic legal plugins | https://github.com/anthropics/claude-for-legal | Prerequisite gates, explicit provisional output, substantive completion | Adapt concepts; no conflicts-screening claims |
| Judicex | https://github.com/JustVugg/judicex | Versioned procedure configuration | No case-law/deadline feature creep |
| Lawgent | https://github.com/WenzhuoXu/lawgent | Source re-fetch and quote round-trip | Never silently repair authoritative source |
| LQ AI | https://github.com/LegalQuants/lq-ai | Explainable citation provenance | UI must show actual backend evidence |
| safe-docx | https://github.com/UseJunior/safe-docx | Candidate tracked-changes DOCX adapter | Separate benchmark, format preservation, egress and license gates |
| Legal Skills visualization | https://github.com/cat-xierluo/legal-skills | Diagram overlap/text capacity tests | Reported CC-BY-NC: do not copy commercial-incompatible materials |
| Open Agreements | https://github.com/open-agreements/open-agreements | Document-mechanics disclaimers | US legal templates not Belgian authority |
| Belgian bar authorities | https://www.ordevanvlaamsebalies.be/ ; https://avocats.be/ | Professional secrecy and practitioner review | Obtain dated authoritative guidance and qualified legal review |

## Admission process
1. Record repository URL, immutable commit SHA, SPDX/license and attribution obligations.
2. Inspect data flow, prompt/tool execution, outbound network calls, dependency tree and supply-chain risks.
3. Run representative synthetic Belgian NL/FR/EN DOCX, text PDF and scanned PDF fixtures.
4. Measure preservation, uncertainty handling, authorization and recovery; collect negative test evidence.
5. Require explicit architecture decision and legal/security approval before incorporating code.
6. Keep evaluation receipts and reject marketing claims not supported by measurements.

## Boundaries
CaseProof is a post-assembly exhibit-reference verifier, not a legal-research agent, a conflicts-screening system, or a deadline calculator. Never import a competitor's framework just because its UI looks similar. Existing `frontend/BLUEPRINT.md` is authoritative for Vite/React/TypeScript and backend boundaries; CaseProof does **not** use Next.js for the current frontend.
