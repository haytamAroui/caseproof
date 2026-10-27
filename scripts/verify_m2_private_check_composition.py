"""M2-B actual private Postgres composition, signed-boundary fixture, no live API.

Requires existing local isolated PostgreSQL 17 service initialized through
Vault, M1 exhibit grants, M2 review and M2 brief graph proposals. Tests are
synthetic only, never a proof of genuine Supabase RLS or real PDF/OCR quality.
"""
from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from application.litigation.brief_checks import CitationCheckState, DraftReference
from application.litigation.exhibit_confirmation import serialized_entries
from apps.api.access_control import AccessRejected
from apps.api.disposable_litigation_brief_graph import DisposableBriefGraphStore
from apps.api.disposable_litigation_review_ledger import DisposableM2ReviewLedger
from apps.api.evidence_vault_protocol import VaultScope
from apps.api.litigation_check_service import AuthorizedLitigationChecker
from apps.api.postgres_litigation_check_store import PostgresPrivateMatterCheckStore
from domains.disputes.exhibits import ExhibitEntry, ExhibitPage
from scripts.extraction_fixtures import NOW
from scripts.verify_document_intake_integration import SyntheticVerifier
from scripts.verify_m2_brief_graph import (
    add_verified_version,
    new_binding,
    normalize,
)
from scripts.verify_m2_disposable_runs import fixture
from scripts.verify_s2_002_database import _env
from scripts.verify_vault_integration import connect, coordinator

EVIDENCE = b"De betaling van EUR 12500 was op 22 mei 2026."


