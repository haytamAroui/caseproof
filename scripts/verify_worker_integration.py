"""Actual PG17 lease/CAS/restart tests, private synthetic bytes, scripted provider.

Run after EI-001..003 integrations. Never installs a production migration.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from uuid import UUID, uuid4

from application.documents.intake import DocumentIntelligence, EntityAssignment
from application.dossiers.pack import build_pack, verify_pack
from application.extraction.contracts import (
    ClaimSlot,
    ExtractionConfig,
    ExtractionError,
    Scope,
    StepState,
    canonical,
    decode,
    digest,
)
from application.review.contracts import ReviewSnapshot
from application.runtime.documents import DocumentJobExecutor, engine_identity
from application.runtime.jobs import JobResult, JobState, LeaseLost
from application.runtime.worker import ExtractionWorker
from apps.api.access_control import CaseAction
from apps.api.disposable_review_repository import DisposableReviewRepository
from apps.api.extraction_scheduler import AuthenticatedExtractionScheduler
from apps.worker.fenced_journal import FencedExtractionJournal
from apps.worker.vault_documents import VaultJobDocuments
from domains.finance.extraction_rules import FinanceEvidencePolicy
from evals.document_corpus import CASES
from infrastructure.execution.postgres_jobs import DisposableJobQueue
from infrastructure.parsers.limited import LimitedDocumentParser
from scripts.verify_document_intake_integration import Catalog, CorpusProvider, provision
from scripts.verify_review_integration import context
from scripts.verify_vault_integration import Fixture, VaultScope, connect, coordinator, seed

SQL = Path(__file__).resolve().parents[1] / "db/proposals/EI-004_disposable_worker.sql"


def policy(c):
    with connect() as conn:
        return conn.execute(
            "select effective_policy_version from caseproof.cases where org_id=%s and id=%s",
            (c.org_id, c.case_id),
        ).fetchone()[0]


def service(journal, provider=None):
    return DocumentIntelligence(
        LimitedDocumentParser(), provider or CorpusProvider(), journal, FinanceEvidencePolicy()
    )


def scheduler(f, queue):
    return AuthenticatedExtractionScheduler(
        context(f), Catalog((f,), CASES[:1]), queue, policy, lambda: engine_identity(service(None))
    )


def setup(root, queue=None):
    f = provision(root)
    with connect() as conn:
        conn.execute(
            "update caseproof.organization_members set actions=array['case:read','evidence:read','finding:write','coverage:read','review:request'] where org_id=%s and user_id=%s",
            (f.scope.org_id, f.actor),
        )
    q = queue or DisposableJobQueue(connect)
    identity = uuid4()
    result = scheduler(f, q).submit(
        bearer="synthetic-fixture-only",
        case_id=str(f.scope.case_id),
        request_id=identity,
        assignments=(EntityAssignment("E1", "invoice", "invoice", confirmed=True),),
        slots=(ClaimSlot("E1", "invoice_issued", ("invoice",)),),
        config=ExtractionConfig(repair_passes=0),
    )
    assert result["state"] == "queued"
    scope = Scope(f.scope.org_id, f.scope.case_id)
    return f, q, scope, identity


def executor(root, f, q, provider=None):
    def catalog(spec):
        c = context(f).authorize("synthetic-fixture-only", str(spec.scope.case_id), CaseAction.READ_EVIDENCE)
        return Catalog((f,), CASES[:1]).list_sources(c)

    loader = VaultJobDocuments(q, catalog, lambda _: coordinator(root, f))
    return DocumentJobExecutor(
        loader, lambda lease: FencedExtractionJournal(q, lease), lambda j: service(j, provider)
    )


def expire(q, spec):
    with connect() as conn:
        conn.execute(
            "update caseproof._worker_jobs set lease_until=clock_timestamp()-interval '1 second' where org_id=%s and case_id=%s and request_id=%s",
            q._keys(spec),
        )


def ready(q, spec):
    with connect() as conn:
        conn.execute(
            "update caseproof._worker_jobs set available_at=clock_timestamp()-interval '1 second' where org_id=%s and case_id=%s and request_id=%s",
            q._keys(spec),
        )


def rows(q, spec):
    with connect() as conn:
        return conn.execute(
            "select revision,state,reason from caseproof._worker_events where org_id=%s and case_id=%s and request_id=%s order by revision",
            q._keys(spec),
        ).fetchall()


class WorkerIntegration(unittest.TestCase):
    def test_real_queued_sources_to_review_and_offline_pack(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            f, q, scope, identity = setup(root)
            provider = CorpusProvider()
            run = executor(root, f, q, provider)
            result = ExtractionWorker(q, run).run_once(scope, uuid4())
            self.assertEqual(result["state"], "succeeded")
            self.assertEqual(len(provider.calls), 1)
            self.assertFalse(result["approved"])
            payload = decode(result["result_json"])
            snapshot = ReviewSnapshot(scope, payload["snapshot_hash"], canonical(payload["snapshot"]))
            repo = DisposableReviewRepository(connect)
            repo.publish(snapshot, f.actor)
            # Rehydrate using persisted normalization; do not call inference to export.

            from application.documents.contracts import restore

            catalog = Catalog((f,), CASES[:1]).list_sources(
                context(f).authorize("synthetic-fixture-only", str(scope.case_id), CaseAction.READ_EVIDENCE)
            )
            spec_run = "job:" + str(identity)
            with connect() as conn:
                saved = conn.execute(
                    "select payload,created_at from caseproof._ei_steps where org_id=%s and case_id=%s and run_id=%s and step_id like 'normalize:%%'",
                    (scope.org_id, scope.case_id, spec_run),
                ).fetchone()
            parsed = restore("invoice", catalog[0].original, decode(saved[0])["artifact"], saved[1])
            packed, checkpoint = build_pack(snapshot, (parsed,), repo.state(scope, f.actor))
            self.assertGreater(verify_pack(packed, expected_manifest=checkpoint)["resolved_citations"], 0)
            self.assertIsNone(ExtractionWorker(q, run).run_once(scope, uuid4()))
            self.assertEqual(
                [r[1] for r in rows(q, replace_snapshot_spec(q, scope, identity))],
                ["queued", "running", "succeeded"],
            )

    def test_enqueue_replay_and_request_fingerprint_conflict(self):
        with TemporaryDirectory() as temp:
            f, q, scope, identity = setup(Path(temp))
            spec = replace_snapshot_spec(q, scope, identity)
            self.assertEqual(q.enqueue(spec)["revision"], 1)
            with self.assertRaises(ExtractionError):
                q.enqueue(replace(spec, max_attempts=2))
            self.assertEqual(len(rows(q, spec)), 1)

    def test_two_connections_claim_one_lease_and_skip_locked_job(self):
        with TemporaryDirectory() as temp:
            f, q, scope, identity = setup(Path(temp))
            barrier = Barrier(2)

            def claim(_):
                barrier.wait()
                return q.claim(scope, uuid4(), 30)

            with ThreadPoolExecutor(max_workers=2) as pool:
                leases = list(pool.map(claim, range(2)))
            self.assertEqual(sum(x is not None for x in leases), 1)
            first = next(x for x in leases if x is not None)
            second_spec = replace(first.spec, request_id=uuid4())
            q.enqueue(second_spec)
            with connect() as conn:
                conn.execute(
                    "select request_id from caseproof._worker_jobs where org_id=%s and case_id=%s and request_id=%s for update",
                    q._keys(first.spec),
                )
                second = q.claim(scope, uuid4(), 30)
                self.assertEqual(second.spec.request_id, second_spec.request_id)

    def test_expired_pre_dispatch_lease_recovers_and_fences_old_journal(self):
        with TemporaryDirectory() as temp:
            f, q, scope, identity = setup(Path(temp))
            old = q.claim(scope, uuid4(), 30)
            journal = FencedExtractionJournal(q, old)
            journal.reserve(scope, old.spec.run_id, "prepared", digest({"input": 1}))
            expire(q, old.spec)
            new = q.claim(scope, uuid4(), 30)
            self.assertEqual(new.attempt, 2)
            with self.assertRaises(LeaseLost):
                journal.transition(
                    scope, old.spec.run_id, "prepared", StepState.PREPARED, StepState.COMPLETED, "{}"
                )
            with self.assertRaises(LeaseLost):
                q.finish(old, JobResult(JobState.UNKNOWN, "execution_unknown"))
            q.heartbeat(new, 30)

    def test_expired_dispatch_is_unknown_without_a_second_provider_call(self):
        with TemporaryDirectory() as temp:
            f, q, scope, identity = setup(Path(temp))
            lease = q.claim(scope, uuid4(), 30)
            journal = FencedExtractionJournal(q, lease)
            journal.reserve(scope, lease.spec.run_id + ":extract", "global", digest({"input": 1}))
            journal.transition(
                scope, lease.spec.run_id + ":extract", "global", StepState.PREPARED, StepState.DISPATCHED
            )
            expire(q, lease.spec)
            self.assertIsNone(q.claim(scope, uuid4(), 30))
            state = q.read(scope, identity, f.actor)
            self.assertEqual((state["state"], state["attempt"]), ("outcome_unknown", 1))
            self.assertIsNone(q.claim(scope, uuid4(), 30))
            with self.assertRaises(LeaseLost):
                q.heartbeat(lease, 30)

    def test_completed_checkpoints_replay_after_separate_process_restart(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            f, q, scope, identity = setup(root)
            lease = q.claim(scope, uuid4(), 30)
            provider = CorpusProvider()
            result = executor(root, f, q, provider)(lease)  # crash before durable job acknowledgement
            self.assertEqual(len(provider.calls), 1)
            expire(q, lease.spec)
            (root / "worker-restart.json").write_text(
                json.dumps(
                    {
                        "org": str(scope.org_id),
                        "case": str(scope.case_id),
                        "actor": str(f.actor),
                        "version": str(f.version),
                        "intent": str(f.intent),
                    }
                )
            )
            child = subprocess.run(
                [sys.executable, "-m", "scripts.verify_worker_integration", "--recover", str(root)],
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
            recovered = json.loads(child.stdout)
            self.assertEqual(
                recovered,
                {
                    "state": "succeeded",
                    "attempt": 2,
                    "provider_calls": 0,
                    "result_hash": digest(decode(result.payload_json)),
                },
            )

    def test_cancel_and_running_dispatch_cancel_fence_all_workers(self):
        with TemporaryDirectory() as temp:
            f, q, scope, identity = setup(Path(temp))
            lease = q.claim(scope, uuid4(), 30)
            self.assertEqual(q.cancel(scope, identity, f.actor)["state"], "cancelled")
            self.assertEqual(q.cancel(scope, identity, f.actor)["state"], "cancelled")
            with self.assertRaises(LeaseLost):
                FencedExtractionJournal(q, lease).reserve(
                    scope, lease.spec.run_id, "cannot_dispatch", digest({})
                )
            s = replace(lease.spec, request_id=uuid4())
            q.enqueue(s)
            lease = q.claim(scope, uuid4(), 30)
            journal = FencedExtractionJournal(q, lease)
            journal.reserve(scope, s.run_id + ":extract", "global", digest({}))
            journal.transition(
                scope, s.run_id + ":extract", "global", StepState.PREPARED, StepState.DISPATCHED
            )
            self.assertEqual(q.cancel(scope, s.request_id, f.actor)["state"], "outcome_unknown")

    def test_retry_backoff_budget_and_unknown_step_veto(self):
        with TemporaryDirectory() as temp:
            f, q, scope, identity = setup(Path(temp))
            for attempt in range(1, 4):
                lease = q.claim(scope, uuid4(), 30)
                state = q.finish(lease, JobResult(JobState.RETRY, "preflight_retry"))
                self.assertEqual(state["state"], "failed" if attempt == 3 else "retry_wait")
                if attempt < 3:
                    self.assertIsNone(q.claim(scope, uuid4(), 30))
                    ready(q, lease.spec)
            s = replace(lease.spec, request_id=uuid4())
            q.enqueue(s)
            lease = q.claim(scope, uuid4(), 30)
            j = FencedExtractionJournal(q, lease)
            j.reserve(scope, s.run_id + ":extract", "global", digest({}))
            j.transition(scope, s.run_id + ":extract", "global", StepState.PREPARED, StepState.DISPATCHED)
            self.assertEqual(
                q.finish(lease, JobResult(JobState.RETRY, "preflight_retry"))["state"], "outcome_unknown"
            )

    def test_event_outage_rolls_back_claim_heartbeat_finish_and_cancel(self):
        class Broken(DisposableJobQueue):
            def _event(self, *args):
                super()._event(*args)
                raise RuntimeError("synthetic event outage")

        with TemporaryDirectory() as temp:
            f, q, scope, identity = setup(Path(temp))
            broken = Broken(connect)
            with self.assertRaises(RuntimeError):
                broken.claim(scope, uuid4(), 30)
            self.assertEqual(q.read(scope, identity, f.actor)["state"], "queued")
            lease = q.claim(scope, uuid4(), 30)
            for action in [
                lambda: broken.heartbeat(lease, 30),
                lambda: broken.finish(lease, JobResult(JobState.UNKNOWN, "execution_unknown")),
                lambda: broken.cancel(scope, identity, f.actor),
            ]:
                with self.assertRaises(RuntimeError):
                    action()
                self.assertEqual(q.read(scope, identity, f.actor)["revision"], 2)
            self.assertEqual(len(rows(q, lease.spec)), 2)

    def test_lost_commit_ack_recovers_exact_result_receipt(self):
        class LostAck:
            def __init__(self):
                self.conn = connect()

            def __enter__(self):
                return self.conn.__enter__()

            def __exit__(self, *args):
                result = self.conn.__exit__(*args)
                if args[0] is None:
                    raise ConnectionError("commit acknowledgement lost")
                return result

        with TemporaryDirectory() as temp:
            f, q, scope, identity = setup(Path(temp))
            lease = q.claim(scope, uuid4(), 30)
            result = JobResult(
                JobState.SUCCEEDED, "review_ready", canonical({"approved": False, "synthetic": True})
            )
            with self.assertRaises(ConnectionError):
                DisposableJobQueue(LostAck).finish(lease, result)
            receipt = q.finish(lease, result)
            self.assertEqual(receipt["state"], "succeeded")
            self.assertEqual(len(rows(q, lease.spec)), 3)

    def test_tenant_revocation_and_policy_changes_block_execution(self):
        with TemporaryDirectory() as temp:
            f, q, scope, identity = setup(Path(temp))
            foreign = seed()
            with self.assertRaises(ExtractionError):
                q.read(scope, identity, foreign.actor)
            with connect() as conn:
                conn.execute(
                    "update caseproof.organization_members set active=false where org_id=%s and user_id=%s",
                    (scope.org_id, f.actor),
                )
            self.assertIsNone(q.claim(scope, uuid4(), 30))
            with self.assertRaises(ExtractionError):
                q.read(scope, identity, f.actor)
            with connect() as conn:
                conn.execute(
                    "update caseproof.organization_members set active=true where org_id=%s and user_id=%s",
                    (scope.org_id, f.actor),
                )
            self.assertEqual(q.read(scope, identity, f.actor)["state"], "blocked")
            s = replace(replace_snapshot_spec(q, scope, identity), request_id=uuid4())
            q.enqueue(s)
            with connect() as conn:
                conn.execute(
                    "update caseproof.cases set effective_policy_version='changed' where org_id=%s and id=%s",
                    (scope.org_id, scope.case_id),
                )
            self.assertIsNone(q.claim(scope, uuid4(), 30))
            self.assertEqual(q.read(scope, s.request_id, f.actor)["state"], "blocked")

    def test_changed_or_foreign_source_cannot_enqueue_and_wrong_run_is_fenced(self):
        with TemporaryDirectory() as temp:
            f, q, scope, identity = setup(Path(temp))
            s = replace_snapshot_spec(q, scope, identity)
            for ref in [replace(s.sources[0], sha256="f" * 64), replace(s.sources[0], intent_id=uuid4())]:
                with self.assertRaises(ExtractionError):
                    q.enqueue(replace(s, request_id=uuid4(), sources=(ref,)))
            lease = q.claim(scope, uuid4(), 30)
            with self.assertRaises(ExtractionError):
                FencedExtractionJournal(q, lease).reserve(scope, "another-job", "global", digest({}))

    def test_heartbeat_keeps_lease_current_and_result_tampering_is_detected(self):
        with TemporaryDirectory() as temp:
            f, q, scope, identity = setup(Path(temp))
            lease = q.claim(scope, uuid4(), 3)
            q.heartbeat(lease, 30)
            self.assertIsNone(q.claim(scope, uuid4(), 30))
            q.finish(lease, JobResult(JobState.SUCCEEDED, "review_ready", canonical({"approved": False})))
            with connect() as conn:
                conn.execute(
                    "update caseproof._worker_jobs set result_json='{}' where org_id=%s and case_id=%s and request_id=%s",
                    q._keys(lease.spec),
                )
            with self.assertRaises(ExtractionError):
                q.read(scope, identity, f.actor)

    def test_disposable_tables_are_inaccessible_to_client_roles(self):
        with connect() as conn:
            for table in ("_worker_jobs", "_worker_events"):
                for role in ("anon", "authenticated"):
                    self.assertFalse(
                        conn.execute(
                            "select has_table_privilege(%s,%s,'select,insert,update,delete')",
                            (role, "caseproof." + table),
                        ).fetchone()[0]
                    )

    def test_received_reply_survives_crash_before_schema_processing(self):
        class CrashAfterReceive(FencedExtractionJournal):
            def transition(self, scope, run_id, step, previous, target, payload=None):
                result = super().transition(scope, run_id, step, previous, target, payload)
                if target is StepState.RECEIVED:
                    raise SystemExit("synthetic process death after received commit")
                return result

        with TemporaryDirectory() as temp:
            root = Path(temp)
            f, q, scope, identity = setup(root)
            lease = q.claim(scope, uuid4(), 30)
            provider = CorpusProvider()
            run = executor(root, f, q, provider)
            interrupted = replace(run, journal_factory=lambda current: CrashAfterReceive(q, current))
            with self.assertRaises(SystemExit):
                interrupted(lease)
            self.assertEqual(len(provider.calls), 1)
            expire(q, lease.spec)
            next_lease = q.claim(scope, uuid4(), 30)
            replay_provider = CorpusProvider()
            outcome = executor(root, f, q, replay_provider)(next_lease)
            self.assertEqual(q.finish(next_lease, outcome)["state"], "succeeded")
            self.assertEqual(replay_provider.calls, [])

    def test_enqueue_audit_outage_leaves_no_job_and_stale_read_hides_result(self):
        class Broken(DisposableJobQueue):
            def _event(self, *args):
                super()._event(*args)
                raise RuntimeError("synthetic audit outage")

        with TemporaryDirectory() as temp:
            f, q, scope, identity = setup(Path(temp))
            s = replace_snapshot_spec(q, scope, identity)
            uncommitted = replace(s, request_id=uuid4())
            with self.assertRaises(RuntimeError):
                Broken(connect).enqueue(uncommitted)
            with self.assertRaises(ExtractionError):
                q.read(scope, uncommitted.request_id, f.actor)
            lease = q.claim(scope, uuid4(), 30)
            q.finish(lease, JobResult(JobState.SUCCEEDED, "review_ready", canonical({"approved": False})))
            with connect() as conn:
                conn.execute(
                    "update caseproof.cases set case_revision=case_revision+1 where org_id=%s and id=%s",
                    (scope.org_id, scope.case_id),
                )
            state = q.read(scope, identity, f.actor)
            self.assertEqual(state["state"], "succeeded")
            self.assertFalse(state["input_current"])
            self.assertIsNone(state["result_json"])

    def test_revoked_permission_fences_active_worker_and_preserves_dispatch_unknown(self):
        with TemporaryDirectory() as temp:
            f, q, scope, identity = setup(Path(temp))
            lease = q.claim(scope, uuid4(), 30)
            j = FencedExtractionJournal(q, lease)
            j.reserve(scope, lease.spec.run_id + ":extract", "global", digest({}))
            j.transition(
                scope, lease.spec.run_id + ":extract", "global", StepState.PREPARED, StepState.DISPATCHED
            )
            with connect() as conn:
                conn.execute(
                    "update caseproof.organization_members set actions=array['case:read'] where org_id=%s and user_id=%s",
                    (scope.org_id, f.actor),
                )
            with self.assertRaises(ExtractionError):
                q.heartbeat(lease, 30)
            with self.assertRaises(ExtractionError):
                j.transition(
                    scope,
                    lease.spec.run_id + ":extract",
                    "global",
                    StepState.DISPATCHED,
                    StepState.RECEIVED,
                    "{}",
                )
            expire(q, lease.spec)
            self.assertIsNone(q.claim(scope, uuid4(), 30))
            with connect() as conn:
                state = conn.execute(
                    "select state from caseproof._worker_jobs where org_id=%s and case_id=%s and request_id=%s",
                    q._keys(lease.spec),
                ).fetchone()[0]
            self.assertEqual(state, "outcome_unknown")

    def test_foreign_case_cannot_borrow_source_or_job_scope(self):
        with TemporaryDirectory() as temp:
            f, q, scope, identity = setup(Path(temp))
            foreign = seed()
            s = replace_snapshot_spec(q, scope, identity)
            with self.assertRaises(ExtractionError):
                q.enqueue(replace(s, scope=Scope(foreign.scope.org_id, foreign.scope.case_id)))
            with self.assertRaises(ExtractionError):
                q.read(Scope(foreign.scope.org_id, foreign.scope.case_id), identity, f.actor)


def replace_snapshot_spec(q, scope, identity):
    from application.runtime.jobs import JobSpec

    with connect() as conn:
        return JobSpec.restore(
            conn.execute(
                "select spec_json from caseproof._worker_jobs where org_id=%s and case_id=%s and request_id=%s",
                (scope.org_id, scope.case_id, identity),
            ).fetchone()[0]
        )


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--recover":
        root = Path(sys.argv[2])
        p = json.loads((root / "worker-restart.json").read_text())
        f = Fixture(
            VaultScope(UUID(p["org"]), UUID(p["case"])),
            UUID(p["actor"]),
            UUID(p["version"]),
            UUID(p["intent"]),
            CASES[0].captured().source.content,
            CASES[0].media_type,
        )
        q = DisposableJobQueue(connect)
        provider = CorpusProvider()
        result = ExtractionWorker(q, executor(root, f, q, provider)).run_once(
            Scope(f.scope.org_id, f.scope.case_id), uuid4()
        )
        print(
            json.dumps(
                {
                    "state": result["state"],
                    "attempt": result["attempt"],
                    "provider_calls": len(provider.calls),
                    "result_hash": result["result_hash"],
                }
            )
        )
        return
    if len(sys.argv) != 1:
        raise SystemExit("unsupported worker integration arguments")
    with connect() as conn:
        conn.execute(SQL.read_text())
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(WorkerIntegration)
    )
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
