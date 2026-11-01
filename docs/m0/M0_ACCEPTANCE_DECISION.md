# M0 acceptance decision record — 31 October 2026

**Decision state: NOT APPROVED / M0 REMAINS OPEN.** The product owner requested completion of all outstanding M0 gates; that request authorized engineering and preparation, **not a fabricated independent lawyer's review or a signature by the owner**. Do not convert this document to APPROVED without actual dated evidence.

## Evidence ledger

| Requirement | Evidence now provided | Approval state |
|---|---|---|
| Vision, design, source-of-truth and four dimensions | [Roadmap](../ROADMAP.md), [ADR 0018](../adr/0018-pre-submission-verification-freeze.md), [ADR 0019](../adr/0019-evidence-engine-and-first-market.md), merged PR #155 | Engineering review complete |
| Author-supplied NL/FR/EN/mixed synthetic labels | [v3 JSON](../../evals/litigation/m0_corpus_v3.json), [synthetic audit](../../scripts/audit_m0_trilingual.py), merged PR #156 | Machine consistency only; **not independent gold** |
| Real-format synthetic evidence | [Generator](../../scripts/m0_real_format_fixtures.py), [tests](../../tests/test_m0_real_formats.py), [manifest](../../docs/m0/REAL_FORMAT_EVIDENCE.md), exact PR/CI receipt | Conditional on PR CI and manifest byte reopen; cannot prove real-world OCR quality |
| Blinded human review | [Blind packet generator](../../scripts/m0_blind_review.py), [qualified adjudication packet](TRILINGUAL_ADJUDICATION_PACKET.md) | **Awaiting two independent language judgments for each gold item**, Belgian legal practitioner where relevant |
| External rights/real-document approval | [Rights declaration](TRILINGUAL_RIGHTS_AND_COVERAGE.md) for new entirely fictional material | Synthetic authorship declared; any later external real material requires distinct rights and confidentiality approvals |
| Formal owner release of M0 | Signed owner acceptance with precise corpus hash, reviewers, corrections and remaining exclusions | **NOT SIGNED** |

## Review submission processing

`scripts/validate_m0_independent_reviews.py` checks submission completeness, exact
corpus binding, distinct declared reviewers, language competence, source observations,
independence/evidence fields and disagreements. It cannot authenticate people or
signatures, establish rights or approve the milestone. Its `m0_approved` output is
always false. Complete forms still require external verification and a named owner.

## Independent review required before acceptance

The blind packet intentionally **excludes author gold labels**. Reviewers must have real identities/organizations, language competence, independent attestation, exact corpus hash and date. At least two independent judgments per case must be recorded; a qualified Belgian practitioner covers applicable procedure; disagreements need an adjudicator. The existing 19 legacy v2 cases have no separately confirmed inventory scope, so reviewers must not invent `NOT_IN_INVENTORY`. Those cases may need a new v4 gold definition before M0 closure.

## Owner signoff fields (intentionally unfilled)

- **Decision:** NOT APPROVED
- **Reviewed exact commit SHA:** NOT RECORDED
- **Current corpus SHA-256:** attach the CI `scripts.audit_m0_trilingual` receipt
- **Actual rights approval and external review record:** NOT RECEIVED
- **Named owner / signed decision / date:** NOT PROVIDED
- **Remaining limitations:** Not representative of law-firm accuracy, real-world semantic support or customer-data permission

**Release boundary:** M0 engineering can be merged while formal M0 remains OPEN. Product M1–M4 and M5 discovery can proceed in parallel using synthetic rights-declared fixtures; confidential-customer or external trials remain separately blocked by SEC-01–16.
