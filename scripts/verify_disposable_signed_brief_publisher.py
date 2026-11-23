"""Disposable SignedBriefPublisher port: real PostgreSQL contract tests.

Runs only against the isolated disposable CI database (127.0.0.1, fixture
password), never a shared Supabase project. Proves the loopback publication
port: deterministic working-brief resolution, revision progression under
optimistic concurrency, stale-revision conflict, document catalog listing
and bearer/grant denial. Synthetic only: proves the loopback port, not
genuine Supabase RLS or IdP identity.
"""

from __future__ import annotations

import unittest
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from application.litigation.brief_checks import DraftReference, VersionedBrief
from application.litigation.exhibit_confirmation import serialized_entries
from application.litigation.unified_review import BriefRepresentation
from apps.api.disposable_litigation_brief_graph import DisposableBriefGraphStore
from apps.api.disposable_signed_brief_publisher import (
    DisposableSignedBriefPublisher,
    working_brief_id,
)
from apps.api.disposable_signed_source_library import DisposableSignedSourceLibrary
from apps.api.evidence_vault_protocol import VaultScope
from apps.api.postgres_litigation_check_store import PostgresPrivateMatterCheckStore
from apps.api.signed_supabase_originals import PrivateStorageDenied
from scripts.verify_document_intake_integration import SyntheticVerifier
from scripts.verify_vault_integration import connect, coordinator, seed

ORIGINAL_V1 = "BRIEF SYNTHETIQUE v1 - aucune affaire reelle. «quote alpha» (Source A)\n".encode()
ORIGINAL_V2 = "BRIEF SYNTHETIQUE v2 - aucune affaire reelle. «quote beta» (Source A)\n".encode()


def extract(text: str) -> list[tuple[str, str, str]]:
    return (
        [("ref-01", "Source A", "quote alpha")]
        if "quote alpha" in text
        else [("ref-01", "Source A", "quote beta")]
    )


def represent(*, case_id, version_id, text, references, original_sha256_hex):
    refs = tuple(DraftReference(rid, label, quote) for rid, label, quote in references)
    brief = VersionedBrief(str(case_id), str(version_id), original_sha256_hex, refs)
    return BriefRepresentation(brief, text, sha256(text.encode()).hexdigest(), "synthetic-utf8-v1", ())


class DisposableSignedBriefPublisherTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = TemporaryDirectory(prefix="caseproof-dsbp-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.f = seed(data=b"placeholder non utilise comme source du brief")
        vault = coordinator(self.root, self.f)
        from scripts.verify_vault_integration import begin

        begin(vault, self.f)
        vault.upload(scope=self.f.scope, intent_id=self.f.intent, data=self.f.data)
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
            encoded = serialized_entries(())
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
        self.publisher = DisposableSignedBriefPublisher(
            connect=connect,
            library=self.library,
            graph=graph,
            verify_bearer=self.verifier.verify_bearer,
            access_lookup=store.current_access,
            extract_references=extract,
            build_representation=represent,
        )
        self.case_id = str(self.f.scope.case_id)

    def _register(self, data: bytes, label: str) -> tuple[str, str]:
        document, version = uuid4(), uuid4()
        with connect() as conn:
            conn.execute(
                "insert into caseproof.documents(id,org_id,case_id,source_label) values(%s,%s,%s,%s)",
                (document, self.f.scope.org_id, self.f.scope.case_id, label),
            )
            conn.execute(
                "insert into caseproof.document_versions(id,org_id,document_id,version_number,"
                "original_sha256_hex,byte_length,media_type) values(%s,%s,%s,1,%s,%s,%s)",
                (version, self.f.scope.org_id, document, sha256(data).hexdigest(), len(data), "text/plain"),
            )
        return str(document), str(version)

    def _upload(self, document_id: str, version_id: str, data: bytes) -> None:
        self.library.put_once(
            bearer="synthetic-fixture-only",
            case_id=self.case_id,
            document_id=document_id,
            version_id=version_id,
            data=data,
        )

    def test_publish_progresses_revisions_on_working_brief(self) -> None:
        d1, v1 = self._register(ORIGINAL_V1, "brief v1")
        d2, v2 = self._register(ORIGINAL_V2, "brief v2")
        self._upload(d1, v1, ORIGINAL_V1)
        self._upload(d2, v2, ORIGINAL_V2)
        first = self.publisher.publish_uploaded(
            bearer="synthetic-fixture-only",
            case_id=self.case_id,
            document_id=d1,
            version_id=v1,
            document_role="own_draft",
            expected_revision=0,
        )
        self.assertEqual(first.published_revision, 1)
        self.assertEqual(first.brief_id, str(working_brief_id(self.case_id, "own_draft")))
        second = self.publisher.publish_uploaded(
            bearer="synthetic-fixture-only",
            case_id=self.case_id,
            document_id=d2,
            version_id=v2,
            document_role="own_draft",
            expected_revision=1,
        )
        self.assertEqual(second.published_revision, 2)
        self.assertEqual(second.brief_id, first.brief_id)
        self.assertNotEqual(second.brief_version_id, first.brief_version_id)

    def test_register_source_version_then_upload_and_publish(self) -> None:
        registration = self.publisher.register_source_version(
            bearer="synthetic-fixture-only",
            case_id=self.case_id,
            label="Source declaree par le signataire",
            media_type="text/plain",
            byte_length=len(ORIGINAL_V1),
            sha256_hex=sha256(ORIGINAL_V1).hexdigest(),
        )
        self._upload(registration.document_id, registration.version_id, ORIGINAL_V1)
        outcome = self.publisher.publish_uploaded(
            bearer="synthetic-fixture-only",
            case_id=self.case_id,
            document_id=registration.document_id,
            version_id=registration.version_id,
            document_role="own_draft",
            expected_revision=0,
        )
        self.assertEqual(outcome.published_revision, 1)
        catalog = self.publisher.list_documents(bearer="synthetic-fixture-only", case_id=self.case_id)
        labels = {d.label for d in catalog}
        self.assertIn("Source declaree par le signataire", labels)

    def test_register_source_version_rejects_bad_digest(self) -> None:
        with self.assertRaises(ValueError):
            self.publisher.register_source_version(
                bearer="synthetic-fixture-only",
                case_id=self.case_id,
                label="digest invalide",
                media_type="text/plain",
                byte_length=10,
                sha256_hex="zz" * 32,
            )

    def test_confirm_exhibit_appends_at_current_revision(self) -> None:
        src = b"SOURCE CONFIRMEE PAR LE SIGNATAIRE. quote beta\n"
        d, v = self._register(src, "source a confirmer")
        self._upload(d, v, src)
        first = self.publisher.confirm_exhibit(
            bearer="synthetic-fixture-only",
            case_id=self.case_id,
            document_id=d,
            version_id=v,
            display_label="Source A",
        )
        self.assertEqual(first.exhibit_revision, 2)
        d2, v2 = self._register(b"AUTRE SOURCE. quote beta\n", "autre source")
        self._upload(d2, v2, b"AUTRE SOURCE. quote beta\n")
        second = self.publisher.confirm_exhibit(
            bearer="synthetic-fixture-only",
            case_id=self.case_id,
            document_id=d2,
            version_id=v2,
            display_label="Source A bis",
        )
        self.assertEqual(second.exhibit_revision, 3)
        self.assertNotEqual(first.exhibit_id, second.exhibit_id)

    def test_confirm_exhibit_unknown_document_masked(self) -> None:
        with self.assertRaises(PrivateStorageDenied):
            self.publisher.confirm_exhibit(
                bearer="synthetic-fixture-only",
                case_id=self.case_id,
                document_id=str(uuid4()),
                version_id=str(uuid4()),
                display_label="inconnue",
            )

    def test_confirm_exhibit_denied_without_grant(self) -> None:
        src = b"SOURCE SANS DROIT. quote beta\n"
        d, v = self._register(src, "source sans droit")
        self._upload(d, v, src)
        with connect() as conn:
            conn.execute(
                "update caseproof._m1_matter_grants "
                "set permissions=array_remove(permissions,'exhibit:confirm') "
                "where case_id=%s and user_id=%s",
                (self.f.scope.case_id, self.f.actor),
            )
        with self.assertRaises(PrivateStorageDenied):
            self.publisher.confirm_exhibit(
                bearer="synthetic-fixture-only",
                case_id=self.case_id,
                document_id=d,
                version_id=v,
                display_label="Source A",
            )

    def test_register_source_version_denied_without_grant(self) -> None:
        with connect() as conn:
            conn.execute(
                "delete from caseproof._m1_matter_grants where case_id=%s and user_id=%s",
                (self.f.scope.case_id, self.f.actor),
            )
        with self.assertRaises(PrivateStorageDenied):
            self.publisher.register_source_version(
                bearer="synthetic-fixture-only",
                case_id=self.case_id,
                label="sans autorisation",
                media_type="text/plain",
                byte_length=len(ORIGINAL_V1),
                sha256_hex=sha256(ORIGINAL_V1).hexdigest(),
            )

    def test_stale_expected_revision_conflicts(self) -> None:
        d1, v1 = self._register(ORIGINAL_V1, "brief v1")
        self._upload(d1, v1, ORIGINAL_V1)
        self.publisher.publish_uploaded(
            bearer="synthetic-fixture-only",
            case_id=self.case_id,
            document_id=d1,
            version_id=v1,
            document_role="own_draft",
            expected_revision=0,
        )
        with self.assertRaises(ValueError):
            self.publisher.publish_uploaded(
                bearer="synthetic-fixture-only",
                case_id=self.case_id,
                document_id=d1,
                version_id=v1,
                document_role="own_draft",
                expected_revision=0,
            )

    def test_publish_before_upload_is_denied(self) -> None:
        d1, v1 = self._register(ORIGINAL_V1, "brief v1")
        with self.assertRaises(PrivateStorageDenied):
            self.publisher.publish_uploaded(
                bearer="synthetic-fixture-only",
                case_id=self.case_id,
                document_id=d1,
                version_id=v1,
                document_role="own_draft",
                expected_revision=0,
            )

    def test_invalid_bearer_denied(self) -> None:
        d1, v1 = self._register(ORIGINAL_V1, "brief v1")
        self._upload(d1, v1, ORIGINAL_V1)
        with self.assertRaises(PrivateStorageDenied):
            self.publisher.publish_uploaded(
                bearer="forged-token",
                case_id=self.case_id,
                document_id=d1,
                version_id=v1,
                document_role="own_draft",
                expected_revision=0,
            )
        with self.assertRaises(PrivateStorageDenied):
            self.publisher.list_documents(bearer="forged-token", case_id=self.case_id)

    def test_catalog_lists_registered_versions(self) -> None:
        d1, v1 = self._register(ORIGINAL_V1, "brief v1")
        catalog = self.publisher.list_documents(bearer="synthetic-fixture-only", case_id=self.case_id)
        found = [d for d in catalog if d.document_id == d1]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].label, "brief v1")
        self.assertEqual(found[0].versions[0].version_id, v1)
        self.assertEqual(found[0].versions[0].sha256_hex, sha256(ORIGINAL_V1).hexdigest())


def main() -> None:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DisposableSignedBriefPublisherTests)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        raise SystemExit("DISPOSABLE_SIGNED_BRIEF_PUBLISHER_FAILED")
    print("DISPOSABLE_SIGNED_BRIEF_PUBLISHER_CONTRACT_PASSED")


if __name__ == "__main__":
    main()
