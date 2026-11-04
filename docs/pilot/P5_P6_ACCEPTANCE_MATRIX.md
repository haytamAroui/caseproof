# CaseProof P5/P6 — dated engineering and pilot evidence ledger

**4 November 2026.** Branch: feat/p5-p6-readability-drift-pilot; PR #185. The evidence below is **synthetic and development scoped**. It is not Microsoft Word certification, operational Supabase restore proof, manual accessibility sign-off, representative-corpus permission, practitioner agreement or approval to process confidential dossiers.

## Engineering evidence collected

| Area | Actual observation | Evidence and limitation |
| --- | --- | --- |
| P5 report and provenance | Readable DOCX labeled appendix, XML character rejection, preserved original ZIP members, source/draft digest and review identities | [kernel architecture regression](https://github.com/haytamAroui/caseproof/actions/runs/41816156764), source tests. Automated render does not prove legal correctness |
| P5 exhibit drift | Frozen snapshot-bound explanatory matching, uncertain/unsupported changes and no review transfer | [application and browser tests](https://github.com/haytamAroui/caseproof/actions/runs/41816156761), server-side tests; not a semantic proof |
| T61 Writer host | **PASS: actual LibreOffice Writer 24.2.7.2 on Ubuntu CI**, synthetic original → corrected → annotated DOCX → PDF and ODT/DOCX reopen, text/table/ZIP checks | [P6 host/restore evidence](https://github.com/haytamAroui/caseproof/actions/runs/41827922427). Microsoft Word desktop and independent visual host audit remain OPEN |
| T70 dev security | Read-only catalog audit of private tables, public privileged RPCs, auth settings; zero direct grants on selected private release/snapshot tables | [Detailed inspection](P6_SECURITY_DEPENDENCY_PRIVACY_TRIAGE_2026-11-04.md), Supabase dev. 15 privileged-RPC advisories still require independent review |
| T72 dependency hygiene | npm lock and Python lock checked; sanitized audit = **11 moderate dev-tooling, 0 production**, no high/critical | [P6 supply-chain run](https://github.com/haytamAroui/caseproof/actions/runs/41827922427). Dev advisories not patched or waived; independent owner disposition OPEN |
| T73 privacy disclosure | Signed development intake visibly states originals and metadata go to Supabase; never claims offline or zero-egress; deployment assessments verified | [P6 corpus/privacy contracts](https://github.com/haytamAroui/caseproof/actions/runs/41827922427), [flow map](../security/PILOT_DATA_FLOW.md). Provider/region/retention/whole-deployment capture and contracts OPEN |
| T74 isolated restore | **PASS: PostgreSQL 17 disposable backup/restore**, four actual CaseProof relation-count checks, test of stale pre-erasure backup, replayed synthetic erasure, private direct grants checked, isolated copy dropped | [P6 restore drill](https://github.com/haytamAroui/caseproof/actions/runs/41827922427). **NOT** an actual Supabase provider backup/restore or full legal-hold recovery test |
| T75 automated a11y | **PASS: Playwright + axe**, keyboard/Enter, narrow 320px, browser zoom simulation, forced colors, reduced motion, long NL/FR/EN synthetic citations | [Frontend CI](https://github.com/haytamAroui/caseproof/actions/runs/41827922398). Genuine screen-reader and human WCAG 2.2 AA review OPEN |
| T76 synthetic corpus | **PASS: author-supplied unadjudicated** NL/FR/EN/mixed regression fixtures and negative controls, integrity check with SHA | [P6 corpus validation](https://github.com/haytamAroui/caseproof/actions/runs/41827922427). Rights-cleared representative client corpus and independent gold labels OPEN |
| T77 signed integrated journey | **PASS: implementation SHA 9004659**, genuine signed intake, review, correction/recheck, release, historical cold reopen, revocation and zero-residual teardown | [Signed F6 run 41827922447](https://github.com/haytamAroui/caseproof/actions/runs/41827922447), confirmed success. Subsequent documentation-only HEAD still requires fresh CI; skipped narrower workflows never count as passes |
| T78 practitioner utility | **NOT RUN** | [Consent, denominator and stop rules](P6_PRACTITIONER_AND_CORPUS_PROTOCOL.md). No independent participants, metrics or commitments claimed |
| T79 formal pilot declaration | **BLOCKED pending human/operational gates** | No sign-off or real client upload authorization |

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
