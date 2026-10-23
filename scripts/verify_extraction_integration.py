"""Real disposable Postgres recovery/CAS/audit proof with SCRIPTED model responses.

Run after verify_s2_009b_database. No live provider, production Auth or customer data.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier
from uuid import UUID

from application.extraction.contracts import ExtractionError, Scope, StepState, digest
from application.extraction.pipeline import EvidenceIntelligence
from apps.api.disposable_extraction_journal import DisposablePostgresJournal
from domains.finance.extraction_rules import FinanceEvidencePolicy
from scripts.extraction_fixtures import ScriptedProvider, request
from scripts.verify_vault_integration import connect, seed

SQL = Path(__file__).resolve().parents[1] / "db/proposals/EI-001_disposable_extraction_journal.sql"


def journal(f):
    return DisposablePostgresJournal(connect, actor_id=f.actor)


def req_for(f):
    return replace(request(), scope=Scope(f.scope.org_id, f.scope.case_id))


class Integration(unittest.TestCase):
    def test_restart_in_separate_process_replays_all_responses(self):
        f = seed()
        req = req_for(f)
        provider = ScriptedProvider()
        report = EvidenceIntelligence(provider, journal(f), FinanceEvidencePolicy()).run(req)
        self.assertEqual(len(provider.calls), 2)
        child = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.verify_extraction_integration",
                "--recover",
                str(f.actor),
                str(f.scope.org_id),
                str(f.scope.case_id),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        self.assertEqual(child.stdout.strip(), digest(json.loads(report.to_json())))

    def test_scoped_reads_and_revoked_actor_fail(self):
        a, b = seed(), seed()
        journal(a).reserve(Scope(a.scope.org_id, a.scope.case_id), "r", "s", digest({}))
        with self.assertRaises(ExtractionError):
            journal(b).reserve(Scope(a.scope.org_id, a.scope.case_id), "r", "s", digest({}))
        with connect() as conn:
            conn.execute(
                "update caseproof.organization_members set active=false where org_id=%s and user_id=%s",
                (a.scope.org_id, a.actor),
            )
        with self.assertRaises(ExtractionError):
            journal(a).reserve(Scope(a.scope.org_id, a.scope.case_id), "r", "s", digest({}))

    def test_concurrent_cas_only_one_dispatch_event(self):
        f = seed()
        scope = Scope(f.scope.org_id, f.scope.case_id)
        journal(f).reserve(scope, "r", "s", digest({}))
        barrier = Barrier(2)

        def advance(_):
            barrier.wait()
            try:
                journal(f).transition(scope, "r", "s", StepState.PREPARED, StepState.DISPATCHED)
                return "dispatch"
            except ExtractionError:
                return "conflict"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(advance, range(2)))
        self.assertEqual(sorted(results), ["conflict", "dispatch"])
        with connect() as conn:
            count = conn.execute(
                "select count(*) from caseproof._ei_events where org_id=%s and state='dispatched'",
                (scope.org_id,),
            ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_unknown_dispatch_survives_new_adapter_without_repurchase(self):
        class Timeout(ScriptedProvider):
            def complete(self, *args, **kwargs):
                self.calls.append("uncertain")
                raise TimeoutError("synthetic")

        f = seed()
        provider = Timeout()
        first = EvidenceIntelligence(provider, journal(f), FinanceEvidencePolicy()).run(req_for(f))
        second = EvidenceIntelligence(provider, journal(f), FinanceEvidencePolicy()).run(req_for(f))
        self.assertEqual(first.to_json(), second.to_json())
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(first.failures[0]["reason"], "outcome_unknown")

    def test_event_failure_rolls_back_checkpoint_state(self):
        f = seed()
        scope = Scope(f.scope.org_id, f.scope.case_id)
        journal(f).reserve(scope, "r", "s", digest({}))

        class BrokenAudit(DisposablePostgresJournal):
            def _event(self, *args, **kwargs):
                raise RuntimeError("synthetic audit outage")

        with self.assertRaises(RuntimeError):
            BrokenAudit(connect, actor_id=f.actor).transition(
                scope, "r", "s", StepState.PREPARED, StepState.DISPATCHED
            )
        restored = journal(f).reserve(scope, "r", "s", digest({}))
        self.assertEqual(restored.state, StepState.PREPARED)

    def test_received_response_survives_committed_but_unacknowledged_write(self):
        f = seed()

        class LostAcknowledgement(DisposablePostgresJournal):
            crashed = False

            def transition(self, *args, **kwargs):
                row = super().transition(*args, **kwargs)
                if row.state is StepState.RECEIVED and not self.crashed:
                    self.crashed = True
                    raise RuntimeError("response commit succeeded but worker lost ack")
                return row

        provider = ScriptedProvider()
        with self.assertRaises(RuntimeError):
            EvidenceIntelligence(
                provider, LostAcknowledgement(connect, actor_id=f.actor), FinanceEvidencePolicy()
            ).run(req_for(f))
        report = EvidenceIntelligence(provider, journal(f), FinanceEvidencePolicy()).run(req_for(f))
        self.assertTrue(report.extraction_complete)
        self.assertEqual(len(provider.calls), 2)

    def test_changed_manifest_rejected_and_no_public_table_grants(self):
        f = seed()
        scope = Scope(f.scope.org_id, f.scope.case_id)
        journal(f).reserve(scope, "r", "s", digest({"v": 1}))
        with self.assertRaises(ExtractionError):
            journal(f).reserve(scope, "r", "s", digest({"v": 2}))
        with connect() as conn:
            for role in ("anon", "authenticated"):
                for table in ("_ei_steps", "_ei_events"):
                    can_read = conn.execute(
                        "select has_table_privilege(%s,%s,'select')", (role, f"caseproof.{table}")
                    ).fetchone()[0]
                    self.assertFalse(can_read)


def main():
    if len(sys.argv) == 5 and sys.argv[1] == "--recover":
        actor, org, case = (UUID(v) for v in sys.argv[2:])

        class NoNetwork(ScriptedProvider):
            def complete(self, *args, **kwargs):
                raise AssertionError("restart must not call provider")

        req = replace(request(), scope=Scope(org, case))
        report = EvidenceIntelligence(
            NoNetwork(), DisposablePostgresJournal(connect, actor_id=actor), FinanceEvidencePolicy()
        ).run(req)
        print(digest(json.loads(report.to_json())))
        return
    if len(sys.argv) != 1:
        raise SystemExit("unsupported integration arguments")
    with connect() as conn:
        conn.execute(SQL.read_text())
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Integration)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
