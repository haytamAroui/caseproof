# CaseProof P5/P6 — dated engineering and pilot evidence ledger

**4 November 2026.** Engineering PR #185 **merged** to `main` as `b162a5f7a08975949a32671cbea774b7f0a7bb09`. Final tested PR head: `3c6058a054ffd5172413cba5b90eb9af4bb44586`; reconciliation in [PR #186](https://github.com/haytamAroui/caseproof/pull/186). The evidence below is **synthetic and development scoped**. It is not Microsoft Word certification, operational Supabase restore proof, manual accessibility sign-off, representative-corpus permission, practitioner agreement or approval to process confidential dossiers.

## Engineering evidence collected

| Area | Actual observation | Evidence and limitation |
| --- | --- | --- |
| P5 report and provenance | Readable DOCX labeled appendix, XML character rejection, preserved original ZIP members, source/draft digest and review identities | [kernel architecture regression](https://github.com/haytamAroui/caseproof/actions/runs/41829163374), source tests. Automated render does not prove legal correctness |
| P5 exhibit drift | Frozen snapshot-bound explanatory matching, uncertain/unsupported changes and no review transfer | [application and browser tests](https://github.com/haytamAroui/caseproof/actions/runs/41829163384), server-side tests; not a semantic proof |
| T61 Writer host | **PASS: actual LibreOffice Writer 24.2.7.2 on Ubuntu CI**, synthetic original → corrected → annotated DOCX → PDF and ODT/DOCX reopen, text/table/ZIP checks | [P6 host/restore evidence](https://github.com/haytamAroui/caseproof/actions/runs/41829163280). Microsoft Word desktop and independent visual host audit remain OPEN |
| T70 dev security | Read-only catalog audit of private tables, public privileged RPCs, auth settings; zero direct grants on selected private release/snapshot tables | [Detailed inspection](P6_SECURITY_DEPENDENCY_PRIVACY_TRIAGE_2026-11-04.md), Supabase dev. 15 privileged-RPC advisories still require independent review |
| T72 dependency hygiene | npm lock and Python lock checked; sanitized audit = **11 moderate dev-tooling, 0 production**, no high/critical | [P6 supply-chain run](https://github.com/haytamAroui/caseproof/actions/runs/41829163280). Dev advisories not patched or waived; independent owner disposition OPEN |
| T73 privacy disclosure | Signed development intake visibly states originals and metadata go to Supabase; never claims offline or zero-egress; deployment assessments verified | [P6 corpus/privacy contracts](https://github.com/haytamAroui/caseproof/actions/runs/41829163280), [flow map](../security/PILOT_DATA_FLOW.md). Provider/region/retention/whole-deployment capture and contracts OPEN |
| T74 isolated restore | **PASS: PostgreSQL 17 disposable backup/restore**, four actual CaseProof relation-count checks, test of stale pre-erasure backup, replayed synthetic erasure, private direct grants checked, isolated copy dropped | [P6 restore drill](https://github.com/haytamAroui/caseproof/actions/runs/41829163280). **NOT** an actual Supabase provider backup/restore or full legal-hold recovery test |
| T75 automated a11y | **PASS: Playwright + axe**, keyboard/Enter, narrow 320px, browser zoom simulation, forced colors, reduced motion, long NL/FR/EN synthetic citations | [Frontend CI](https://github.com/haytamAroui/caseproof/actions/runs/41829163384). Genuine screen-reader and human WCAG 2.2 AA review OPEN |
| T76 synthetic corpus | **PASS: author-supplied unadjudicated** NL/FR/EN/mixed regression fixtures and negative controls, integrity check with SHA | [P6 corpus validation](https://github.com/haytamAroui/caseproof/actions/runs/41829163280). Rights-cleared representative client corpus and independent gold labels OPEN |
| T77 signed integrated journey | **PASS: exact final PR head 3c6058a**, genuine signed intake, review, correction/recheck, release, historical cold reopen, revocation and zero-residual teardown | [Signed F6 run 41829162860](https://github.com/haytamAroui/caseproof/actions/runs/41829162860), confirmed exact-head success with `DOSSIER_COMPLETE_SIGNED_JOURNEY_AND_TEARDOWN_PASSED` and `ZERO_RESIDUAL_VERIFIED`; four skipped narrower workflows are not independent passes |
| T78 practitioner utility | **NOT RUN** | [Consent, denominator and stop rules](P6_PRACTITIONER_AND_CORPUS_PROTOCOL.md). No independent participants, metrics or commitments claimed |
| T79 formal pilot declaration | **BLOCKED pending human/operational gates** | No sign-off or real client upload authorization |

## Open real-world acceptance and handoff for PR #186

The merged engineering release is **not** a pilot approval. The following items are outstanding despite successful automated checks. Each receipt must name a responsible owner and independent reviewer, environment, exact versions/commit, approved input rights, evidence and negative cases, outcomes, limitations, rollback and dated sign-off. An unassigned owner or missing receipt means OPEN.

| Work item | Owner/action required | Evidence to append (private for sensitive materials) |
| --- | --- | --- |
| T60 / T66 | Independent engineering reviewer | Comment/review of exporter, source/page drift, unsafe/uncertain cases and API/UI auth; signed-off findings |
| T61 | Word desktop tester and independent document reviewer | Word OS/version, original/corrected/annotated files, styles/runs/tables/footnotes/comments/links, hashes and screenshots; LibreOffice alone insufficient |
| T70 | Security/database owner | 15 SECURITY DEFINER RPC body/grant/search_path assessments, anon/authenticated RLS and cross-matter/revoked signed tests, leaked-password setting remediation or recorded decision |
| T72 | Dependency owner | 11 named moderate dev-tooling advisories: patch/version and green CI, or review of exploitability with time-limited explicit risk exception |
| T73 | Deployment/privacy owner | Region/processors/DPA, exact browser/API/OCR egress, authorized network capture, retention/legal hold, deletion/backup and privacy sign-off |
| T74 | Operations and privacy owners | Authorized isolated restore from actual Supabase backup, tenant/role enforcement, source/geometry/report/review/release coverage, erasure replay, teardown and recovery measurements |
| T75 | Independent a11y tester | Screen-reader/browser/OS, real 200% zoom, focus, validation/recovery, keyboard only, locale/contrast tests with remediation receipts |
| T76 | Rights/data owner and label reviewers | Written authorized rights, representative 3–5 NL/FR/EN dossiers, controlled private hash manifests and independently adjudicated gold labels |
| T77 | Engineering owner | **Done for PR #185 head**: [final signed F6 #41829162860](https://github.com/haytamAroui/caseproof/actions/runs/41829162860); re-run only if relevant implementation changes |
| T78 | Two consenting independent practitioners | Timed manual-vs-product reviews, exact gold denominators, false verified/abstain/page/recall measures, agreement, stop rules and corrections |
| T79 | Product + security + privacy + operations signers | Explicit pilot decision after other gates, residual risks, permitted data class, rollback, limits and authorization |

**Do not** put confidential real corpus, tokens, backups, practitioner consent or private signatures in the public repository, workflow artifacts or logs. No production migration, provider policy or credentials are changed by PR #186.

## Outstanding genuine acceptance (requires actual people/systems)

- Microsoft Word desktop on declared OS, versioned host reopening and manual inspection of all supported formatting.
- Independent expert review of public SECURITY DEFINER RPC bodies, security advisories, actual signed role/tenant matrix, and selected provider configuration; enable/approve leaked-password protection.
- A selected deployment and privacy owner to record provider regions, data-processing terms, exact retention/backup expiry, legal holds, full-flow network captures and actual authorized restore of provider backups.
- Independent manual accessibility tester using actual screen reader and browser, including keyboard, localization, 200% real zoom, forced colors and error focus.
- Written permission for real representative NL/FR/EN dossiers, confidential custody and independent adjudicated labels; 2 reviewers' blinded manual-vs-CaseProof study and safety/utility report.
- Actual pilot/operations/security/privacy decisions, with named signers, signed-off residual risk, rollback and stop rules.

## Per-gate evidence schema (do not fabricate)

task_id, status (OPEN / EVIDENCED / APPROVED / BLOCKED), actor and reviewer, environment, document class and rights, exact commit, run URL, tool/host versions, observed result, negative cases, limitations, zero-residual cleanup, rollback, dated approval. Missing evidence is OPEN, not zero.

See [practitioner protocol](P6_PRACTITIONER_AND_CORPUS_PROTOCOL.md) and [P6 dev security triage](P6_SECURITY_DEPENDENCY_PRIVACY_TRIAGE_2026-11-04.md). No customer documents or credentials are stored in public CI artifacts.

Authoritative external acceptance frameworks: [GDPR Article 32](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679), [WCAG 2.2](https://www.w3.org/TR/WCAG22/), [npm security audit](https://docs.npmjs.com/auditing-package-dependencies-for-security-vulnerabilities/).
