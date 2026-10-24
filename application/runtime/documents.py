"""Source-to-review job execution using the existing intake/extraction contracts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from application.documents.intake import CapturedDocument, DocumentIntelligence
from application.extraction.contracts import (
    PROMPT_VERSION,
    SCHEMA_VERSION,
    ExtractionError,
    StepJournal,
    canonical,
    decode,
)
from application.review.contracts import freeze_review
from application.runtime.jobs import JobResult, JobSpec, JobState, Lease


def engine_identity(service: DocumentIntelligence) -> dict[str, str]:
    return {
        "schema": SCHEMA_VERSION,
        "prompt": PROMPT_VERSION,
        "parser": service.parser.identity,
        "provider": service.provider.identity,
        "model": service.provider.model,
        "vocabulary": service.policy.namespace,
        "validator": service.policy.version,
    }


def check_documents(spec: JobSpec, documents: tuple[CapturedDocument, ...]) -> None:
    if type(documents) is not tuple or len(documents) != len(spec.sources):
        raise ExtractionError("job source inventory changed")
    for source, ref in zip(documents, spec.sources, strict=True):
        original = source.source
        if (
            source.source_id,
            original.document_id,
            original.version_id,
            original.sha256_hex,
            original.media_type,
        ) != (ref.source_id, str(ref.document_id), str(ref.version_id), ref.sha256, ref.media_type):
            raise ExtractionError("job source version changed")


@dataclass(frozen=True)
class DocumentJobExecutor:
    """Loader must freshly authorize the actor and read verified Vault bytes each time.

    Both callbacks are server composition. Never deserialize a callback, filesystem
    locator, provider key or arbitrary Python entrypoint from a stored job.
    """

    load_documents: Callable[[JobSpec], tuple[CapturedDocument, ...]]
    journal_factory: Callable[[Lease], StepJournal]
    service_factory: Callable[[StepJournal], DocumentIntelligence]

    def __call__(self, lease: Lease) -> JobResult:
        spec = lease.spec
        journal = self.journal_factory(lease)
        service = self.service_factory(journal)
        if service.journal is not journal or engine_identity(service) != decode(spec.plan_json)["engine"]:
            return JobResult(JobState.BLOCKED, "input_changed")
        documents = self.load_documents(spec)
        check_documents(spec, documents)
        assignments, slots, config = spec.inputs()
        result = service.run(
            scope=spec.scope,
            run_id=spec.run_id,
            documents=documents,
            assignments=assignments,
            slots=slots,
            config=config,
        )
        after = self.load_documents(spec)
        check_documents(spec, after)
        if after != documents:
            return JobResult(JobState.BLOCKED, "input_changed")
        if any(f.get("reason") == "outcome_unknown" for f in result.failures):
            return JobResult(JobState.UNKNOWN, "provider_outcome_unknown")
        if result.status == "blocked" or result.extraction is None:
            return JobResult(
                JobState.BLOCKED,
                "incomplete_evidence",
                canonical(
                    {
                        "schema": "document-job-result-v1",
                        "approved": False,
                        "failures": result.failures,
                        "extraction_complete": False,
                    }
                ),
            )
        snapshot = freeze_review(
            result,
            scope=spec.scope,
            title="Invoice evidence review",
            case_revision=spec.case_revision,
            policy_version=spec.policy_version,
            source_intents={s.source_id: s.intent_id for s in spec.sources},
        )
        return JobResult(
            JobState.SUCCEEDED,
            "review_ready",
            canonical(
                {
                    "schema": "document-job-result-v1",
                    "approved": False,
                    "snapshot_hash": snapshot.snapshot_hash,
                    "snapshot": snapshot.data,
                    "extraction_complete": result.extraction.extraction_complete,
                    "coverage_complete": False,
                    "review_confirmed": False,
                    "decision_approved": False,
                }
            ),
        )
