# CaseProof final-workflow adaptation — code-evidence audit (2026-11-08)

**Source of target requirements:** user-provided `caseproof-final-workflow (2).md`.
**Reference code:** `main` after merged PR #208 (`6aaa8171e1c8f0d59467983aa7872d6dd603ab25`).
**Status:** implementation gap audit and **first bounded adaptation only**. Not a claim that the
full final workflow, customer data handling, model quality or pilot is accepted. The
commercial scope of ADR 0018 is **not silently superseded** by this technical branch.

The source specification's core rule is retained: LLM proposes, deterministic
checks make only their bounded technical assertions, authorized human reviewers
decide semantic support, and the baseline works without an LLM.

## Code-level inventory

| Target capability | Code evidence on main | Present | Connected to signed dossier journey | Testing/acceptance status |
|---|---|---|---|---|
| Signed intake, immutable original hash | `apps/api/workspace_intake.py`, `apps/api/signed_supabase_originals.py`, `apps/api/dossier_journey.py` | Yes | Yes, signed development | Synthetic/signed development tested; independent confidential-client authorization open |
| Original DOCX/PDF/OCR, physical-page evidence | `infrastructure/parsers/`, `apps/api/signed_document_parse.py`, `apps/api/dossier_journey.py` | Yes | Yes, with limits | Unit and development E2E; representative real-source OCR acceptance open |
| Stuk/Pièce reference discovery | `domains/disputes/reference_detection.py`, `infrastructure/parsers/docx_reference_discovery.py` | Yes | Yes | Synthetic NL/FR reference fixtures, recall and unsupported-region caveats |
| Deterministic factual **claim candidates** | Previously only explicit reference candidates and separate evidence-intelligence ClaimSlot contracts | Partial | No general claim inventory in signed dossier report | This branch adds `docx_claim_discovery.py` and separate signed read endpoint; not full factual-classification recall |
| Claim-level coverage | DOCX region/reference denominators in `docx_text_regions.py` and `dossier_contracts.py` | Partial | Reference-level; not full claim-level | This branch adds candidate counts, omission and unscanned scope; factual recall remains unmeasured |
| Evidence discovery/search | `apps/api/litigation_evidence_search.py`, `apps/api/litigation_search_app.py` | Yes | Legacy lexical adapter is development-only; rights-gated checker disables its legacy port | Search tests exist; no signed general per-claim candidate retrieval acceptance |
| Requesty optional inference | `apps/api/requesty_extraction.py`, `application/extraction/pipeline.py` | Yes | No evidence of direct connection to the signed litigation claim-review path | Transport/pipeline tests, synthetic smoke; separate `docs/m2/LIVE_REQUESTY_SMOKE.md` records a failed manual live request |
| LLM NL/FR reranking, claim qualifiers | `application/litigation/paraphrase_guard.py` is **deterministic**, not an LLM ranker | Not accepted | No | Requires authorization, privacy, evals and no-status-promotion tests |
| Identity/page/text checks | `domains/disputes/dossier_verification.py`, `application/litigation/brief_checks.py` | Yes | Yes | Signed/synthetic; independent original PDF falsification still required |
| Human decisions, correction, recheck | `apps/api/dossier_journey.py`, `application/litigation/review_cycle.py`, frontend review/correction features | Yes | Yes | Signed development tested; live pilot not performed |
| Add Fact Cite | `apps/word_addin/` synthetic task pane and `apps/api/litigation_evidence_search.py` candidates | Partial | Not accepted for signed source-to-DOCX insertion | Simulated Office tests; no independent live host insertion/reopen acceptance |
| Real Microsoft Word task pane | `apps/word_addin/`, `manifest-live-dev.xml` | Yes (prototype) | Read-only signed development pathway | Real Microsoft Word host acceptance open; DOCX round trip is not task-pane acceptance |
| Stuk/Pièce numbering and assembled exhibits | Confirmed exhibit register and PDF/DOCX export components | Partial | Narrow reviewed output | Dynamic renumbering/combined exhibit assembly still requires acceptance |
| Rights-gated signed export | `apps/api/dossier_export_release.py`, `apps/api/export_rights_manifest.py`, `application/litigation/release_completeness.py` | Yes | Yes | Synthetic/signature tests; third-party receipt verification and customer acceptance require evidence |
| Threshold registry + full replay | Versioned sub-rules and snapshots in multiple components | Partial | Partial | A single semver registry is not established; threshold version alone is not enough for deterministic replay |
| Gold set and privacy gate | `docs/pilot/P6_PRACTITIONER_AND_CORPUS_PROTOCOL.md`, `docs/security/PILOT_DATA_FLOW.md` | Protocols | Not a running customer pilot | Written rights, legal approval, independent labels and real-pilot execution open |

