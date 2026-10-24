"""Execution contracts and untrusted input safety; PG durability tested separately."""

from dataclasses import asdict, replace
from uuid import UUID, uuid4

import pytest

from application.documents.intake import DocumentIntelligence, EntityAssignment
from application.extraction.contracts import (
    ClaimSlot,
    ExtractionConfig,
    ExtractionError,
    OutcomeUnknown,
    canonical,
    decode,
)
from application.extraction.journal import MemoryJournal
from application.runtime.documents import DocumentJobExecutor, check_documents, engine_identity
from application.runtime.jobs import JobResult, JobSpec, JobState, Lease, LeaseLost, RetryLater, SourceRef
from application.runtime.worker import ExtractionWorker
from domains.finance.extraction_rules import FinanceEvidencePolicy
from evals.document_corpus import CASES
from infrastructure.parsers.limited import LimitedDocumentParser
from scripts.extraction_fixtures import SCOPE
from scripts.review_demo_fixture import DemoProvider


def spec():
    c = CASES[0].captured()
    engine = engine_identity(
        DocumentIntelligence(
            LimitedDocumentParser(), DemoProvider(), MemoryJournal(), FinanceEvidencePolicy()
        )
    )
    return JobSpec(
        SCOPE,
        uuid4(),
        uuid4(),
        1,
        "test-v1",
        (SourceRef(c.source_id, uuid4(), uuid4(), uuid4(), c.source.sha256_hex, c.source.media_type),),
        canonical(
            {
                "assignments": [asdict(EntityAssignment("E1", "invoice", c.source_id, confirmed=True))],
                "slots": [asdict(ClaimSlot("E1", "invoice_issued", (c.source_id,)))],
                "config": asdict(ExtractionConfig(repair_passes=0)),
                "engine": engine,
            }
        ),
    )


def documents(s):
    c = CASES[0].captured()
    r = s.sources[0]
    return (
        replace(c, source=replace(c.source, document_id=str(r.document_id), version_id=str(r.version_id))),
    )


def test_job_roundtrip_and_fingerprint_pin_all_inputs():
    s = spec()
    assert JobSpec.restore(canonical(s.payload())) == s
    assert replace(s, actor_id=uuid4()).fingerprint != s.fingerprint
    assert replace(s, case_revision=2).fingerprint != s.fingerprint
    assert replace(s, request_id=uuid4()).run_id != s.run_id
    assert '"content":' not in canonical(s.payload()) and '"token":' not in canonical(s.payload())


@pytest.mark.parametrize(
    "change",
    [
        {"max_attempts": 0},
        {"max_attempts": True},
        {"max_runtime_seconds": 0},
        {"max_runtime_seconds": True},
        {"max_runtime_seconds": 3601},
        {"case_revision": -1},
        {"request_id": UUID(int=0)},
        {"sources": ()},
        {"sources": []},
        {"plan_json": "{}"},
        {"plan_json": '{"api_key":"secret"}'},
    ],
)
def test_job_rejects_unbounded_unknown_or_untyped_inputs(change):
    with pytest.raises(ExtractionError):
        replace(spec(), **change)


@pytest.mark.parametrize("key", ["engine", "assignments", "config", "slots"])
def test_extra_instructions_and_entrypoints_never_deserialize(key):
    s = spec()
    p = decode(s.plan_json)
    if key == "engine":
        p[key]["entrypoint"] = "os.system"
    elif key == "config":
        p[key]["approve"] = True
    else:
        p[key][0]["tenant_id"] = "foreign"
    with pytest.raises(ExtractionError):
        replace(s, plan_json=canonical(p))


def test_source_alias_and_tamper_are_not_accepted():
    s = spec()
    with pytest.raises(ExtractionError):
        replace(s, sources=s.sources * 2)
    with pytest.raises(ExtractionError):
        check_documents(s, (CASES[0].captured(),))
    check_documents(s, documents(s))


@pytest.mark.parametrize("state", [JobState.QUEUED, JobState.RUNNING, JobState.CANCELLED])
def test_worker_cannot_claim_a_nonterminal_state_as_result(state):
    with pytest.raises(ExtractionError):
        JobResult(state, "review_ready")


def test_success_requires_unapproved_bounded_payload():
    with pytest.raises(ExtractionError):
        JobResult(JobState.SUCCEEDED, "review_ready")
    with pytest.raises(ExtractionError):
        JobResult(JobState.SUCCEEDED, "review_ready", canonical({"approved": True}))
    with pytest.raises(ExtractionError):
        JobResult(JobState.BLOCKED, "raw document or exception secret")


def test_document_executor_reuses_existing_source_to_review_without_authority():
    s = spec()
    journal = MemoryJournal()
    executor = DocumentJobExecutor(
        lambda _: documents(s),
        lambda _: journal,
        lambda j: DocumentIntelligence(LimitedDocumentParser(), DemoProvider(), j, FinanceEvidencePolicy()),
    )
    lease = Lease(s, uuid4(), 1, uuid4())
    result = executor(lease)
    data = decode(result.payload_json)
    assert result.state is JobState.SUCCEEDED
    assert data["snapshot"]["locations"] and not data["approved"]
    assert not data["decision_approved"] and not data["coverage_complete"]
    assert executor(lease).payload_json == result.payload_json


@pytest.mark.parametrize("version_key", ["model", "schema", "prompt"])
def test_changed_engine_is_blocked_before_read_or_provider_dispatch(version_key):
    s = spec()
    p = decode(s.plan_json)
    p["engine"][version_key] = "changed"
    s = replace(s, plan_json=canonical(p))

    def forbidden(_):
        pytest.fail("no document read permitted after changed configuration")

    executor = DocumentJobExecutor(
        forbidden,
        lambda _: MemoryJournal(),
        lambda j: DocumentIntelligence(LimitedDocumentParser(), DemoProvider(), j, FinanceEvidencePolicy()),
    )
    assert executor(Lease(s, uuid4(), 1, uuid4())).reason == "input_changed"


class QueueStub:
    """Tests worker control flow only; makes no durability or clock claim."""

    def __init__(self, lease):
        self.lease, self.finished = lease, []

    def claim(self, *args):
        return self.lease

    def finish(self, lease, result):
        self.finished.append(result)
        return {"state": result.state.value, "approved": False}

    def heartbeat(self, *args):
        pass


@pytest.mark.parametrize(
    "error,target",
    [
        (OutcomeUnknown("secret"), JobState.UNKNOWN),
        (RetryLater("transient"), JobState.RETRY),
        (ExtractionError("untrusted source"), JobState.BLOCKED),
        (RuntimeError("secret"), JobState.UNKNOWN),
    ],
)
def test_worker_reports_safe_failure_codes_without_raw_errors(error, target):
    s = spec()
    q = QueueStub(Lease(s, uuid4(), 1, uuid4()))

    def execute(_):
        raise error

    assert ExtractionWorker(q, execute).run_once(s.scope, uuid4())["state"] == target
    assert "secret" not in q.finished[0].reason


def test_lost_lease_never_writes_an_outcome_and_idle_worker_does_nothing():
    s = spec()
    q = QueueStub(Lease(s, uuid4(), 1, uuid4()))

    def execute(_):
        raise LeaseLost("stale worker")

    with pytest.raises(LeaseLost):
        ExtractionWorker(q, execute).run_once(s.scope, uuid4())
    assert q.finished == []
    assert ExtractionWorker(QueueStub(None), execute).run_once(s.scope, uuid4()) is None
