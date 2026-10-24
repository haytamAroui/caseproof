"""Real disposable review CAS/audit/replay/export tests. Synthetic identity only."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from application.documents.intake import CapturedDocument
from application.dossiers.pack import verify_pack
from application.extraction.contracts import ExtractionError, Scope
from application.review.contracts import ReviewCommand, ReviewConflict, ReviewKind
from apps.api.access_control import CaseAccessService
from apps.api.disposable_extraction_journal import DisposablePostgresJournal
from apps.api.disposable_review_repository import DisposableReviewRepository
from apps.api.evidence_vault_protocol import VaultScope, VaultUnavailable
from apps.api.postgres_case_repository import PostgresCaseAccessRepository
from apps.api.review_workbench import AuthenticatedReviewWorkbench, ReviewMaterial
from apps.api.synthetic_review_app import create_demo_app
from evals.document_corpus import CASES
from scripts.extraction_fixtures import NOW
from scripts.review_demo_fixture import demo_material
from scripts.verify_document_intake_integration import Catalog, SyntheticVerifier, extra_source, provision
from scripts.verify_vault_integration import Fixture, begin, connect, coordinator, seed

SQL = Path(__file__).resolve().parents[1] / "db/proposals/EI-003_disposable_review.sql"


def setup(root):
    first = provision(root)
    cases = CASES[:3]
    fixtures = (first, *(extra_source(root, first, c) for c in cases[1:]))
    with connect() as conn:
        conn.execute(
            "update caseproof.organization_members set actions=array['case:read','evidence:read','coverage:read',"
            "'finding:write','review:request'] where org_id=%s and user_id=%s",
            (first.scope.org_id, first.actor),
        )
    return fixtures


def context(first):
    access = CaseAccessService(
        SyntheticVerifier(first.actor),
        PostgresCaseAccessRepository(connect),
        "synthetic-issuer",
        "authenticated",
        lambda: NOW,
    )
    return access


def material(root, fixtures):
    from apps.api.access_control import CaseAction

    f = fixtures[0]
    authorized = context(f).authorize(
        "synthetic-fixture-only", str(f.scope.case_id), CaseAction.READ_EVIDENCE
    )
    records = Catalog(fixtures, CASES[:3]).list_sources(authorized)
    docs = tuple(CapturedDocument(r.source_id, r.original) for r in records)
    with connect() as conn:
        revision, policy = conn.execute(
            "select case_revision,effective_policy_version from caseproof.cases where org_id=%s and id=%s",
            (f.scope.org_id, f.scope.case_id),
        ).fetchone()
    snapshot, parsed = demo_material(
        scope=Scope(f.scope.org_id, f.scope.case_id),
        documents=docs,
        source_intents={c.case_id: fixture.intent for c, fixture in zip(CASES[:3], fixtures, strict=True)},
        case_revision=revision,
        policy_version=policy,
        journal=DisposablePostgresJournal(connect, actor_id=f.actor),
    )
    return ReviewMaterial(snapshot, parsed)


def facade(root, fixtures, repo=None):
    f = fixtures[0]
    captured = material(root, fixtures)

    def load(authorized):
        for fixture, document in zip(fixtures, captured.documents, strict=True):
            raw = coordinator(root, fixture).read(scope=fixture.scope, intent_id=fixture.intent)
            if raw != document.evidence.source.content:
                raise ExtractionError("source bytes changed")
        return captured

    return AuthenticatedReviewWorkbench(
        context(f), load, repo or DisposableReviewRepository(connect)
    ), captured


def command(snapshot, revision=0, identity=None):
    return ReviewCommand(
        identity or uuid4(),
        snapshot.snapshot_hash,
        revision,
        snapshot.data["extraction"]["atoms"][0]["candidate_id"],
        ReviewKind.CORRECT,
        "Synthetic review rationale",
        "A proposed correction",
    )


def state_rows(f):
    with connect() as conn:
        return tuple(
            conn.execute(
                "select count(*) from caseproof." + table + " where org_id=%s and case_id=%s",
                (f.scope.org_id, f.scope.case_id),
            ).fetchone()[0]
            for table in ("_review_events", "_review_receipts")
        )


class Integration(unittest.TestCase):
    def test_http_review_and_export_survive_fresh_repository(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            fixtures = setup(root)
            f = fixtures[0]
            service, captured = facade(root, fixtures)
            with TestClient(create_demo_app(service=service, case_id=str(f.scope.case_id))) as client:
                state = client.get("/demo/api/state").json()
                cmd = command(captured.snapshot)
                headers = {"Origin": "http://testserver", "X-Review-Session": state["session"]}
                response = client.post("/demo/api/reviews", json=cmd.payload(), headers=headers)
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.json()["approved"])
                replay = client.post("/demo/api/reviews", json=cmd.payload(), headers=headers).json()
                self.assertTrue(replay["replayed"])
            restarted, _ = facade(root, fixtures)
            with TestClient(create_demo_app(service=restarted, case_id=str(f.scope.case_id))) as client:
                state = client.get("/demo/api/state").json()
                self.assertEqual(state["revision"], 1)
                pack = client.get("/demo/api/export")
                result = verify_pack(pack.content, expected_manifest=pack.headers["x-pack-manifest-sha256"])
                self.assertEqual(result["review_events"], 1)
            self.assertEqual(state_rows(f), (1, 1))

    def test_same_command_concurrent_receipt_and_different_command_cas(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            fixtures = setup(root)
            f = fixtures[0]
            _, captured = facade(root, fixtures)
            repo = DisposableReviewRepository(connect)
            snap = captured.snapshot
            repo.publish(snap, f.actor)
            cmd = command(snap)
            barrier = Barrier(2)

            def same(_):
                barrier.wait()
                return repo.record(snap.scope, f.actor, cmd)

            with ThreadPoolExecutor(max_workers=2) as pool:
                receipts = list(pool.map(same, range(2)))
            self.assertEqual(sum(r["replayed"] for r in receipts), 1)
            barrier = Barrier(2)

            def race(_):
                barrier.wait()
                try:
                    repo.record(snap.scope, f.actor, command(snap, 1))
                    return "saved"
                except ReviewConflict:
                    return "conflict"

            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(sorted(pool.map(race, range(2))), ["conflict", "saved"])
            self.assertEqual(state_rows(f), (2, 2))

    def test_audit_failure_rolls_back_head_event_and_receipt(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            fixtures = setup(root)
            f = fixtures[0]
            _, captured = facade(root, fixtures)
            snap = captured.snapshot
            repo = DisposableReviewRepository(connect)
            repo.publish(snap, f.actor)

            class BrokenAudit(DisposableReviewRepository):
                def _append_event(self, *args):
                    super()._append_event(*args)
                    raise RuntimeError("synthetic audit outage")

            with self.assertRaises(RuntimeError):
                BrokenAudit(connect).record(snap.scope, f.actor, command(snap))
            self.assertEqual(repo.state(snap.scope, f.actor)["revision"], 0)
            self.assertEqual(state_rows(f), (0, 0))

    def test_unknown_commit_ack_reconciles_one_record(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            fixtures = setup(root)
            f = fixtures[0]
            _, captured = facade(root, fixtures)
            snap = captured.snapshot
            repo = DisposableReviewRepository(connect)
            repo.publish(snap, f.actor)
            cmd = command(snap)

            class LostAck:
                def __init__(self):
                    self.conn = connect()

                def __enter__(self):
                    return self.conn.__enter__()

                def __exit__(self, *args):
                    result = self.conn.__exit__(*args)
                    if args[0] is None:
                        raise ConnectionError("committed but acknowledgement lost")
                    return result

            with self.assertRaises(ConnectionError):
                DisposableReviewRepository(LostAck).record(snap.scope, f.actor, cmd)
            receipt = repo.record(snap.scope, f.actor, cmd)
            self.assertTrue(receipt["replayed"])
            self.assertEqual(state_rows(f), (1, 1))

    def test_revoked_foreign_actor_and_missing_permission_are_denied(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            fixtures = setup(root)
            f = fixtures[0]
            foreign = seed()
            _, captured = facade(root, fixtures)
            snap = captured.snapshot
            repo = DisposableReviewRepository(connect)
            repo.publish(snap, f.actor)
            with self.assertRaises(ExtractionError):
                repo.record(snap.scope, foreign.actor, command(snap))
            with connect() as conn:
                conn.execute(
                    "update caseproof.organization_members set active=false where org_id=%s and user_id=%s",
                    (f.scope.org_id, f.actor),
                )
            with self.assertRaises(ExtractionError):
                repo.state(snap.scope, f.actor)
            with connect() as conn:
                conn.execute(
                    "update caseproof.organization_members set active=true,actions=array['case:read','evidence:read','coverage:read'] "
                    "where org_id=%s and user_id=%s",
                    (f.scope.org_id, f.actor),
                )
            with self.assertRaises(ExtractionError):
                repo.record(snap.scope, f.actor, command(snap))
            self.assertEqual(state_rows(f), (0, 0))

    def test_stale_case_policy_snapshot_and_corrupt_bytes_block(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            fixtures = setup(root)
            f = fixtures[0]
            service, captured = facade(root, fixtures)
            snap = captured.snapshot
            repo = service.repository
            repo.publish(snap, f.actor)
            with connect() as conn:
                conn.execute(
                    "update caseproof.cases set effective_policy_version='changed-policy' where org_id=%s and id=%s",
                    (f.scope.org_id, f.scope.case_id),
                )
            with self.assertRaises(ReviewConflict):
                repo.record(snap.scope, f.actor, command(snap))
            with connect() as conn:
                conn.execute(
                    "update caseproof.cases set effective_policy_version=%s where org_id=%s and id=%s",
                    (snap.data["policy_version"], f.scope.org_id, f.scope.case_id),
                )
            from dataclasses import replace

            with self.assertRaises(ReviewConflict):
                repo.record(snap.scope, f.actor, replace(command(snap), snapshot_hash="f" * 64))
            intent = begin(coordinator(root, f), f)
            (root / intent.object_key).write_bytes(b"tampered")
            with self.assertRaises((VaultUnavailable, ExtractionError)):
                service.export(bearer="synthetic-fixture-only", case_id=str(f.scope.case_id))
            self.assertEqual(state_rows(f), (0, 0))

    def test_separate_process_replays_snapshot_and_review_receipt(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            fixtures = setup(root)
            f = fixtures[0]
            service, captured = facade(root, fixtures)
            snap = captured.snapshot
            repo = service.repository
            repo.publish(snap, f.actor)
            cmd = command(snap)
            receipt = repo.record(snap.scope, f.actor, cmd)
            metadata = {
                "org": str(f.scope.org_id),
                "case": str(f.scope.case_id),
                "actor": str(f.actor),
                "command": cmd.payload(),
                "fixtures": [{"version": str(v.version), "intent": str(v.intent)} for v in fixtures],
            }
            (root / "review-restart.json").write_text(json.dumps(metadata))
            child = subprocess.run(
                [sys.executable, "-m", "scripts.verify_review_integration", "--recover", str(root)],
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
            self.assertEqual(json.loads(child.stdout), {**receipt, "replayed": True})
            self.assertEqual(state_rows(f), (1, 1))

    def test_disposable_tables_have_no_public_grants(self):
        with connect() as conn:
            for table in ("_review_snapshots", "_review_heads", "_review_events", "_review_receipts"):
                for role in ("anon", "authenticated"):
                    allowed = conn.execute(
                        "select has_table_privilege(%s,%s,'select')", (role, "caseproof." + table)
                    ).fetchone()[0]
                    self.assertFalse(allowed)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--recover":
        root = Path(sys.argv[2])
        saved = json.loads((root / "review-restart.json").read_text())
        fixtures = tuple(
            Fixture(
                VaultScope(UUID(saved["org"]), UUID(saved["case"])),
                UUID(saved["actor"]),
                UUID(ids["version"]),
                UUID(ids["intent"]),
                case.captured().source.content,
                case.media_type,
            )
            for ids, case in zip(saved["fixtures"], CASES[:3], strict=True)
        )
        _, captured = facade(root, fixtures)
        c = saved["command"]
        cmd = ReviewCommand(
            UUID(c["request_id"]),
            c["snapshot_hash"],
            c["expected_revision"],
            c["item_id"],
            ReviewKind(c["kind"]),
            c["note"],
            c["correction"],
        )
        receipt = DisposableReviewRepository(connect).record(captured.snapshot.scope, fixtures[0].actor, cmd)
        print(json.dumps(receipt))
        return
    if len(sys.argv) != 1:
        raise SystemExit("unsupported integration arguments")
    with connect() as conn:
        conn.execute(SQL.read_text())
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(Integration)
    )
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
