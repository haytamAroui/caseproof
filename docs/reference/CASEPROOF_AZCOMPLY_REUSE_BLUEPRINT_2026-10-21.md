# CaseProof — AZComply architecture reuse reference

**Summary edition** derived from the prior CaseProof–AZComply reuse blueprint (2026-10-21). The full research document remains in the previously supplied archive. This file is not a claim of finished reusable-package extraction.

## Product boundary
CaseProof prepares traceable factual evidence dossiers for disputed commercial invoices. It does not automatically litigate, establish legal truth or decide procedural eligibility.

## Independently deployed systems
- AZComply remains authoritative for its EU AI Act workflows.
- CaseProof gets dedicated repository, data store, worker, object storage, routes and billing.
- Common code is copied and proven through a narrow domain-neutral adapter before deciding whether to publish an independently versioned shared library.

## Verified AZComply candidates
| Path in AZComply | Reuse strategy |
|---|---|
| `conform-ai/extraction/source_normalizer.py` | Adapt: trusted block IDs, character offsets and control-character hygiene |
| `conform-ai/extraction/evidence_verifier.py` | Adapt: exact/fuzzy quote matching; status is citation-only |
| `conform-ai/extraction/qae_models.py` | Redesign: preserve typed candidates, verification and reviewer states; remove `legal_signals`, `module_hint` and AI Act coupling |
| `conform-ai/api/services/evidence_hash_service.py` | Reuse/adapt SHA-256 and provenance records |
| `conform-ai/api/services/evidence_integrity_service.py` | Adapt integrity state transitions and recompute proofs |
| `conform-ai/api/services/fact_provenance_service.py` | Redesign tenant/case scope checks; distinguish source support from legal consequence |
| `conform-ai/api/services/proof_chain_service.py` | Reimplement: transaction ideas useful; compliance-specific closure projections are not portable |
| `conform-ai/api/services/api_job_queue.py` | Adapt durable queue patterns, but rebuild CaseProof workflow states and idempotency keys |
| `conform-ai/api/services/assessment_runtime_service.py` | Adapt hash manifests, cancellation and recovery |
| `conform-ai/report/smart_executive_dossier.py` | Reuse ReportLab know-how; build new evidence dossier template |
| `conform-ai/extraction/segmented_qae_pipeline.py` | Reuse segmentation architecture only after removing domain-specific passes |

## Do not copy
No EU AI Act compliance classifications, risk tiers, prohibited-practice logic, SystemFacts, automatic conservative risk interpretation, provider-specific credentials or live database tables.

## Extraction contract
`CandidateAssertion = {statement, source_document_version_id, source_block_id, verbatim_quote, entity_candidates, claimed_dates, prompt_version, model_version}`.
Trusted code resolves offsets. Semantic reviewers maintain separate states for supported, contradicted, insufficient and indeterminate.

## Reuse acceptance gates
1. Pin AZComply source revision and map imports.
2. Review IP and licenses, LLM/provider data agreements and regional routing.
3. Convert domain-specific Pydantic types into domain-neutral values.
4. Build two-way regression fixtures and prevent AZComply behavior changes.
5. Run proprietary/sensitive data leak and tenant-isolation tests.
6. Package only after two proven stable consumers; avoid forced shared runtime deployment.