## Changes in this draft branch

1. Add a bounded, no-model **candidate** inventory from already-extracted DOCX text.
   Stable IDs bind to original DOCX SHA-256, region, offsets and literal text.
   It emits possible numbers, dates, names and Stuk/Pièce references, **not
   factual claims deemed true or false**.
2. Expose candidates at `GET /v2/matters/{case_id}/briefs/{brief_id}/dossier/claim-candidates`.
   The signed dossier store performs the existing bundle/action-rights read,
   verified original readback, snapshot and post-check; the route cross-checks
   the original hash against the signed draft row. No independent untrusted
   evidence-input or model provider is introduced.
3. Carry `unscanned_parts`, `omitted_candidate_segments`,
   `factual_claim_recall_measured=false` and
   `claim_semantics_assessed=false`, even if all supported text was scanned.
4. Regression-test NL/FR lexical candidates, limits, scope omissions,
   injection-like text, unsigned access and source-hash mismatch.

**Non-goals:** No LLM calls, semantic verdicts, automatic release, new
correction commands, Word installation, signed receipt-format changes,
external-data egress, provider credential changes or database migrations.
`main` must not be called full-final-workflow compliant because this
draft feature exists.

## Specification phrases that cannot be interpreted as authoritative facts

- “Proves every factual claim”: claim detection recall is not proven;
  report the discovered scope and abstain on omissions.
- “Raw OCR text ... source of truth”: the preserved original pixels/bytes
  are authoritative. OCR text is a derived representation with uncertainty.
- “Unlinked claims ... unsupported”: use “no support located within the
  searched scope,” not a finding of falsehood or legal insufficiency.
- “verified (literal match)”: a literal match is **technical fidelity only**;
  human-only semantic support remains a separate decision.
- “DOCX round trip counts as a Word panel”: false for Office-host acceptance.
- “same threshold version reproduces identically”: reproducibility also
  requires exact originals, index/representation/rule versions and proposals.
- “zero filing risk”: confidential non-filing research still needs signed
  permissions and an approved privacy/security processing boundary.
- “cut scope, never pilot”: do not waive mandatory legal/security prerequisites.

## Next implementation dependencies — audit-gated

1. Agree the versioned, reviewed **claim identity and coverage contract**:
   candidate semantics; offset stability; DOCX stories/footnotes; bounded
   original text; snapshots, stale IDs and region/corpus coverage.
2. Reuse the authorized lexical search port to find candidate evidence for an
   explicit claim, without treating a hit as proof of support. Check source
   snapshot/grants before and after retrieval.
3. Only when the privacy/provider decision is approved, adapt Requesty's
   existing proposal-only pipeline for bounded NL/FR reranking, with no tools,
   frozen candidate passages, prompt/version provenance and LLM-off parity.
4. Wire lawyer-reviewed evidence selection into a version-safe Add Fact Cite
   command and test actual source PDF/page and DOCX save/reopen. The current
   synthetic task pane is a starting point, not production acceptance.
5. Extend exhibit assembly and receipt validation without weakening the
   existing release-completeness and document-rights gates.
6. Run independent falsification and reviewer study on rights-cleared NL/FR
   dossiers; do not report commercial validation from synthetic CI.

## Sources

- [Current roadmap](ROADMAP.md)
- [ADR 0018](adr/0018-pre-submission-verification-freeze.md)
- [Signed dossier orchestration](../apps/api/dossier_journey.py)
- [Requesty provider](../apps/api/requesty_extraction.py)
- [Evidence intelligence contracts](../application/extraction/contracts.py)
- [Existing lexical search](../apps/api/litigation_evidence_search.py)
- [Word integration boundary](../apps/word_addin/README.md)
- [Practitioner corpus protocol](pilot/P6_PRACTITIONER_AND_CORPUS_PROTOCOL.md)
- [Pilot data-flow boundary](security/PILOT_DATA_FLOW.md)