class M2CheckCompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = TemporaryDirectory(prefix="caseproof-m2-private-check-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.f, _ = fixture(self.root)
        # Independent immutable piece, not the draft's own SourceVersion.
        self.evidence = add_verified_version(self.root, self.f, EVIDENCE)
        evidence_document = new_binding(self.evidence).document_id
        register = (
            ExhibitEntry(
                "stuk-1", "Stuk 1",
                (ExhibitPage(
                    str(evidence_document), str(self.evidence.version),
                    printed_page=1,
                ),),
                confirmed=True,
            ),
        )
        encoded = serialized_entries(register)
        with connect() as conn:
            conn.execute(
                "select * from caseproof._m1_disposable_confirm_exhibits("
                "%s,%s,%s,1,%s::jsonb,%s)",
                (self.f.actor, self.f.scope.case_id, uuid4(),
                 encoded.decode("utf-8"), sha256(encoded).hexdigest()),
            ).fetchone()
        self.brief_id = uuid4()
        self.brief_version = uuid4()
        self.reader = lambda org, case, intent: coordinator(
            self.root, self.f,
        ).read(scope=VaultScope(org, case), intent_id=intent)
        self.graph = DisposableBriefGraphStore(connect, self.reader)
        self.graph.publish(
            org_id=self.f.scope.org_id, actor_id=self.f.actor,
            brief_id=self.brief_id, binding=new_binding(self.f),
            representation=normalize(self.f, self.brief_version),
            document_role="own_draft", request_id=uuid4(), expected_revision=0,
        )
        self.store = PostgresPrivateMatterCheckStore(connect, self.graph, self.reader)
        self.ledger = DisposableM2ReviewLedger(connect)
        self.service = AuthorizedLitigationChecker(
            verifier=SyntheticVerifier(self.f.actor), store=self.store,
            publisher=self.ledger,
            issuer="synthetic-issuer", audience="authenticated",
            clock=lambda: NOW + timedelta(minutes=1),
        )

    def check(self, *, version=None, case=None, bearer="synthetic-fixture-only"):
        return self.service.check(
            bearer=bearer,
            case_id=case or str(self.f.scope.case_id),
            brief_version_id=version or str(self.brief_version),
        )

    def test_full_private_graph_to_exhibit_vault_to_check_to_ledger(self):
        check = self.check()
        self.assertEqual(check.brief_version_id, str(self.brief_version))
        self.assertEqual(check.exhibit_revision, 2)
        self.assertEqual(len(check.declared), 1)
        self.assertEqual(check.declared[0][1], str(self.evidence.version))
        self.assertEqual(check.processed, check.declared)
        self.assertEqual(check.incomplete, ())
        self.assertEqual(len(check.factual_observations), 1)
        self.assertEqual(check.factual_observations[0].claim_id, "money-1")
        with connect() as conn:
            self.assertEqual(conn.execute(
                "select count(*) from caseproof._m2_check_runs "
                "where case_id=%s and brief_version_id=%s",
                (self.f.scope.case_id, str(self.brief_version)),
            ).fetchone()[0], 1)
        self.assertEqual(
            self.ledger.state(org_id=self.f.scope.org_id, actor_id=self.f.actor,
                              run=check).revision, 0,
        )
        # Idempotent independent retry stores only the same snapshot once.
        self.assertEqual(self.check().snapshot_hash, check.snapshot_hash)

    def test_signed_boundary_and_private_matter_denials(self):
        for case, bearer in (
            (str(self.f.scope.case_id), "wrong"),
            (str(uuid4()), "synthetic-fixture-only"),
        ):
            with self.assertRaises(AccessRejected) as error:
                self.check(case=case, bearer=bearer)
            self.assertIn(error.exception.http_status, (401, 404))
        # Same valid org membership but revoked explicit matter grant.
        with connect() as conn:
            conn.execute(
                "update caseproof._m1_matter_grants set active=false "
                "where case_id=%s and user_id=%s",
                (self.f.scope.case_id, self.f.actor),
            )
        with self.assertRaises(AccessRejected):
            self.check()

    def test_post_load_exhibit_change_prevents_publishing(self):
        original = self.store.still_current
        def changed(*, access, bundle):
            with connect() as conn:
                conn.execute(
                    "update caseproof._m1_exhibit_heads "
                    "set revision=revision+1 where org_id=%s and case_id=%s",
                    (self.f.scope.org_id, self.f.scope.case_id),
                )
            return original(access=access, bundle=bundle)
        self.store.still_current = changed  # type: ignore[method-assign]
        with self.assertRaises(AccessRejected) as error:
            self.check()
        self.assertEqual(error.exception.http_status, 503)
        with connect() as conn:
            self.assertEqual(conn.execute(
                "select count(*) from caseproof._m2_check_runs where case_id=%s",
                (self.f.scope.case_id,),
            ).fetchone()[0], 0)

    def test_source_unavailable_and_noncanonical_brief_masked(self):
        with self.assertRaises(AccessRejected):
            self.check(version=self.brief_version.hex)
        with connect() as conn:
            key = conn.execute(
                "select object_key from caseproof._s2_009b_vault_intents "
                "where intent_id=%s", (self.evidence.intent,),
            ).fetchone()[0]
        (self.root / key).write_bytes(b"tampered")
        with self.assertRaises(AccessRejected):
            self.check()
        with connect() as conn:
            self.assertEqual(conn.execute(
                "select count(*) from caseproof._m2_check_runs where case_id=%s",
                (self.f.scope.case_id,),
            ).fetchone()[0], 0)

    def test_page_scoped_exact_quote_without_page_provenance_is_incomplete(self):
        # The literal quote is present, but text/plain carries no authoritative
        # physical PDF page. It MUST NOT become a definitive mismatch.
        confirmed = (
            ExhibitEntry(
                "stuk-1", "Stuk 1", (
                    ExhibitPage(
                        str(new_binding(self.evidence).document_id),
                        str(self.evidence.version),
                        pdf_page=1, printed_page=1,
                    ),
                ), confirmed=True,
            ),
        )
        encoded = serialized_entries(confirmed)
        with connect() as conn:
            conn.execute(
                "select * from caseproof._m1_disposable_confirm_exhibits("
                "%s,%s,%s,2,%s::jsonb,%s)",
                (self.f.actor, self.f.scope.case_id, uuid4(),
                 encoded.decode("utf-8"), sha256(encoded).hexdigest()),
            ).fetchone()
        next_original = add_verified_version(self.root, self.f, self.f.data)
        new_id = uuid4()
        rep = normalize(next_original, new_id)
        ref = DraftReference("ref-1", "Stuk 1", EVIDENCE.decode(), 1)
        rep = replace(rep, brief=replace(rep.brief, references=(ref,)))
        self.graph.publish(
            org_id=self.f.scope.org_id, actor_id=self.f.actor,
            brief_id=self.brief_id, binding=new_binding(next_original),
            representation=rep, document_role="own_draft",
            request_id=uuid4(), expected_revision=1,
        )
        run = self.check(version=str(new_id))
        self.assertEqual(run.declared, run.incomplete)
        self.assertEqual(run.processed, ())
        self.assertEqual(
            run.citation_observations[0].state,
            CitationCheckState.INCOMPLETE_EXTRACTION,
        )
        self.assertNotEqual(
            run.citation_observations[0].state,
            CitationCheckState.QUOTE_NOT_FOUND,
        )
        # Byte-identical, no-physical-page check must remain conservative
        # even if the draft reference itself omits a physical page.
        self.assertEqual(run.exhibit_revision, 3)

    def test_dangerous_original_is_not_mistaken_for_verified_quote(self):
        # A change to the untrusted brief is not an alternative verified source.
        # Only the confirmed separate evidence document is in the denominator.
        check = self.check()
        self.assertEqual(len(check.declared), 1)
        self.assertNotEqual(check.declared[0][1], str(self.f.version))


def main() -> None:
    _env()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(M2CheckCompositionTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    print("M2_PRIVATE_MATTER_PERSISTED_CHECK_TO_REVIEW_PASSED")


if __name__ == "__main__":
    main()
