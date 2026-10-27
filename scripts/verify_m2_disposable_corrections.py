"""M2-B disposable correction/recheck saga + crash recovery acceptance.

Runs after private check integration, on the LOCAL guarded PostgreSQL fixture.
All actors in this script are synthetic; no customer source, Word integration
or live Supabase session is used.
"""
from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

from psycopg.errors import ObjectNotInPrerequisiteState

from application.litigation.review_cycle import CorrectionProposal
from application.litigation.unified_review import ObservationReview, ReviewDisposition
from apps.api.disposable_litigation_corrections import (
    CorrectionCommand,
    CorrectionConflict,
    DisposableCorrectionCoordinator,
)
from scripts.verify_m2_brief_graph import add_verified_version, new_binding, normalize
from scripts.verify_m2_private_check_composition import M2CheckCompositionTests
from scripts.verify_s2_002_database import _env, _run
from scripts.verify_vault_integration import connect

SQL = Path(__file__).resolve().parents[1] / "db/proposals/PIV-M2_disposable_correction_recheck.sql"


class DurableCorrectionTests(unittest.TestCase):
    def _before_initial_graph_publish(self) -> None:
        # Synthetic corrections exist as separately preserved Vault artifacts
        # before recording the reviewer check. Preserving an original AFTER
        # a reviewed check increments the case revision and invalidates it.
        text = self.f.data.decode("utf-8")
        self.staged_sources = {}
        for amount in ("€12501", "€12502"):
            bytes_new = text.replace("€12500", amount).encode("utf-8")
            self.staged_sources[amount] = add_verified_version(
                self.root, self.f, bytes_new,
            )

    def setUp(self) -> None:
        M2CheckCompositionTests.setUp(self)
        self.run = self._check()
        review = ObservationReview(
            "fact:money-1", str(self.f.actor), ReviewDisposition.CONFIRMED,
            "Reviewing only a source-backed candidate, not a legal conclusion",
        )
        self.ledger.record(
            org_id=self.f.scope.org_id, actor_id=self.f.actor,
            run=self.run, request_id=uuid4(),
            expected_revision=0, decision=review,
        )
        self.coordinator = DisposableCorrectionCoordinator(
            connect, self.graph, self.ledger, self.service,
        )
        self.bearer = "synthetic-fixture-only"

    def _check(self, *, version=None):
        return M2CheckCompositionTests.check(self, version=version)

    def new_command(self, *, new_amount="€12501", request_id=None):
        text = self.f.data.decode("utf-8")
        before = "€12500"
        begin = text.index(before)
        proposed = text[:begin] + new_amount + text[begin + len(before):]
        source = self.staged_sources[new_amount]
        normalized = normalize(source, uuid4())
        proposal = CorrectionProposal(
            "fact:money-1", str(self.f.actor), self.run.snapshot_hash,
            self.run.brief_version_id, self.run.representation_sha256,
            begin, begin + len(before), before, new_amount,
            "Human reviewed a candidate amount; new private source required",
        )
        command = CorrectionCommand(
            request_id or uuid4(), self.run, proposal,
            normalized, new_binding(source), 1, 1,
        )
        return command, proposed

    def prepare(self, cmd, *, coordinator=None):
        return (coordinator or self.coordinator).prepare(
            bearer=self.bearer, brief_id=self.brief_id, command=cmd,
        )

    def apply(self, cmd, *, coordinator=None):
        return (coordinator or self.coordinator).apply(
            bearer=self.bearer, brief_id=self.brief_id, command=cmd,
        )

    def recheck(self, cmd, *, coordinator=None):
        return (coordinator or self.coordinator).recheck(
            bearer=self.bearer, brief_id=self.brief_id, command=cmd,
        )

    def count(self, table: str) -> int:
        with connect() as conn:
            return int(conn.execute(
                "select count(*) from caseproof." + table +
                " where org_id=%s and case_id=%s and brief_id=%s",
                (self.f.scope.org_id, self.f.scope.case_id, self.brief_id),
            ).fetchone()[0])

    def test_correct_persist_recheck_and_independent_restart(self):
        command, revised_text = self.new_command()
        prepared = self.prepare(command)
        self.assertEqual(prepared.stage, "prepared")
        self.assertEqual(self.count("_m2_correction_plans"), 1)
        self.assertEqual(self.count("_m2_correction_events"), 0)
        applied = self.apply(command)
        self.assertEqual(applied.stage, "graph_applied")
        self.assertEqual(applied.graph_sha256, prepared.graph_sha256)
        self.assertFalse(applied.release_authorized)
        self.assertEqual(self.count("_m2_correction_events"), 1)
        self.assertEqual(
            self.graph.load(
                org_id=self.f.scope.org_id, actor_id=self.f.actor,
                case_id=self.f.scope.case_id, brief_id=self.brief_id,
            ).representation.text, revised_text,
        )
        # New coordinator instance uses the same DB and immutable Vault,
        # not the old process' in-memory state.
        fresh = DisposableCorrectionCoordinator(
            connect, self.graph, self.ledger, self.service,
        )
        completed = self.recheck(command, coordinator=fresh)
        self.assertEqual(completed.stage, "rechecked")
        self.assertNotEqual(completed.recheck_run_sha256, self.run.snapshot_hash)
        self.assertFalse(completed.release_authorized)
        self.assertEqual(self.count("_m2_correction_events"), 2)
        with connect() as conn:
            stored = conn.execute(
                "select count(*) from caseproof._m2_check_runs "
                "where org_id=%s and case_id=%s and snapshot_sha=%s",
                (self.f.scope.org_id, self.f.scope.case_id,
                 completed.recheck_run_sha256),
            ).fetchone()[0]
        self.assertEqual(stored, 1)
        self.assertEqual(self.recheck(command).recheck_run_sha256,
                         completed.recheck_run_sha256)
        self.assertEqual(self.count("_m2_correction_plans"), 1)
        self.assertEqual(self.count("_m2_correction_events"), 2)
        # Old original and original run remain provable and immutable.
        old = self.graph.load(
            org_id=self.f.scope.org_id, actor_id=self.f.actor,
            case_id=self.f.scope.case_id, brief_id=self.brief_id,
            version_id=UUID(self.run.brief_version_id), require_current=False,
        )
        self.assertEqual(old.representation.text, self.f.data.decode("utf-8"))
        self.assertFalse(old.is_current)

    def test_crash_after_graph_commit_is_idempotently_recoverable(self):
        cmd, _ = self.new_command()

        class CrashAfterGraph(DisposableCorrectionCoordinator):
            @staticmethod
            def _audit(conn, ctx, request_id, action, fingerprint):
                if action == "m2_correction_graph_applied":
                    raise RuntimeError("injected after graph commit before stage event")
                return DisposableCorrectionCoordinator._audit(
                    conn, ctx, request_id, action, fingerprint,
                )

        transient = CrashAfterGraph(
            connect, self.graph, self.ledger, self.service,
        )
        with self.assertRaises(RuntimeError):
            self.apply(cmd, coordinator=transient)
        self.assertEqual(self.count("_m2_correction_plans"), 1)
        self.assertEqual(self.count("_m2_correction_events"), 0)
        recovered = self.recheck(cmd)
        self.assertEqual(recovered.stage, "rechecked")
        self.assertEqual(self.count("_m2_correction_plans"), 1)
        self.assertEqual(self.count("_m2_correction_events"), 2)

    def test_revoked_review_permission_after_prepare_blocks_mutation(self):
        cmd, _ = self.new_command()
        self.prepare(cmd)
        with connect() as conn:
            conn.execute(
                "update caseproof._m1_matter_grants set active=false "
                "where case_id=%s and user_id=%s",
                (self.f.scope.case_id, self.f.actor),
            )
        with self.assertRaises(CorrectionConflict):
            self.apply(cmd)
        self.assertEqual(self.count("_m2_correction_events"), 0)
        self.assertEqual(self.count("_m2_correction_plans"), 1)
        with connect() as conn:
            head = conn.execute(
                "select revision from caseproof._m2_brief_heads "
                "where brief_id=%s", (self.brief_id,),
            ).fetchone()[0]
        self.assertEqual(head, 1)

    def test_source_staged_after_review_invalidates_old_case_snapshot(self):
        # Fresh source custody touches the case revision. An old check and
        # human disposition must not be quietly carried across that change.
        cmd, _ = self.new_command()
        add_verified_version(self.root, self.f, b"late unrelated case source")
        with self.assertRaises(CorrectionConflict):
            self.prepare(cmd)
        self.assertEqual(self.count("_m2_correction_plans"), 0)

    def test_unreviewed_or_dismissed_candidate_cannot_prepare(self):
        cmd, _ = self.new_command()
        invalid = replace(cmd, expected_review_revision=2)
        with self.assertRaises(CorrectionConflict):
            self.prepare(invalid)
        bad_proposal = replace(cmd.proposal, actor_id=str(uuid4()))
        with self.assertRaises(CorrectionConflict):
            self.prepare(replace(cmd, proposal=bad_proposal))
        with self.assertRaises(CorrectionConflict):
            self.prepare(replace(cmd, request_id=uuid4(),
                                 expected_brief_revision=3))
        self.assertEqual(self.count("_m2_correction_plans"), 0)

    def test_two_prepared_corrections_stale_graph_cas_only_one_applies(self):
        first, _ = self.new_command()
        second, _ = self.new_command(new_amount="€12502")
        self.prepare(first)
        self.prepare(second)
        self.apply(first)
        with self.assertRaises(CorrectionConflict):
            self.apply(second)
        self.assertEqual(self.count("_m2_correction_plans"), 2)
        self.assertEqual(self.count("_m2_correction_events"), 1)

    def test_pending_history_and_final_events_immutable(self):
        cmd, _ = self.new_command()
        self.recheck(cmd)
        for sql in (
            "delete from caseproof._m2_correction_plans where brief_id=%s",
            "update caseproof._m2_correction_events "
            "set graph_sha=repeat('0',64) where brief_id=%s",
        ):
            with self.assertRaises(ObjectNotInPrerequisiteState):
                with connect() as conn:
                    conn.execute(sql, (self.brief_id,))

    def test_same_request_cannot_be_reused_for_changed_new_original(self):
        cmd, _ = self.new_command()
        self.prepare(cmd)
        other, _ = self.new_command(new_amount="€12502", request_id=cmd.request_id)
        with self.assertRaises(CorrectionConflict):
            self.prepare(other)
        self.assertEqual(self.count("_m2_correction_plans"), 1)


def main() -> None:
    env = _env()
    _run(SQL.read_text(encoding="utf-8"), env)
    _run(
        "set role authenticated; select * from caseproof._m2_correction_plans;",
        env, should_pass=False,
    )
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(DurableCorrectionTests),
    )
    if not result.wasSuccessful():
        raise SystemExit(1)
    print("M2_DISPOSABLE_CORRECTION_PREPARE_GRAPH_RECHECK_RECOVERY_PASSED")


if __name__ == "__main__":
    main()
