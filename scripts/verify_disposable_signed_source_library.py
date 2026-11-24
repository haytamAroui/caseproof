"""Disposable SignedSourceLibrary port: real PostgreSQL contract tests.

Runs only against the isolated disposable CI database (127.0.0.1, fixture
password), never a shared Supabase project. Mirrors the failure semantics
of the remote SignedSourceLibrary: masked/denied authorization, put-once
immutability, digest enforcement and verified readback. Synthetic only:
proves the loopback port, not genuine Supabase RLS or IdP identity.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from apps.api.disposable_signed_source_library import DisposableSignedSourceLibrary
from apps.api.postgres_litigation_check_store import PostgresPrivateMatterCheckStore
from apps.api.signed_supabase_originals import (
    PrivateStorageDenied,
    PrivateStorageExists,
    PrivateStorageIntegrityError,
)
from scripts.verify_document_intake_integration import SyntheticVerifier
from scripts.verify_vault_integration import connect, seed

ORIGINAL = b"CONTRAT SYNTHETIQUE DE DEMONSTRATION - aucune affaire reelle.\n"
REPLACEMENT = b"AUTRE CONTENU SYNTHETIQUE - ne doit jamais remplacer.\n"


class DisposableSignedSourceLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = TemporaryDirectory(prefix="caseproof-dssl-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        # Pre-registered version: declared digest/length/mime, NO bytes yet.
        self.f = seed(data=ORIGINAL)
        self.other_actor = uuid4()
        with connect() as conn:
            conn.execute(
                "insert into auth.users(id,instance_id) values(%s,%s)",
                (self.other_actor, uuid4()),
            )
            conn.execute(
                "insert into caseproof.organization_members(org_id,user_id,actions) values(%s,%s,%s)",
                (self.f.scope.org_id, self.other_actor, ["case:read", "finding:write", "evidence:read"]),
            )
            conn.execute(
                "update caseproof.organization_members "
                "set actions=array['case:read','finding:write','review:request',"
                "'evidence:read']::text[] "
                "where org_id=%s and user_id=%s",
                (self.f.scope.org_id, self.f.actor),
            )
            conn.execute(
                "insert into caseproof._m1_matter_grants("
                "org_id,case_id,user_id,role,permissions) "
                "values(%s,%s,%s,'reviewer',array['case:read','draft:check',"
                "'evidence:read','evidence:upload']::text[])",
                (self.f.scope.org_id, self.f.scope.case_id, self.f.actor),
            )
        store = PostgresPrivateMatterCheckStore.__new__(PostgresPrivateMatterCheckStore)
        store._connect = connect
        verifier = SyntheticVerifier(self.f.actor)
        self.library = DisposableSignedSourceLibrary(
            connect=connect,
            byte_store_root=self.root,
            verify_bearer=verifier.verify_bearer,
            access_lookup=store.current_access,
        )
        self.kwargs = {
            "case_id": str(self.f.scope.case_id),
            "document_id": self._document_id(),
            "version_id": str(self.f.version),
        }

    def _document_id(self) -> str:
        with connect() as conn:
            return str(
                conn.execute(
                    "select document_id from caseproof.document_versions where id=%s",
                    (self.f.version,),
                ).fetchone()[0]
            )

    def test_put_once_then_read_roundtrip(self) -> None:
        self.library.put_once(bearer="synthetic-fixture-only", data=ORIGINAL, **self.kwargs)
        self.assertEqual(self.library.read(bearer="synthetic-fixture-only", **self.kwargs), ORIGINAL)

    def test_read_before_any_upload_is_denied(self) -> None:
        with self.assertRaises(PrivateStorageDenied):
            self.library.read(bearer="synthetic-fixture-only", **self.kwargs)

    def test_invalid_bearer_denied(self) -> None:
        with self.assertRaises(PrivateStorageDenied):
            self.library.put_once(bearer="forged-token", data=ORIGINAL, **self.kwargs)

    def test_actor_without_matter_grant_denied(self) -> None:
        # Same organization membership, but no matter grant for this case.
        store = PostgresPrivateMatterCheckStore.__new__(PostgresPrivateMatterCheckStore)
        store._connect = connect
        verifier = SyntheticVerifier(self.other_actor)
        foreign = DisposableSignedSourceLibrary(
            connect=connect,
            byte_store_root=self.root,
            verify_bearer=verifier.verify_bearer,
            access_lookup=store.current_access,
        )
        with self.assertRaises(PrivateStorageDenied):
            foreign.put_once(bearer="synthetic-fixture-only", data=ORIGINAL, **self.kwargs)

    def test_digest_mismatch_rejected_before_write(self) -> None:
        with self.assertRaises(PrivateStorageIntegrityError):
            self.library.put_once(
                bearer="synthetic-fixture-only",
                data=ORIGINAL + b"modification",
                **self.kwargs,
            )
        with self.assertRaises(PrivateStorageDenied):
            self.library.read(bearer="synthetic-fixture-only", **self.kwargs)

    def test_no_overwrite_after_commit(self) -> None:
        self.library.put_once(bearer="synthetic-fixture-only", data=ORIGINAL, **self.kwargs)
        with self.assertRaises(PrivateStorageExists):
            self.library.put_once(bearer="synthetic-fixture-only", data=ORIGINAL, **self.kwargs)
        self.assertEqual(self.library.read(bearer="synthetic-fixture-only", **self.kwargs), ORIGINAL)


def main() -> None:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DisposableSignedSourceLibraryTests)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        raise SystemExit("DISPOSABLE_SIGNED_SOURCE_LIBRARY_FAILED")
    print("DISPOSABLE_SIGNED_SOURCE_LIBRARY_CONTRACT_PASSED")


if __name__ == "__main__":
    main()
