"""M2 disposable PostgreSQL durability, CAS, audit and private-matter tests.

Requires the existing single-use local CI service, S2 Vault and M1 proposal.
No live Supabase, no customer documents, no signed-user claim.
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier, Event
from uuid import UUID, uuid4

from psycopg.errors import ObjectNotInPrerequisiteState

from application.litigation.brief_checks import DraftReference, VersionedBrief
from application.litigation.factual_values import FactAssertion, FactKind, FactRole
from application.litigation.library import EvidencePreview, EvidenceRow
from application.litigation.unified_review import (
    BriefRepresentation,
    ObservationReview,
    ReviewDisposition,
    SourceScope,
    run_unified_check,
)
from apps.api.disposable_litigation_review_ledger import (
    DisposableM2ReviewLedger,
    M2LedgerConflict,
)
from domains.disputes.exhibits import ExhibitEntry, ExhibitPage, ExhibitRegister
from scripts.verify_s2_002_database import _env, _run
from scripts.verify_vault_integration import begin, connect, coordinator, ledger, seed

SQL = Path(__file__).resolve().parents[1] / "db/proposals/PIV-M2_disposable_review_runs.sql"
SOURCE = "De betaling van €12500 was op 22 mei 2026."
BRIEF = "De betaling van €14500 was op 12 mei 2026."


def fixture(root: Path):
    f = seed(data=SOURCE.encode("utf-8"))
    vault = coordinator(root, f)
    begin(vault, f)
    vault.upload(scope=f.scope, intent_id=f.intent, data=f.data)
    # Bind the EvidenceRow source_id to its real preserved document, not a
    # synthetic alias unrelated to the Vault/version ancestry.
    with connect() as conn:
        doc = conn.execute(
            "select document_id from caseproof.document_versions "
            "where org_id=%s and id=%s", (f.scope.org_id, f.version),
        ).fetchone()[0]
        conn.execute(
            "update caseproof.organization_members "
            "set actions=array['case:read','finding:write','review:request']::text[] "
            "where org_id=%s and user_id=%s", (f.scope.org_id, f.actor),
        )
        conn.execute(
            "insert into caseproof._m1_matter_grants("
            "org_id,case_id,user_id,role,permissions) "
            "values(%s,%s,%s,'reviewer',array['case:read','draft:check',"
            "'review:request','exhibit:confirm']::text[])",
            (f.scope.org_id, f.scope.case_id, f.actor),
        )
        register_json = json.dumps({
            "schema": "caseproof-exhibit-register-v1",
            "entries": [{"id": "e1", "label": "Stuk 1",
                         "source": str(doc), "version": str(f.version)}],
        }, sort_keys=True, separators=(",", ":"))
        conn.execute(
            "select * from caseproof._m1_disposable_confirm_exhibits("
            "%s,%s,%s,0,%s::jsonb,%s)",
            (f.actor, f.scope.case_id, uuid4(), register_json,
             sha256(register_json.encode()).hexdigest()),
        ).fetchone()
    preview = EvidencePreview(
        EvidenceRow(str(doc), str(doc), str(f.version), f.digest,
                    "text/plain", "ready", "identity-utf8-v1", "rep-v1", (), ()),
        SOURCE, ((0, len(SOURCE), "identity_utf8", None),),
    )
    register = ExhibitRegister(1, (
        ExhibitEntry("e1", "Stuk 1",
                     (ExhibitPage(str(doc), str(f.version), printed_page=1),),
                     confirmed=True),
    ))
    assertions = (
        FactAssertion("money", "ref-1", BRIEF, 0, len(BRIEF),
                      FactKind.MONEY, FactRole.PAYMENT, "nl", "nl"),
        FactAssertion("date", "ref-1", BRIEF, 0, len(BRIEF),
                      FactKind.DATE, FactRole.PAYMENT, "nl", "nl"),
    )
    brief = VersionedBrief(str(f.scope.case_id), "draft-v1",
                           sha256(BRIEF.encode()).hexdigest(),
                           (DraftReference("ref-1", "Stuk 1", None, None),))
    representation = BriefRepresentation(
        brief, BRIEF, sha256(BRIEF.encode()).hexdigest(), "fixture-utf8", assertions,
    )
    run = run_unified_check(
        representation=representation, register=register, previews=(preview,),
        source_scope=SourceScope(((str(doc), str(f.version)),)),
        authorized_case_id=str(f.scope.case_id), authorized_register_revision=1,
    )
    assert len(run.factual_observations) == 2
    return f, run


def decision(actor: UUID, target: str = "fact:money") -> ObservationReview:
    return ObservationReview(
        target, str(actor), ReviewDisposition.NEEDS_INFORMATION,
        "Requires source-level practitioner assessment",
    )


def counts(f) -> tuple[int, int, int]:
    with connect() as conn:
        return tuple(int(conn.execute(
            "select count(*) from caseproof." + table +
            " where org_id=%s and case_id=%s",
            (f.scope.org_id, f.scope.case_id),
        ).fetchone()[0]) for table in (
            "_m2_review_events", "_m2_review_receipts", "audit_events",
        ))


class LedgerTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory(prefix="caseproof-m2-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.f, self.run = fixture(self.root)
        self.repo = DisposableM2ReviewLedger(connect)
        self.assertTrue(self.repo.publish(
            org_id=self.f.scope.org_id, actor_id=self.f.actor, run=self.run,
        ))

    def save(self, *, request=None, expected=0, target="fact:money"):
        return self.repo.record(
            org_id=self.f.scope.org_id, actor_id=self.f.actor, run=self.run,
            request_id=request or uuid4(), expected_revision=expected,
            decision=decision(self.f.actor, target),
        )

    def test_publish_is_idempotent_and_reopen_with_new_repository(self):
        self.assertFalse(self.repo.publish(
            org_id=self.f.scope.org_id, actor_id=self.f.actor, run=self.run,
        ))
        state, replay = self.save()
        self.assertFalse(replay)
        self.assertEqual(state.revision, 1)
        restarted = DisposableM2ReviewLedger(connect)
        state2 = restarted.state(
            org_id=self.f.scope.org_id, actor_id=self.f.actor, run=self.run,
        )
        self.assertEqual(state2.packet, state.packet)
        self.assertFalse(state2.customer_release_authorized)
        code = subprocess.run([
            sys.executable, "-m", "scripts.verify_m2_disposable_runs", "--recover",
            str(self.f.scope.org_id), str(self.f.scope.case_id),
            self.run.snapshot_hash,
        ], capture_output=True, text=True, timeout=20, check=False)
        self.assertEqual((code.returncode, code.stdout.strip()),
                         (0, "M2_FRESH_PROCESS_RECORD_PASSED"), msg=code.stderr[:1000])

    def test_same_request_replay_and_conflicting_key(self):
        request = uuid4()
        first, replay = self.save(request=request)
        second, replay2 = self.save(request=request)
        self.assertFalse(replay)
        self.assertTrue(replay2)
        self.assertEqual(first, second)
        with self.assertRaises(M2LedgerConflict):
            self.save(request=request, target="fact:date")
        self.assertEqual(counts(self.f)[0:2], (1, 1))

    def test_stale_and_two_writer_cas_only_one_commit(self):
        barrier = Barrier(2)

        def race(target):
            barrier.wait()
            try:
                self.save(target=target)
                return "saved"
            except (M2LedgerConflict, ValueError):
                return "conflict"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(race, ("fact:money", "fact:date")))
        self.assertEqual(sorted(results), ["conflict", "saved"])
        with self.assertRaises(ValueError):
            self.save(expected=0)
        self.assertEqual(counts(self.f)[0:2], (1, 1))

    def test_foreign_restricted_grant_revocation_and_case_change(self):
        other = seed()
        with self.assertRaises(M2LedgerConflict):
            self.repo.state(org_id=self.f.scope.org_id, actor_id=other.actor,
                            run=self.run)
        with connect() as conn:
            conn.execute(
                "update caseproof._m1_matter_grants set active=false "
                "where case_id=%s and user_id=%s",
                (self.f.scope.case_id, self.f.actor),
            )
        with self.assertRaises(M2LedgerConflict):
            self.save()
        with connect() as conn:
            conn.execute(
                "update caseproof._m1_matter_grants set active=true "
                "where case_id=%s and user_id=%s",
                (self.f.scope.case_id, self.f.actor),
            )
            conn.execute(
                "update caseproof.cases set case_revision=case_revision+1 "
                "where id=%s", (self.f.scope.case_id,),
            )
        with self.assertRaises(M2LedgerConflict):
            self.save()
        self.assertEqual(counts(self.f)[0:2], (0, 0))

    def test_organization_finding_permission_revocation_blocks_publish(self):
        # A private matter draft:check grant alone is not sufficient to persist
        # a check: ADR-0017 also requires current organization finding:write.
        with connect() as conn:
            conn.execute(
                "update caseproof.organization_members "
                "set actions=array['case:read','review:request']::text[] "
                "where org_id=%s and user_id=%s",
                (self.f.scope.org_id, self.f.actor),
            )
        with self.assertRaises(M2LedgerConflict):
            self.repo.publish(
                org_id=self.f.scope.org_id, actor_id=self.f.actor, run=self.run,
            )
        with connect() as conn:
            conn.execute(
                "update caseproof.organization_members "
                "set actions=array['case:read','review:request','finding:write']::text[] "
                "where org_id=%s and user_id=%s",
                (self.f.scope.org_id, self.f.actor),
            )
        self.assertFalse(self.repo.publish(
            org_id=self.f.scope.org_id, actor_id=self.f.actor, run=self.run,
        ))

    def test_concurrent_state_reader_observes_consistent_review_history(self):
        # The reader pauses just after its SELECT of the review head.
        # The writer must not append an event until the reader finishes
        # reconstructing the revision-limited history in one transaction.
        entered, resume = Event(), Event()

        class PausingReader(DisposableM2ReviewLedger):
            @staticmethod
            def _events(conn, keys, run, expected_revision, expected_head):
                entered.set()
                if not resume.wait(3):
                    raise AssertionError("reader did not resume")
                return DisposableM2ReviewLedger._events(
                    conn, keys, run, expected_revision, expected_head,
                )

        writer_started = Event()

        def write():
            writer_started.set()
            return self.save()

        def read():
            return PausingReader(connect).state(
                org_id=self.f.scope.org_id, actor_id=self.f.actor, run=self.run,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            reader_future = pool.submit(read)
            try:
                self.assertTrue(entered.wait(3), "reader did not lock head")
                writer_future = pool.submit(write)
                self.assertTrue(writer_started.wait(3))
                self.assertFalse(writer_future.done())
            finally:
                resume.set()
            read_state = reader_future.result(timeout=5)
            write_state, replay = writer_future.result(timeout=5)
        self.assertEqual(read_state.revision, 0)
        self.assertEqual(write_state.revision, 1)
        self.assertFalse(replay)

    def test_source_destruction_and_run_mutation_withheld(self):
        with self.assertRaises(M2LedgerConflict):
            self.repo.publish(
                org_id=self.f.scope.org_id, actor_id=self.f.actor,
                run=replace(self.run, brief_version_id="substituted"),
            )
        vault_ledger = ledger(self.f)
        record = vault_ledger.get_scoped(self.f.scope, self.f.intent)
        assert record is not None
        vault_ledger.mark_unavailable(record, "missing")
        with self.assertRaises(M2LedgerConflict):
            self.save()

    def test_audit_failure_rolls_back_all_ledger_mutations(self):
        class FailedAudit(DisposableM2ReviewLedger):
            def _audit(self, *args):
                super()._audit(*args)
                raise RuntimeError("injected audit rollback")

        before = counts(self.f)
        with self.assertRaises(RuntimeError):
            FailedAudit(connect).record(
                org_id=self.f.scope.org_id, actor_id=self.f.actor,
                run=self.run, request_id=uuid4(), expected_revision=0,
                decision=decision(self.f.actor),
            )
        self.assertEqual(self.repo.state(
            org_id=self.f.scope.org_id, actor_id=self.f.actor,
            run=self.run,
        ).revision, 0)
        # Failed audit and review must roll back to exactly the baseline.
        self.assertEqual(counts(self.f), before)

    def test_no_client_role_access_or_mutation_of_history(self):
        # Table RLS has no policy; no API role can inspect its existence.
        env = _env()
        sql = ("set role authenticated; "
               "select * from caseproof._m2_check_runs;")
        _run(sql, env, should_pass=False)
        with self.assertRaises(ObjectNotInPrerequisiteState):
            with connect() as conn:
                conn.execute(
                    "update caseproof._m2_check_runs set brief_version_id='bad' "
                    "where case_id=%s", (self.f.scope.case_id,),
                )
        self.save()
        with self.assertRaises(ObjectNotInPrerequisiteState):
            with connect() as conn:
                conn.execute(
                    "delete from caseproof._m2_review_events where case_id=%s",
                    (self.f.scope.case_id,),
                )


def recovery_probe(args: list[str]) -> None:
    org, case, run_sha = args
    with connect() as conn:
        row = conn.execute(
            "select h.revision,h.event_sha,r.payload_sha,r.payload "
            "from caseproof._m2_check_runs r "
            "join caseproof._m2_review_heads h on h.org_id=r.org_id "
            "and h.case_id=r.case_id and h.snapshot_sha=r.snapshot_sha "
            "where r.org_id=%s and r.case_id=%s and r.snapshot_sha=%s",
            (UUID(org), UUID(case), run_sha),
        ).fetchone()
    if row is None or row[0] != 1 or row[1] == "0" * 64:
        raise AssertionError("new-process persisted run/review not readable")
    if sha256(row[3].encode()).hexdigest() != row[2]:
        raise AssertionError("recovered run payload digest mismatch")
    print("M2_FRESH_PROCESS_RECORD_PASSED")


def main() -> None:
    _env()  # Hard refusal outside localhost disposable CI.
    if len(sys.argv) == 5 and sys.argv[1] == "--recover":
        recovery_probe(sys.argv[2:5])
        return
    _run(SQL.read_text(encoding="utf-8"), _env())
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(LedgerTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    print("M2_DISPOSABLE_REVIEW_CAS_AUDIT_RESTART_PASSED")


if __name__ == "__main__":
    main()
