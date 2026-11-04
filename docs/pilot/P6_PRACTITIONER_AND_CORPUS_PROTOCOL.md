# CaseProof P6 practitioner study and corpus intake — execution protocol

**2026-11-04:** This file is a protocol, **not** evidence that a practitioner participated, client consented, or a Microsoft Word desktop host was tested. Do not upload client files to GitHub/public CI.

## Corpus separation and rights

1. **Synthetic, author-supplied regression corpus**: evals/litigation/m0_corpus_v2.json, validated by scripts/validate_litigation_corpus.py. The fixtures explicitly state author_supplied_unadjudicated and cover NL/FR/EN/mixed languages, absent scan text, missing and moved citations, duplicate inventory matches, and prompt injection. SHA-256 of this file is recorded in CI. This is not independently adjudicated or a representative litigation sample.
2. **Real rights-cleared documents**: OPEN. Every dossier requires the actual rights holder's written testing authorization, permitted geography/processors, privacy classification, hash, retention and legal-hold restrictions, and independent adjudication records, held privately. The absence of permission is a BLOCKER.
3. **Pilot corpus**: OPEN until permissioned representative DOCX+inventory+PDF text/scans (including NL/FR/EN), 3–5 dossiers, repeated citations and source moves, document-host fidelity cases and independently reviewed gold labels exist. Synthetic checks alone cannot close T76.

## Pre-registered practitioner protocol

Two independent practicing reviewers, appropriate permission/consent, 3–5 authorized dossiers. Randomize/counterbalance manual review and CaseProof conditions, guarding against knowledge carryover. Record actual build SHA and input hashes; keep observations confidential.

For every case collect: total independently adjudicated references; detected references; false verified claims; unmapped/mis-mapped physical pages; not assessed/abstained items; OCR uncertainty; time-to-decision; review agreement; confidence in uncertainty explanations; newly introduced correction errors. Compute recall with a nonzero actual gold denominator. Keep uncertainty separate from false approval. Never invent performance or paid commitment data.

Stop immediately on unsupported verified state, wrong-source rendering, case isolation failure, uncaught revocation, unsafe derivative, or missing data permission. Practitioner disagreement requires a third adjudication or explicit unresolved note.

## Host and accessibility handoff

Desktop Microsoft Word **and** LibreOffice Writer: capture version, OS, original and derivative SHA-256, reopen notes/screenshots, paragraphs, styles, runs, tables, footnotes, comments, links, page labels, and re-save behavior. Automated LibreOffice round-trip alone does not close Word support.

Real keyboard-only/assistive technology: record tester, actual screen reader/AT version and browser; inspect focus order, errors, recovery, saved review, export and history; 200% real browser zoom, narrow layout, forced colors, reduced motion, NL/FR/EN long strings. Axe/Playwright is a supplement, not a WCAG 2.2 AA human sign-off.

## Evidence template

| Field | Required value |
| --- | --- |
| Case rights and data owner | Actual signed authorization URI in private storage |
| Corpus input identity | SHA-256 and approved confidential classification |
| Independent label reviewers | Two names/roles; conflicts and adjudication URI |
| Practitioner consent | Dated private consent record |
| Host/accessibility versions | OS, Word/Writer, browser/AT and timestamp |
| Manual and CaseProof time | Actual seconds, with protocol and ordering |
| Error denominators | Gold references, false verified, abstained, source/page errors |
| Cleanup/retention | Owner, deletion and incident response evidence |
| Approval | Actual independent reviewer signature and date, or OPEN |

Missing numeric outcomes are **unknown**, not zero. The study has not run merely because a protocol and CI corpus exist.
