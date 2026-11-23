"""Disposable SignedReviewReceipt port: real PostgreSQL contract tests.

Runs only against the isolated disposable CI database (127.0.0.1, fixture
password), never a shared Supabase project. Proves the loopback review
receipt port: the exported receipt transcribes the published working-brief
head, the recorded check run (payload digest recomputed) and the recorded
human review decisions (hash chain replayed from genesis). Tampering with a
stored row fails closed; forged bearers and unpublished matters are denied.
Synthetic only: proves the loopback port, not genuine Supabase RLS or IdP
identity.
"""

from __future__ import annotations

import unittest
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import psycopg

from application.litigation.brief_checks import DraftReference, VersionedBrief
from application.litigation.exhibit_confirmation import serialized_entries
from application.litigation.unified_review import BriefRepresentation, ReviewDisposition
from apps.api.disposable_litigation_brief_graph import DisposableBriefGraphStore
from apps.api.disposable_litigation_review_ledger import DisposableM2ReviewLedger
from apps.api.disposable_review_receipt import DisposableSignedReviewReceipt
from apps.api.disposable_signed_brief_publisher import (
    DisposableSignedBriefPublisher,
    working_brief_id,
)
from apps.api.disposable_signed_source_library import DisposableSignedSourceLibrary
from apps.api.evidence_vault_protocol import VaultScope
from apps.api.litigation_check_service import AuthorizedLitigationChecker
from apps.api.litigation_review_workspace import ReviewCommand, SignedReviewWorkspace
from apps.api.postgres_litigation_check_store import PostgresPrivateMatterCheckStore
from apps.api.signed_supabase_originals import PrivateStorageDenied
from domains.disputes.exhibits import ExhibitEntry, ExhibitPage
from scripts.extraction_fixtures import NOW
from scripts.verify_document_intake_integration import SyntheticVerifier
from scripts.verify_m2_brief_graph import add_verified_version, new_binding
from scripts.verify_vault_integration import begin, connect, coordinator, seed

ORIGINAL = "BRIEF SYNTHETIQUE - aucune affaire reelle. «quote alpha» (Source A)\n".encode()


def extract(text: str) -> list[tuple[str, str, str]]:
    return [("ref-01", "Source A", "quote alpha")] if "quote alpha" in text else []


def represent(*, case_id, version_id, text, references, original_sha256_hex):
    refs = tuple(DraftReference(rid, label, quote) for rid, label, quote in references)
    brief = VersionedBrief(str(case_id), str(version_id), original_sha256_hex, refs)
    return BriefRepresentation(brief, text, sha256(text.encode()).hexdigest(), "synthetic-utf8-v1", ())


class DisposableReviewReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = TemporaryDirectory(prefix="caseproof-dsrr-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.f = seed(data=b"placeholder non utilise comme source du brief")
        vault = coordinator(self.root, self.f)
        begin(vault, self.f)
        vault.upload(scope=self.f.scope, intent_id=self.f.intent, data=self.f.data)
        corpus = add_verified_version(self.root, self.f, b"SOURCE A SYNTHETIQUE. quote alpha\n")
        binding = new_binding(corpus)
        entries = (
            ExhibitEntry(
                "piece-1",
                "Source A",
                (ExhibitPage(str(binding.document_id), str(corpus.version), printed_page=1),),
                confirmed=True,
            ),
        )
        encoded = serialized_entries(entries)
        with connect() as conn:
            conn.execute(
                "update caseproof.organization_members "
                "set actions=array['case:read','finding:write','review:request',"
                "'evidence:read']::text[] where org_id=%s and user_id=%s",
                (self.f.scope.org_id, self.f.actor),
            )
            conn.execute(
                "insert into caseproof._m1_matter_grants("
                "org_id,case_id,user_id,role,permissions) "
                "values(%s,%s,%s,'reviewer',array['case:read','draft:check',"
                "'review:request','exhibit:confirm','evidence:read','evidence:upload']::text[])",
                (self.f.scope.org_id, self.f.scope.case_id, self.f.actor),
            )
            conn.execute(
                "select * from caseproof._m1_disposable_confirm_exhibits(%s,%s,%s,0,%s::jsonb,%s)",
                (
                    self.f.actor,
                    self.f.scope.case_id,
                    uuid4(),
                    encoded.decode("utf-8"),
                    sha256(encoded).hexdigest(),
                ),
            ).fetchone()
        store = PostgresPrivateMatterCheckStore.__new__(PostgresPrivateMatterCheckStore)
        store._connect = connect
        self.verifier = SyntheticVerifier(self.f.actor)
        self.library = DisposableSignedSourceLibrary(
            connect=connect,
            byte_store_root=self.root,
            verify_bearer=self.verifier.verify_bearer,
            access_lookup=store.current_access,
        )
        reader = lambda org, case, intent: coordinator(self.root, self.f).read(  # noqa: E731
            scope=VaultScope(org, case), intent_id=intent
        )
        graph = DisposableBriefGraphStore(connect, reader)
        self.check_store = PostgresPrivateMatterCheckStore(connect, graph, reader)
        ledger = DisposableM2ReviewLedger(connect)
        self.service = AuthorizedLitigationChecker(
            verifier=self.verifier,
            store=self.check_store,
            publisher=ledger,
            issuer="synthetic-issuer",
            audience="authenticated",
            clock=lambda: NOW + timedelta(minutes=1),
        )
        self.workspace = SignedReviewWorkspace(self.service, ledger)
        self.publisher = DisposableSignedBriefPublisher(
            connect=connect,
            library=self.library,
            graph=graph,
            verify_bearer=self.verifier.verify_bearer,
            access_lookup=store.current_access,
            extract_references=extract,
            build_representation=represent,
        )
        self.receipts = DisposableSignedReviewReceipt(
            connect=connect,
            verify_bearer=self.verifier.verify_bearer,
            access_lookup=store.current_access,
        )
        self.case_id = str(self.f.scope.case_id)

    def _publish_checked_reviewed(self) -> str:
        document, version = uuid4(), uuid4()
        with connect() as conn:
            conn.execute(
                "insert into caseproof.documents(id,org_id,case_id,source_label) values(%s,%s,%s,%s)",
                (document, self.f.scope.org_id, self.f.scope.case_id, "brief v1"),
            )
            conn.execute(
                "insert into caseproof.document_versions(id,org_id,document_id,version_number,"
                "original_sha256_hex,byte_length,media_type) values(%s,%s,%s,1,%s,%s,%s)",
                (
                    version,
                    self.f.scope.org_id,
                    document,
                    sha256(ORIGINAL).hexdigest(),
                    len(ORIGINAL),
                    "text/plain",
                ),
            )
        self.library.put_once(
            bearer="synthetic-fixture-only",
            case_id=self.case_id,
            document_id=str(document),
            version_id=str(version),
            data=ORIGINAL,
        )
        outcome = self.publisher.publish_uploaded(
            bearer="synthetic-fixture-only",
            case_id=self.case_id,
            document_id=str(document),
            version_id=str(version),
            document_role="own_draft",
            expected_revision=0,
        )
        run = self.service.check(
            bearer="synthetic-fixture-only",
            case_id=self.case_id,
            brief_version_id=outcome.brief_version_id,
        )
        self.workspace.record(
            bearer="synthetic-fixture-only",
            case_id=self.case_id,
            brief_version_id=outcome.brief_version_id,
            command=ReviewCommand(
                snapshot_hash=run.snapshot_hash,
                observation_id="citation:ref-01",
                request_id=uuid4(),
                expected_revision=0,
                disposition=ReviewDisposition.CONFIRMED,
                rationale="Synthetic contract review; no legal approval",
            ),
        )
        return outcome.brief_version_id

    def test_receipt_transcribes_head_check_and_review(self) -> None:
        brief_version_id = self._publish_checked_reviewed()
        body = self.receipts.receipt(
            bearer="synthetic-fixture-only", case_id=self.case_id, document_role="own_draft"
        )
        self.assertEqual(body["schema"], "caseproof-review-receipt-v1")
        self.assertEqual(body["case_id"], self.case_id)
        brief = body["brief"]
        self.assertEqual(brief["brief_id"], str(working_brief_id(self.case_id, "own_draft")))
        self.assertEqual(brief["head_revision"], 1)
        self.assertEqual(brief["head_version_id"], brief_version_id)
        self.assertEqual(brief["original_sha256"], sha256(ORIGINAL).hexdigest())
        self.assertEqual(len(body["checks"]), 1)
        self.assertTrue(body["checks"][0]["payload_sha256_verified"])
        self.assertEqual(len(body["reviews"]), 1)
        review = body["reviews"][0]
        self.assertTrue(review["chain_verified"])
        self.assertEqual(review["snapshot_sha256"], body["checks"][0]["snapshot_sha256"])
        self.assertEqual(len(review["decisions"]), 1)
        decision = review["decisions"][0]["decision"]
        self.assertEqual(decision["observation_id"], "citation:ref-01")
        self.assertEqual(decision["disposition"], "confirmed_candidate")
        self.assertRegex(body["receipt_sha256"], r"^[0-9a-f]{64}$")

    def test_receipt_before_publication_is_denied(self) -> None:
        with self.assertRaises(PrivateStorageDenied):
            self.receipts.receipt(
                bearer="synthetic-fixture-only", case_id=self.case_id, document_role="own_draft"
            )

    def test_forged_bearer_is_denied(self) -> None:
        self._publish_checked_reviewed()
        with self.assertRaises(PrivateStorageDenied):
            self.receipts.receipt(bearer="forged-token", case_id=self.case_id, document_role="own_draft")

    def test_recorded_history_is_immutable(self) -> None:
        # The store itself denies mutation of recorded runs and review events;
        # the receipt's digest/chain re-verification is defense in depth.
        self._publish_checked_reviewed()
        with self.assertRaises(psycopg.Error), connect() as conn:
            conn.execute(
                "update caseproof._m2_review_events set decision='tampered' where org_id=%s and case_id=%s",
                (self.f.scope.org_id, self.f.scope.case_id),
            )
        with self.assertRaises(psycopg.Error), connect() as conn:
            conn.execute(
                "update caseproof._m2_check_runs set payload='tampered' where org_id=%s and case_id=%s",
                (self.f.scope.org_id, self.f.scope.case_id),
            )
        with self.assertRaises(psycopg.Error), connect() as conn:
            conn.execute(
                "delete from caseproof._m2_review_events where org_id=%s and case_id=%s",
                (self.f.scope.org_id, self.f.scope.case_id),
            )
        body = self.receipts.receipt(
            bearer="synthetic-fixture-only", case_id=self.case_id, document_role="own_draft"
        )
        self.assertEqual(len(body["reviews"]), 1)
        self.assertTrue(body["reviews"][0]["chain_verified"])


def main() -> None:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DisposableReviewReceiptTests)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        raise SystemExit("DISPOSABLE_REVIEW_RECEIPT_FAILED")
    print("DISPOSABLE_REVIEW_RECEIPT_CONTRACT_PASSED")


if __name__ == "__main__":
    main()
