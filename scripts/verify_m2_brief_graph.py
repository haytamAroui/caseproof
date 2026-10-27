"""Disposable verified-original brief graph acceptance (synthetic identity only).

Runs AFTER M1 and S2 Vault proposals on the disposable PostgreSQL CI service.
No production migrations, signed user tokens or outbound model requests.
"""
from __future__ import annotations

import faulthandler
import signal
import unittest
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from uuid import UUID, uuid4

from psycopg.errors import ObjectNotInPrerequisiteState

from application.litigation.brief_checks import DraftReference, VersionedBrief
from application.litigation.factual_values import FactAssertion, FactKind, FactRole, FactState
from application.litigation.library import EvidencePreview, EvidenceRow
from application.litigation.unified_review import (
    BriefRepresentation,
    ObservationReview,
    ReviewDisposition,
    SourceScope,
    run_unified_check,
)
from apps.api.disposable_litigation_brief_graph import (
    BriefGraphConflict,
    DisposableBriefGraphStore,
    VerifiedBriefBinding,
)
from apps.api.disposable_litigation_review_ledger import DisposableM2ReviewLedger
from apps.api.evidence_vault_protocol import VaultScope
from domains.disputes.exhibits import ExhibitEntry, ExhibitPage, ExhibitRegister
from scripts.verify_m2_disposable_runs import fixture
from scripts.verify_s2_002_database import _env, _run
from scripts.verify_vault_integration import Fixture, begin, connect, coordinator

SQL = Path(__file__).resolve().parents[1] / "db/proposals/PIV-M2_disposable_brief_graph.sql"


def new_binding(f) -> VerifiedBriefBinding:
    with connect() as conn:
        document = conn.execute(
            "select document_id from caseproof.document_versions "
            "where org_id=%s and id=%s", (f.scope.org_id, f.version),
        ).fetchone()[0]
    return VerifiedBriefBinding(document, f.version, f.intent)


def normalize(f, version: UUID) -> BriefRepresentation:
    text = f.data.decode("utf-8")
    reference = DraftReference("ref-1", "Stuk 1", None, None)
    claim = FactAssertion(
        "money-1", "ref-1", text, 0, len(text), FactKind.MONEY,
        FactRole.PAYMENT, "nl", "nl",
    )
    brief = VersionedBrief(
        str(f.scope.case_id), str(version), sha256(f.data).hexdigest(),
        (reference,),
    )
    return BriefRepresentation(brief, text, sha256(text.encode()).hexdigest(),
                               "fixture-utf8-v1", (claim,))


def add_verified_version(root: Path, existing: Fixture, data: bytes) -> Fixture:
    """New immutable original in the SAME case; never overwrite first source."""
    new_version, new_intent, document = uuid4(), uuid4(), uuid4()
    other = Fixture(existing.scope, existing.actor, new_version,
                    new_intent, data, "text/plain")
    with connect() as conn:
        conn.execute(
            "insert into caseproof.documents(id,org_id,case_id,source_label) "
            "values(%s,%s,%s,%s)", (
                document, existing.scope.org_id, existing.scope.case_id,
                "versioned-brief-copy",
            ),
        )
        conn.execute(
            "insert into caseproof.document_versions("
            "id,org_id,document_id,version_number,original_sha256_hex,"
            "byte_length,media_type) values(%s,%s,%s,1,%s,%s,'text/plain')",
            (new_version, existing.scope.org_id, document,
             sha256(data).hexdigest(), len(data)),
        )
    vault = coordinator(root, other)
    begin(vault, other)
    vault.upload(scope=other.scope, intent_id=other.intent, data=data)
    return other


class BriefGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = TemporaryDirectory(prefix="caseproof-m2-brief-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.f, _ = fixture(self.root)
        self.graph_id = uuid4()
        self.version_id = uuid4()
        self.binding = new_binding(self.f)
        self.representation = normalize(self.f, self.version_id)
        self.store = DisposableBriefGraphStore(
            connect, lambda org, case, intent: coordinator(self.root, self.f).read(
                scope=VaultScope(org, case), intent_id=intent,
            ),
        )

    def publish(self, *, f=None, representation=None, expected=0,
                request=None, document_role="own_draft"):
        target = f or self.f
        return self.store.publish(
            org_id=self.f.scope.org_id, actor_id=self.f.actor,
            brief_id=self.graph_id, binding=new_binding(target),
            representation=representation or self.representation,
            request_id=request or uuid4(), expected_revision=expected,
            document_role=document_role,
        )

    def load(self, **kwargs):
        return self.store.load(
            org_id=self.f.scope.org_id, actor_id=self.f.actor,
            case_id=self.f.scope.case_id, brief_id=self.graph_id, **kwargs,
        )

    def test_persistent_graph_roundtrip_keeps_exact_source_and_assertion(self):
        receipt = self.publish()
        self.assertEqual(receipt.revision, 1)
        self.assertFalse(receipt.release_authorized)
        reopened = DisposableBriefGraphStore(connect, self.store._read_original)
        result = reopened.load(
            org_id=self.f.scope.org_id, actor_id=self.f.actor,
            case_id=self.f.scope.case_id, brief_id=self.graph_id,
        )
        self.assertEqual(result.representation, self.representation)
        self.assertEqual(result.binding, self.binding)
        self.assertEqual(result.graph_sha256, receipt.graph_sha256)
        self.assertTrue(result.is_current)
        self.assertEqual(result.document_role, "own_draft")
        with connect() as conn:
            references = conn.execute(
                "select count(*) from caseproof._m2_brief_references "
                "where version_id=%s", (self.version_id,),
            ).fetchone()[0]
            assertions = conn.execute(
                "select count(*) from caseproof._m2_brief_assertions "
                "where version_id=%s", (self.version_id,),
            ).fetchone()[0]
        self.assertEqual((references, assertions), (1, 1))

    def test_restored_graph_to_check_to_durable_review(self):
        self.publish()
        restored = self.load()
        source_id = str(self.binding.document_id)
        version_id = str(self.binding.document_version_id)
        row = EvidenceRow(
            source_id, source_id, version_id, sha256(self.f.data).hexdigest(),
            "text/plain", "ready", "fixture-utf8-v1", "rep-1", (), (),
        )
        preview = EvidencePreview(
            row, self.f.data.decode("utf-8"),
            ((0, len(self.f.data.decode("utf-8")), "identity_utf8", None),),
        )
        register = ExhibitRegister(1, (
            ExhibitEntry(
                "exhibit-1", "Stuk 1",
                (ExhibitPage(source_id, version_id, printed_page=1),),
                confirmed=True,
            ),
        ))
        run = run_unified_check(
            representation=restored.representation,
            register=register, previews=(preview,),
            source_scope=SourceScope(((source_id, version_id),)),
            authorized_case_id=str(self.f.scope.case_id),
            authorized_register_revision=1,
        )
        self.assertEqual(run.factual_observations[0].state, FactState.MATCH)
        ledger = DisposableM2ReviewLedger(connect)
        self.assertTrue(ledger.publish(
            org_id=self.f.scope.org_id, actor_id=self.f.actor, run=run,
        ))
        decision = ObservationReview(
            "fact:money-1", str(self.f.actor),
            ReviewDisposition.CONFIRMED,
            "Synthetic reviewer confirmed source-level value alignment",
        )
        recorded, replay = ledger.record(
            org_id=self.f.scope.org_id, actor_id=self.f.actor, run=run,
            request_id=uuid4(), expected_revision=0, decision=decision,
        )
        self.assertFalse(replay)
        self.assertEqual(recorded.revision, 1)
        self.assertFalse(recorded.customer_release_authorized)
        readback = DisposableM2ReviewLedger(connect).state(
            org_id=self.f.scope.org_id, actor_id=self.f.actor, run=run,
        )
        self.assertEqual(readback.packet, recorded.packet)

    def test_request_replay_and_stale_revision_fail_closed(self):
        request = uuid4()
        first = self.publish(request=request)
        replay = self.publish(request=request)
        self.assertEqual(first.graph_sha256, replay.graph_sha256)
        self.assertTrue(replay.replayed)
        with self.assertRaises(BriefGraphConflict):
            self.publish(request=request, document_role="opponent_brief")
        with self.assertRaises(BriefGraphConflict):
            self.publish()
        with self.assertRaises(BriefGraphConflict):
            self.publish(expected=1)  # Same physical source version forbidden.

    def test_new_preserved_source_revision_and_historical_read(self):
        first = self.publish()
        old = self.representation
        other = add_verified_version(
            self.root, self.f,
            b"De betaling van EUR 13000 was op 23 mei 2026.",
        )
        second_version = uuid4()
        second = normalize(other, second_version)
        second_receipt = self.publish(f=other, representation=second, expected=1)
        self.assertEqual(second_receipt.revision, 2)
        self.assertNotEqual(first.graph_sha256, second_receipt.graph_sha256)
        self.assertEqual(self.load().representation, second)
        with self.assertRaises(BriefGraphConflict):
            self.load(version_id=self.version_id)
        history = self.load(version_id=self.version_id, require_current=False)
        self.assertEqual(history.representation, old)
        self.assertFalse(history.is_current)

    def test_cross_case_revocation_and_source_damage_reject(self):
        with self.assertRaises(BriefGraphConflict):
            self.store.publish(
                org_id=uuid4(), actor_id=self.f.actor,
                brief_id=self.graph_id, binding=self.binding,
                representation=self.representation,
                document_role="own_draft", request_id=uuid4(),
                expected_revision=0,
            )
        self.publish()
        with connect() as conn:
            conn.execute(
                "update caseproof._m1_matter_grants set active=false "
                "where case_id=%s and user_id=%s",
                (self.f.scope.case_id, self.f.actor),
            )
        with self.assertRaises(BriefGraphConflict):
            self.load()
        with connect() as conn:
            conn.execute(
                "update caseproof._m1_matter_grants set active=true "
                "where case_id=%s and user_id=%s",
                (self.f.scope.case_id, self.f.actor),
            )
        # Bytes missing/tampered cannot pass just because DB state is verified.
        with connect() as conn:
            key = conn.execute(
                "select object_key from caseproof._s2_009b_vault_intents "
                "where intent_id=%s", (self.f.intent,),
            ).fetchone()[0]
        (self.root / key).write_bytes(b"tampered private original")
        with self.assertRaises(BriefGraphConflict):
            self.load()

    def test_organization_permission_and_snapshot_revocation(self):
        self.publish()
        with connect() as conn:
            conn.execute(
                "update caseproof.organization_members "
                "set actions=array['case:read','review:request']::text[] "
                "where org_id=%s and user_id=%s",
                (self.f.scope.org_id, self.f.actor),
            )
        with self.assertRaises(BriefGraphConflict):
            self.load()
        with connect() as conn:
            conn.execute(
                "update caseproof.organization_members "
                "set actions=array['case:read','review:request','finding:write']::text[] "
                "where org_id=%s and user_id=%s",
                (self.f.scope.org_id, self.f.actor),
            )
            conn.execute(
                "update caseproof.cases set case_revision=case_revision+1 "
                "where id=%s", (self.f.scope.case_id,),
            )
        with self.assertRaises(BriefGraphConflict):
            self.load()
        self.assertTrue(self.load(require_current=False).is_current)

    def test_audit_failure_rolls_back_and_immutable_history(self):
        class FailAuditConnection:
            def __init__(self):
                self.conn = connect()

            def __enter__(self):
                self.conn.__enter__()
                return self

            def __exit__(self, *args):
                return self.conn.__exit__(*args)

            def execute(self, sql, params=None):
                if "insert into caseproof.audit_events(" in sql:
                    raise RuntimeError("injected audit outage")
                return self.conn.execute(sql, params)

        failed = DisposableBriefGraphStore(
            FailAuditConnection, self.store._read_original,
        )
        with self.assertRaises(RuntimeError):
            failed.publish(
                org_id=self.f.scope.org_id, actor_id=self.f.actor,
                brief_id=self.graph_id, binding=self.binding,
                representation=self.representation,
                document_role="own_draft", request_id=uuid4(),
                expected_revision=0,
            )
        with connect() as conn:
            n = conn.execute(
                "select count(*) from caseproof._m2_brief_versions "
                "where brief_id=%s", (self.graph_id,),
            ).fetchone()[0]
        self.assertEqual(n, 0)
        with self.assertRaises(BriefGraphConflict):
            self.store.publish(
                org_id=self.f.scope.org_id, actor_id=uuid4(),
                brief_id=self.graph_id, binding=self.binding,
                representation=self.representation,
                document_role="own_draft", request_id=uuid4(),
                expected_revision=0,
            )
        self.publish()
        for statement in (
            "update caseproof._m2_brief_versions set parser_id='bad' where brief_id=%s",
            "delete from caseproof._m2_brief_events where brief_id=%s",
            "update caseproof._m2_brief_references set exhibit_label='fake' where brief_id=%s",
        ):
            with self.assertRaises(ObjectNotInPrerequisiteState):
                with connect() as conn:
                    conn.execute(statement, (self.graph_id,))
        self.assertEqual(self.load().revision, 1)

    def test_two_writers_same_revision_only_one_commits(self):
        self.publish()
        a = add_verified_version(self.root, self.f, b"De betaling van EUR 13000.")
        b = add_verified_version(self.root, self.f, b"De betaling van EUR 14000.")
        barrier = Barrier(2)
        def attempt(other):
            barrier.wait()
            try:
                self.publish(f=other, representation=normalize(other, uuid4()),
                             expected=1)
                return "committed"
            except BriefGraphConflict:
                return "rejected"
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, (a, b)))
        self.assertEqual(sorted(outcomes), ["committed", "rejected"])
        self.assertEqual(self.load().revision, 2)


def main() -> None:
    _env()
    _run(SQL.read_text(encoding="utf-8"), _env())
    # Protect physical graph tables from PostgREST's authenticated role.
    _run("set role authenticated; select * from caseproof._m2_brief_versions;",
         _env(), should_pass=False)
    # Fail fast with a meaningful traceback instead of consuming an entire
    # GitHub Actions job if a fixture holds a database lock indefinitely.
    faulthandler.dump_traceback_later(20, repeat=True)
    signal.alarm(85)
    try:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(BriefGraphTests)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    finally:
        signal.alarm(0)
        faulthandler.cancel_dump_traceback_later()
    if not result.wasSuccessful():
        raise SystemExit(1)
    print("M2_DISPOSABLE_BRIEF_GRAPH_CAS_SOURCE_RESTART_PASSED")


if __name__ == "__main__":
    main()
