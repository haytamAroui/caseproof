# Paid QAE / Evidence Intelligence adaptation audit

24 October 2026. **Result: substantial proposal/safety infrastructure, partial paid-pipeline adaptation, not extraction-phase completion.** Earlier summaries saying that components, global-first execution, signal promotion and four-pass extraction were simply “implemented” were too broad. Code exists for conservative versions of these concepts; capability names do not establish equivalence to AZComply or completion of the supplied roadmap.

## Scope and reproducibility

| Repository | Pinned source | Inspection |
|---|---|---|
| CaseProof | [`7c27e4ffcb5d512a55f88aca48423adb1d923861`](https://github.com/haytamAroui/caseproof/commit/7c27e4ffcb5d512a55f88aca48423adb1d923861) | Merged #53–56 runtime, parsers, domain policies, review, exports, worker, tests and evaluation |
| AZComply | [`4249ea640568b5a95e0f57758e3c9479c7b40267`](https://github.com/haytamAroui/azcomply/commit/4249ea640568b5a95e0f57758e3c9479c7b40267) | 35 selected extraction/paid-route files fetched through the authorized GitHub connector; relevant entrypoints and authority branches inspected |

This is a selective code/contract comparison, not a line-by-line audit of the complete AZComply tree, an execution of its paid service, an assessment of deployed feature flags, or a security certification. The extraction root currently lists 116 top-level Python files; nested modules were not counted to reconcile the older roadmap's “123” inventory. No production topology is inferred from source defaults. No AZComply implementation, credentials or database data was copied into CaseProof. No live Requesty call, customer document, production migration or deployment was performed.

“Reference implemented” below means working proposal-only code with relevant tests. “Partial” means a narrower mechanism exists but important required behavior is missing. “Missing” means no implementation was found in the inspected CaseProof workflow. “Intentional exclusion” is a domain/authority boundary, not a defect to fix by copying AI Act code.

## Executive finding

Preserve the Kernel and current reference implementations. The strongest completed adaptations are immutable source/representation identities, exact quote checks, conservative source/entity eligibility, explicit failed/rejected candidates, scoped immutable checkpoints, response replay, worker fencing and unapproved draft export.

The largest unfinished **extraction** capabilities are a durable entity-boundary clarification/confirmation workflow, a typed signal registry with explicit per-signal decisions/consumer policies, richer typed facts/reconciliation, and evidence-matrix-driven targeted repair. Separate downstream gaps remain in genuine authenticated production intake, accepted finding/link/coverage persistence and consequential human decisions. Scripted tests do not establish extraction accuracy.

## Capability-by-capability mapping

| # | Paid AZComply pattern / roadmap requirement | Actual CaseProof evidence | Assessment and gap |
|---|---|---|---|
| 1 | Paid extraction is QAE-first, distinct from free questionnaire classification | [A1], [A2]; [C1], [C2] | **Correct direction.** CaseProof is document-to-candidate extraction, not a port of the free SystemFacts questionnaire. |
| 2 | QAE atom schema and quote-anchored prompt | [A3]; `Atom`, `SYSTEM`, `_envelope`, `check_atom` in [C1] | **Reference implemented.** Strict envelope, polarity/relation vocabulary and exact quote. Subject/object, typed event time, typed Decimal amount/currency and richer allegation attribution from the target roadmap are absent from the generic atom. `value` is a string. |
| 3 | Source blocks and immutable representation-bound identity | [A3], [A4]; [C2], [C3], Kernel projection in [C1] | **Reference implemented** for current formats. Originals, parser manifest, representation digest, Unicode spans and page/path/part maps are preserved. This does not establish authenticity. |
| 4 | Exact/fuzzy quote verification and eligibility | [A4]; `_locate`, `check_atom`, `project_to_kernel` in [C1] | **Deliberately stricter adaptation.** Exact match required; repeated text needs an explicit exact start. No fuzzy auto-promotion. Fuzzy location suggestions are not implemented and are not required for safe default eligibility. |
| 5 | Component segmentation with sentence labels and boundary policy | [A5]; `EntityAssignment`, `EntityScope` in [C2], [C4] | **Partial.** Caller-supplied independent boundaries are enforced, but no equivalent deterministic business-identity/temporal clustering or operational-vs-commentary sentence labeling workflow exists. Intake expands selected parser blocks into boundaries; it does not infer/confirm business segmentation. |
| 6 | Quote-grounded component clarification | [A6]; `_discover` in [C1] | **Partial proposal discovery.** Quote-backed entity proposals are retained. No separate clarify → edit → source-rebind → confirm service. |
| 7 | Explicit outcome for every proposed component boundary | [A7]; [C5], [C6] | **Missing as an entity workflow.** Review commands refer to atoms or case evidence requests, not versioned boundary proposals. `confirmed=True` is an input to intake, not the output of a durable authenticated boundary review. The model cannot set it, which is correct. |
| 8 | Atom-to-component/source/block/family alignment | [A8]; `check_atom` and step-scope checks in [C1] | **Reference implemented for current contracts.** Exact source and independent entity-range/claim-slot checks block wrong ownership. No richer issue-family alignment or cross-entity relationship validation comparable to AZComply. |
| 9 | Case-wide global scout followed by planned repair | [A9]; `EvidenceIntelligence.run` in [C1] | **Partial, name overstates equivalence.** CaseProof plans a scout plus one full-source task per input before consuming scout output. Discoveries do not alter targeting, boundaries or claim inventory. AZComply builds a segmented skeleton, verifies alignment, builds a component/family matrix and plans bounded repair batches. |
| 10 | Segmented execution | [A10]; topology branch in [C1] | **Partial.** Per-boundary tasks and bounded concurrency exist, with post-extraction attribution gates. Each task still sends the full source representation, including other entities; `focus_entity` is a prompt hint. No cropped, offset-preserving entity context builder. This is same-case context, not a demonstrated cross-tenant leak. |
| 11 | Adaptive extraction depth/preflight | [A9], [A10]; `ExtractionConfig` in [C4] | **Partial.** Deterministic budgets/strict no-downgrade behavior exist. No equivalent operational preflight selecting depth from case complexity, prior conflict, coverage or risk. Caller selects topology. |
| 12 | Four complementary extraction passes | [A11]; four-purpose loop in [C1] | **Partial and experimental.** Four passes exist and duplicates are not counted as votes. They share complete source text and differ by purpose; no AZComply-style sentence-selected contexts, pass ownership, vocabulary-hit context or adaptive pass plan. No measured improvement supports activation by default. |
| 13 | Typed, categorized signal registry and consumer accountability | [A12]; [C7], `Vocabulary` in [C4] | **Partial.** Two versioned vocabularies with 7 finance and 8 construction signals, lexical phrase/value checks and allowed entity kinds. No registry records for category, severity, semantic validator coverage, reviewer policy, consumer slots and per-signal version. `payment_asserted` is conservative; it is not payment confirmation. |
| 14 | Separate quote verification, signal validation and promotion decision | [A13]; `check_atom`, [C7], [C5] | **Partial.** Unknown signals are review-only; confidence cannot establish eligibility; authoritative approval is disabled. There is no persisted typed FactSignalCandidate/SignalDecision stage equivalent to AZComply's CandidateSignal/ValidatedSignalDecision/FactPatch. Atom state/reason plus manifest version is a narrower trace. Kernel promotion remains a separate pure policy, not a completed extraction-to-decision transaction. |
| 15 | Negation, allegations, legal commentary, user instructions | [A5], [A13]; screen and polarity checks in [C1], tests [T1] | **Conservative guard implemented, semantic parity absent.** English/French/Dutch lexical screening and polarity hold candidates for review. A matching phrase/value is labeled `proposal_lexically_consistent`, not proven semantic support. No robust multilingual role/negation/conditional assessor or labeled-sentence quarantine. |
| 16 | Entity/module grouping and mapping | [A14]; slot grouping and Kernel projection in [C1] | **Partial and correctly domain-neutral.** Existing findings/links/coverage are reused; no parallel authoritative CaseFacts table. No broad grouping/reconciliation of entity identities and source revisions. ModuleFacts/SystemFacts are intentionally excluded. |
| 17 | Cross-source conflicts/reconciliation | [A15]; conflict loop and slot results in [C1] | **Basic mechanism implemented, broader requirement partial.** Unequal strings/polarities for the same entity/slot/signal flag a pair; an explicit contradicting relation marks a slot conflicting. No monetary normalization, amount basis/currency semantics, temporal supersession, party-identity resolution, source hierarchy or amendment ledger. Unreviewed contradictions are not auto-resolved. |
| 18 | Rejected/misaligned candidates remain visible | [A8], [A15]; `atoms`, `failures`, `discoveries` in [C1] | **Reference implemented.** Rejections/review-only items remain in the report/raw checkpoints rather than being silently promoted. This does not mean every UI screen exposes every discovery or alignment failure. |
| 19 | Coverage matrix and high-impact issue-family repair | [A16]; repair loop and `project_to_kernel` in [C1] | **Partial.** Expected slots/sources, attempt failures, bounded uncovered-slot repair and Kernel blockers exist. Repair sends whole selected sources for a union of uncovered slots. No importance-ranked matrix, per-gap provenance, targeted snippet batches or repair of entity-boundary ambiguity. |
| 20 | Claim states supported/conflicting/missing/unverified/not-applicable | [C1], [C5] | **Partial by design.** Extracted slots only become conflicting/unverified/missing and always require human review. No authorized policy path computes supported/not-applicable, or applies a reviewer disposition to authoritative support/coverage. Keeping these unresolved is safer than fabricating completion. |
| 21 | Dependency/relationship graph proposals | [A17]; `_discover` in [C1] | **Partial proposal storage.** Quote-backed edge dictionaries exist. No durable typed graph, endpoint-integrity gate, dependency analysis, isolation or causal adjudication. Heuristic dependency must never become proven causation. |
| 22 | Parse/split/reconcile large documents and formats | [A18]; [C2], [C3], [C8] | **Partial.** Bounded text/PDF/XML/MIME normalization is real. No OCR, images, DOCX, spreadsheets/cell anchors, WhatsApp intake or large-document split/reconciliation strategy. Unsupported/incomplete required sources fail closed; PDF page text is not an invented bounding box. |
| 23 | Durable provider calls and replay | [A19]; `_call` in [C1], [C9] | **Reference implemented with tests.** Dispatch/receive/checkpoint CAS, valid response envelope retention, no blind unknown retry, scoped PG journal. Malformed HTTP/provider envelopes are rejected; there is no general raw-HTTP-byte archive. Persisted valid replies replay before extraction JSON validation. |
| 24 | Cache/authority snapshot and restart | [A20]; request/intake manifests, [C9] | **Adapted without task-local authority dependence.** Source/parser/prompt/model/vocabulary/config versions are bound and checked. No independent cross-run adaptive-QAE cache; same-run checkpoints provide replay. Restart behavior has real disposable PG tests. |
| 25 | Leased background work and safe unknown outcomes | [C9], [C13], [C14], [T4] | **Reference implemented beyond basic extraction.** Heartbeats, total deadline, fencing, cancellation, bounded retries, immutable results/events and process recovery. No deployed supervisor, global scheduler, production service delegation or external-effects outbox. |
| 26 | Paid HITL freeze and approved assessment boundary | [A1], [A2], [A7]; [C5], [C6] | **Major downstream gap.** CaseProof has frozen recommendations, immutable corrections, stale guards and atomic disposable audit/receipt. It does not have genuine authenticated human attestation or approved decisions; installed request permissions cannot grant approval. |
| 27 | Deterministic domain reasoning | [A14], [A21]; finance comparison and [C10] | **Partial vertical integration; classifier port intentionally excluded.** Native UBL totals can use the existing Decimal comparator. General extracted text atoms do not supply a fully typed tax/currency/line/delivery/credit/amendment model. Construction has a vocabulary/test consumer, not a construction rules/dossier product. |
| 28 | Reproducible source-linked dossier | [C11], [T3] | **Reference implemented for draft ZIP/HTML.** Original bytes, representations, source citations, review trail, manifest and offline consistency verifier. No approved dossier or generated resolution PDF; no qualified timestamp/signature/authenticity claim. |
| 29 | Corpus and comparative/live evaluation | [C12], [T1], [T2], [T3], [T4] | **Incomplete exit gate.** Four labeled synthetic document fixtures plus scripted adversarial/unit/integration tests. Opt-in live evaluator callable exists, requires durable journal/config; module CLI invokes scripted mode only. No live Requesty quality/cost baseline, statistical corpus, multilingual/OCR benchmark, inter-reviewer workload measure or topology comparison was executed. |
| 30 | Runtime observability and source security | [C1], [C8], [C9], [C12] | **Partial.** Optional token/cost fields, step failures, bounded parser, source byte checks and safe operational reasons exist. No measured provider drift, production scanning/quarantine/sandbox/storage lifecycle, real processor-policy verification or complete customer telemetry/release monitoring. |

## Original milestone exit gates

| Milestone | Audit result against the supplied roadmap |
|---|---|
| M0 baseline/evaluation | **Partial.** This audit pins source SHAs; CI and synthetic fixtures exist. Actual live-provider baseline and deployed AZComply flags are not measured/verified. |
| M1 ingestion/representations | **Partial.** Supported-format originals/representations resolve and survive disposable restart. Production private Storage, scanning, OCR and sheet locators do not meet the full gate. |
| M2 global scout/entities | **Partial.** Discovery and attribution constraints exist; no working boundary proposal/confirmation graph workflow. |
| M3 anchored QAE/execution | **Core reference demonstrated.** Exact source checks, failures, checkpoint replay and budgets are tested. Full typed factual fields, meaningful dynamic targeting, representative documents and live performance remain gaps. |
| M4 registry/promotion | **Partial.** Conservative lexical policies and disabled approval do not satisfy the full typed registry/decision contract. |
| M5 reconciliation/coverage | **Partial.** Visible conflicts and incomplete-source blockers; no comprehensive semantic/temporal/monetary reconciliation or persisted accepted link/coverage graph. |
| M6 reviewer/durable decision | **Recommendations only.** No real authorized consequential decision exit. |
| M7 two verticals/dossier | **Partial.** Finance reference + draft pack; construction vocabulary is not the required complete construction scenario. |
| M8 advanced/hardening | **Not demonstrated.** Optional four-pass exists; no measured comparative improvement, OCR/multilingual/security/operational release evidence. |

No percentage or blanket “done” status is assigned: these milestones have different authority boundaries and exit criteria. A passing test count cannot substitute for an unimplemented gate.

## Executed evidence and probes

- Re-fetched actual main CI at the pinned CaseProof SHA: [architecture/browser](https://github.com/haytamAroui/caseproof/actions/runs/40069404749/job/120799386418), [disposable PG](https://github.com/haytamAroui/caseproof/actions/runs/40069404749/job/120799386597), [migration guard](https://github.com/haytamAroui/caseproof/actions/runs/40069404737/job/120799386474): all success. Earlier recorded execution: 1,105 pytest, 20 worker PG and 8 browser checks, alongside existing DB integrations.
- Re-ran the five affected local suites: `uv run pytest -q tests/test_evidence_intelligence.py tests/test_document_intelligence.py tests/test_worker_runtime.py tests/test_requesty_extraction.py tests/test_review_resolution_pack.py`: **209 passed, exit 0**, 2 warnings (Starlette/httpx deprecation; intentionally duplicated ZIP negative fixture). All 137 Python files under application/apps/domains/infrastructure/evals/scripts/tests in the execution worktree were byte-compared against the pinned main tree with zero differences; audit docs are on a new worktree at the exact main SHA.
- Three ad-hoc, repository-owned synthetic probes ran locally, exit 0, without a provider network call:

| Probe | Observed result | Interpretation |
|---|---|---|
| Same exact anchor/value/polarity, opposing supports/contradicts proposals | Both retained; slot conflicting; approved false | **Safety behavior confirmed.** Candidate ID includes relation. Do not claim an interpretation-loss defect here. Pairwise conflict list is empty, but the slot explicitly records conflict. |
| Scout proposes an entity named DISCOVERED | Target still receives only independent boundary E1; no discoveries field | Correctly prevents self-confirmation, but confirms the scout is not currently a dynamic targeting/segmentation planner. |
| Segmented boundary ends at character 28 of a 66-character source | Task sends all 66 characters, including OTHER ENTITY | Source/entity eligibility is checked afterwards; segmented prompt minimization/offset-preserving snippets are not implemented. |

These probes are observations of scripted execution, not model-accuracy tests. No AZComply tests, deployed database, paid provider, feature-flag environment, customer files or production security gates were exercised.

## Rechecking the original AZComply risk notes

The original roadmap contains hypotheses, not an established list of production vulnerabilities. At this pin, `QAE_MIN_VERIFIED_RATIO` still defaults to 0.2; mapper helper verified statuses include fuzzy strong/weak; a raw-label fallback still exists when `validated_signals` is absent; some unregistered validators can append a signal after a review-policy check; extract-route calls still pass strict-boundary false and invoke post-QAE override/enrichment helpers. Their deployed reachability/effect was not executed here. Do not present them as proven production exploits.

Importantly, [A20] **does** contain versioned snapshot and restore functions for the authority ContextVar. Saying “authority is task-local, therefore definitely lost on restart” would be unsupported. Likewise the paid confirmation/assessment routes check frozen facts and hashes; they must not be described as having no durable HITL authority merely because CaseProof's corresponding integration is unfinished.

CaseProof deliberately uses exact spans, keeps unknown signals review-only, keeps coverage and approval false and has no unchecked AI Act/context-to-fact mapping. These are adaptations to retain, not reasons to copy AZComply's defaults.

## Prioritized completion work

One combined **core extraction completion** PR should address EIP-01 through EIP-04 together, with meaningful end-to-end fixtures and one shared runtime. Preserve the existing pure Kernel and Requesty port; do not add Vertex, a second truth store or a general multi-agent framework.

| Priority | Work | Concrete acceptance evidence |
|---|---|---|
| EIP-01 / P0 | Versioned entity proposals, deterministic source alignment, explicit edit/confirm/reject boundary outcomes; typed graph edges | Two invoices/variations with overlapping references stay distinct; every ambiguous proposal remains review-blocked until independently confirmed; edits create revisions; no LLM confirmation. |
| EIP-02 / P0 | Typed signal registry and per-signal validation/eligibility decisions, categories/consumers/reviewer rules | Unknown high-impact signal, negated approval, legal commentary and an allegation never map to an affirmative eligible observation; rejected/review-only decisions remain inspectable. |
| EIP-03 / P0 | Typed subject/event/time/Decimal/currency fields and source-aware reconciliation | Partial payment, currency/basis mismatch, amended PO, credit note and contradictory dates preserve source-linked alternatives without string-based false equivalence or silent resolution. |
| EIP-04 / P0 | Explicit per-entity/slot evidence matrix and bounded context/repair planning | Scout findings can propose work without changing confirmed scope; targeted snippets preserve full-representation offsets; high-value uncovered slots/failed alignment trigger bounded repair; overflow remains a blocker. |
| EIP-05 / P0 exit evidence | Larger labeled FR/NL/EN corpus and real Requesty evaluation | Authorized configured run records grounded fact/attribution/conflict metrics, latency/tokens/cost, missing telemetry and errors honestly; no fabricated target attainment. Retain a holdout corpus and adversarial cases. |
| EIP-06 / separate release gate | Genuine Auth/private Storage/least-privilege DB, accepted evidence graph and action-scoped human decisions | Real reviewer completes private source-to-approved-decision workflow with cross-tenant/revocation/stale/concurrency/audit tests. Approval actions require separately reviewed permissions and attestation; no mock closes this gate. |
| P1, measured | Advanced sentence/pass planning, OCR/sheets, larger documents, richer graph proposals and operational hardening | Enable only after needed formats/customer cases and measured benefit justify complexity; strict runs never silently downgrade. |

Intentional exclusions: EU AI Act SystemFacts/ModuleFacts, legal signal catalogs, AI-component legal classifier, Article 5/Annex III/GPAI/reachability law logic, free questionnaire, paid billing and AZComply's provider-specific clients. Their absence is not a CaseProof extraction parity defect. Adapt engineering patterns and domain-neutral contracts, not the other product's legal schema.

## Pinned source references

AZComply references below can require repository access. Function names above identify relevant entrypoints; links remain fixed to the inspected revision.

[A1]: https://github.com/haytamAroui/azcomply/blob/4249ea640568b5a95e0f57758e3c9479c7b40267/conform-ai/api/routes/assess_extract.py
[A2]: https://github.com/haytamAroui/azcomply/blob/4249ea640568b5a95e0f57758e3c9479c7b40267/conform-ai/api/routes/assess_paid.py
[A3]: https://github.com/haytamAroui/azcomply/blob/4249ea640568b5a95e0f57758e3c9479c7b40267/conform-ai/extraction/qae_models.py
[A4]: https://github.com/haytamAroui/azcomply/blob/4249ea640568b5a95e0f57758e3c9479c7b40267/conform-ai/extraction/evidence_verifier.py
[A5]: https://github.com/haytamAroui/azcomply/blob/4249ea640568b5a95e0f57758e3c9479c7b40267/conform-ai/extraction/component_segmentation.py
[A6]: https://github.com/haytamAroui/azcomply/blob/4249ea640568b5a95e0f57758e3c9479c7b40267/conform-ai/extraction/component_clarifier.py
[A7]: https://github.com/haytamAroui/azcomply/blob/4249ea640568b5a95e0f57758e3c9479c7b40267/conform-ai/extraction/component_confirmation.py
[A8]: https://github.com/haytamAroui/azcomply/blob/4249ea640568b5a95e0f57758e3c9479c7b40267/conform-ai/extraction/component_alignment_verifier.py
[A9]: https://github.com/haytamAroui/azcomply/blob/4249ea640568b5a95e0f57758e3c9479c7b40267/conform-ai/extraction/global_first_qae_pipeline.py
[A10]: https://github.com/haytamAroui/azcomply/blob/4249ea640568b5a95e0f57758e3c9479c7b40267/conform-ai/extraction/segmented_qae_pipeline.py
[A11]: https://github.com/haytamAroui/azcomply/blob/4249ea640568b5a95e0f57758e3c9479c7b40267/conform-ai/extraction/four_pass_qae.py
[A12]: https://github.com/haytamAroui/azcomply/blob/4249ea640568b5a95e0f57758e3c9479c7b40267/conform-ai/extraction/signal_mapping_registry.py
[A13]: https://github.com/haytamAroui/azcomply/blob/4249ea640568b5a95e0f57758e3c9479c7b40267/conform-ai/extraction/signal_promotion.py
[A14]: https://github.com/haytamAroui/azcomply/blob/4249ea640568b5a95e0f57758e3c9479c7b40267/conform-ai/extraction/evidence_mapper.py
[A15]: https://github.com/haytamAroui/azcomply/blob/4249ea640568b5a95e0f57758e3c9479c7b40267/conform-ai/extraction/component_reconciler.py
[A16]: https://github.com/haytamAroui/azcomply/blob/4249ea640568b5a95e0f57758e3c9479c7b40267/conform-ai/extraction/issue_family_repair_planner.py
[A17]: https://github.com/haytamAroui/azcomply/blob/4249ea640568b5a95e0f57758e3c9479c7b40267/conform-ai/extraction/component_dependency_analyzer.py
[A18]: https://github.com/haytamAroui/azcomply/blob/4249ea640568b5a95e0f57758e3c9479c7b40267/conform-ai/extraction/document_parser.py
[A19]: https://github.com/haytamAroui/azcomply/blob/4249ea640568b5a95e0f57758e3c9479c7b40267/conform-ai/extraction/durable_llm_call.py
[A20]: https://github.com/haytamAroui/azcomply/blob/4249ea640568b5a95e0f57758e3c9479c7b40267/conform-ai/extraction/extraction_authority_context.py
[A21]: https://github.com/haytamAroui/azcomply/blob/4249ea640568b5a95e0f57758e3c9479c7b40267/conform-ai/extraction/component_classifier.py
[C1]: https://github.com/haytamAroui/caseproof/blob/7c27e4ffcb5d512a55f88aca48423adb1d923861/application/extraction/pipeline.py
[C2]: https://github.com/haytamAroui/caseproof/blob/7c27e4ffcb5d512a55f88aca48423adb1d923861/application/documents/intake.py
[C3]: https://github.com/haytamAroui/caseproof/blob/7c27e4ffcb5d512a55f88aca48423adb1d923861/application/documents/contracts.py
[C4]: https://github.com/haytamAroui/caseproof/blob/7c27e4ffcb5d512a55f88aca48423adb1d923861/application/extraction/contracts.py
[C5]: https://github.com/haytamAroui/caseproof/blob/7c27e4ffcb5d512a55f88aca48423adb1d923861/application/review/contracts.py
[C6]: https://github.com/haytamAroui/caseproof/blob/7c27e4ffcb5d512a55f88aca48423adb1d923861/apps/api/review_workbench.py
[C7]: https://github.com/haytamAroui/caseproof/blob/7c27e4ffcb5d512a55f88aca48423adb1d923861/domains/finance/extraction_rules.py
[C8]: https://github.com/haytamAroui/caseproof/blob/7c27e4ffcb5d512a55f88aca48423adb1d923861/infrastructure/parsers/limited.py
[C9]: https://github.com/haytamAroui/caseproof/blob/7c27e4ffcb5d512a55f88aca48423adb1d923861/apps/worker/fenced_journal.py
[C10]: https://github.com/haytamAroui/caseproof/tree/7c27e4ffcb5d512a55f88aca48423adb1d923861/domains/finance
[C11]: https://github.com/haytamAroui/caseproof/blob/7c27e4ffcb5d512a55f88aca48423adb1d923861/application/dossiers/pack.py
[C12]: https://github.com/haytamAroui/caseproof/blob/7c27e4ffcb5d512a55f88aca48423adb1d923861/evals/document_extraction.py
[T1]: https://github.com/haytamAroui/caseproof/blob/7c27e4ffcb5d512a55f88aca48423adb1d923861/tests/test_evidence_intelligence.py
[T2]: https://github.com/haytamAroui/caseproof/blob/7c27e4ffcb5d512a55f88aca48423adb1d923861/tests/test_document_intelligence.py
[T3]: https://github.com/haytamAroui/caseproof/blob/7c27e4ffcb5d512a55f88aca48423adb1d923861/tests/test_review_resolution_pack.py
[T4]: https://github.com/haytamAroui/caseproof/blob/7c27e4ffcb5d512a55f88aca48423adb1d923861/scripts/verify_worker_integration.py

[C13]: https://github.com/haytamAroui/caseproof/blob/7c27e4ffcb5d512a55f88aca48423adb1d923861/infrastructure/execution/postgres_jobs.py
[C14]: https://github.com/haytamAroui/caseproof/blob/7c27e4ffcb5d512a55f88aca48423adb1d923861/application/runtime/worker.py
