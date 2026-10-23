"""Real disposable PostgreSQL + private filesystem Vault integration.

Run AFTER verify_s2_009b_database in the ephemeral CI service. Synthetic
actors and an isolated postgres owner are NOT production authentication/RLS.
No remote service, migration, HTTP route or customer document is used.
Missing dependencies/database fail the command; nothing is skipped.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from uuid import UUID, uuid4

import psycopg

from apps.api.disposable_postgres_vault_ledger import (
    COMMAND_SQL,
    DisposablePostgresVaultLedger,
    DisposableVaultActorContext,
)
from apps.api.evidence_vault_protocol import (
    VaultConflict,
    VaultCoordinator,
    VaultMissing,
    VaultScope,
    VaultState,
    VaultUnavailable,
    VaultUnknownOutcome,
)
from apps.api.private_filesystem_byte_store import PrivateFilesystemByteStore
from scripts.verify_s2_007_disposable_tenancy import _isolated_postgres_env

SYNTHETIC_SOURCE = b"Synthetic invoice: net EUR 1150.00\n"

def connect(*, cursor_factory=psycopg.Cursor):
    # Reuse the existing fail-closed disposable guard, and explicitly override
    # libpq service/options/address settings rather than inheriting PG* values.
    env = _isolated_postgres_env()
    allowed = {"PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD", "PGCONNECT_TIMEOUT"}
    if any(key.startswith("PG") and key not in allowed for key in os.environ):
        raise RuntimeError("Unexpected libpq environment override")
    return psycopg.connect(
        host=env["PGHOST"], hostaddr=env["PGHOST"], port=env["PGPORT"],
        dbname=env["PGDATABASE"], user=env["PGUSER"], password=env["PGPASSWORD"],
        options="", sslmode="disable", connect_timeout=5,
        cursor_factory=cursor_factory,
    )


@dataclass(frozen=True)
class Fixture:
    scope: VaultScope
    actor: UUID
    version: UUID
    intent: UUID
    data: bytes = SYNTHETIC_SOURCE

    @property
    def digest(self):
        return sha256(self.data).hexdigest()


def seed(*, data: bytes = SYNTHETIC_SOURCE):
    """Fresh tenant/case/version with digest of ACTUAL synthetic source bytes."""
    f = Fixture(VaultScope(uuid4(), uuid4()), uuid4(), uuid4(), uuid4(), data)
    document = uuid4()
    with connect() as conn:
        conn.execute(
            "insert into auth.users(id,instance_id) values(%s,%s)",
            (f.actor, UUID(int=1)),
        )
        conn.execute(
            "insert into caseproof.organizations(id,display_name) values(%s,%s)",
            (f.scope.org_id, "Disposable Vault integration"),
        )
        conn.execute(
            "insert into caseproof.organization_members(org_id,user_id,actions) "
            "values(%s,%s,%s)",
            (f.scope.org_id, f.actor, ["case:read", "finding:write"]),
        )
        conn.execute(
            "insert into caseproof.cases(id,org_id,created_by_user,effective_policy_version) "
            "values(%s,%s,%s,%s)",
            (f.scope.case_id, f.scope.org_id, f.actor, "vault-integration-v1"),
        )
        conn.execute(
            "insert into caseproof.documents(id,org_id,case_id,source_label) values(%s,%s,%s,%s)",
            (document, f.scope.org_id, f.scope.case_id, "synthetic-source"),
        )
        conn.execute(
            "insert into caseproof.document_versions(id,org_id,document_id,version_number,"
            "original_sha256_hex,byte_length,media_type) values(%s,%s,%s,1,%s,%s,%s)",
            (f.version, f.scope.org_id, document, f.digest, len(f.data), "text/plain"),
        )
    return f


def ledger(f, factory=connect):
    return DisposablePostgresVaultLedger(
        factory, DisposableVaultActorContext(f.actor, f.version),
    )


def coordinator(root, f, factory=connect):
    return VaultCoordinator(store=PrivateFilesystemByteStore(root), ledger=ledger(f, factory))


def begin(vault, f):
    return vault.begin(
        scope=f.scope, intent_id=f.intent, sha256_hex=f.digest,
        byte_length=len(f.data), media_type="text/plain",
    )


def snapshot(f):
    """Independent committed connection: aggregate + atomic side effects."""
    with connect() as conn:
        revision = conn.execute(
            "select case_revision from caseproof.cases where org_id=%s and id=%s",
            (f.scope.org_id, f.scope.case_id),
        ).fetchone()[0]
        counts = []
        for table in (
            "audit_events", "idempotency_records", "_s2_009b_availability_events",
            "_s2_009b_vault_intents",
        ):
            # Identifiers are hardcoded fixture names, values are parameterized.
            from psycopg import sql

            counts.append(conn.execute(
                sql.SQL("select count(*) from caseproof.{} where org_id=%s and case_id=%s")
                .format(sql.Identifier(table)), (f.scope.org_id, f.scope.case_id),
            ).fetchone()[0])
    return (revision, *counts)


def recover_in_new_process(root, f):
    """No coordinator, connection, store or in-memory receipt crosses restart."""
    manifest = root / "restart-fixture.json"
    manifest.write_text(json.dumps({
        "root": str(root), "org": str(f.scope.org_id), "case": str(f.scope.case_id),
        "actor": str(f.actor), "version": str(f.version), "intent": str(f.intent),
    }), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "scripts.verify_vault_integration", "--recover", str(manifest)],
        text=True, capture_output=True, timeout=30, check=False,
    )
    if result.returncode != 0 or result.stdout.strip() != "VAULT_RESTART_RECOVERY_PASSED":
        raise AssertionError("Separate-process Vault recovery failed: " + result.stderr[:1500])


class AuditFailureCursor(psycopg.Cursor):
    """Inject the existing SQL proposal's audit fault through a REAL driver."""

    def execute(self, query, params=None, *, prepare=None, binary=None):
        if query == COMMAND_SQL:
            query = query.replace("p_fault => null", "p_fault => 'audit'")
        return super().execute(query, params, prepare=prepare, binary=binary)


class LostAcknowledgmentLedger(DisposablePostgresVaultLedger):
    def publish_verified(self, expected):
        super().publish_verified(expected)  # Actual DB commit happens first.
        raise ConnectionError("Injected loss of committed publication acknowledgment")


class VaultIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="caseproof-vault-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.f = seed()
        self.vault = coordinator(self.root, self.f)

    def upload(self, vault=None, fixture=None):
        vault, f = vault or self.vault, fixture or self.f
        intent = begin(vault, f)
        result = vault.upload(scope=f.scope, intent_id=f.intent, data=f.data)
        self.assertEqual(result.state, VaultState.VERIFIED)
        return intent, result

    def test_two_tenants_positive_reads_then_foreign_scope_denial(self):
        other = seed()
        other_vault = coordinator(self.root, other)
        self.upload()
        self.upload(other_vault, other)
        for f, vault in ((self.f, self.vault), (other, other_vault)):
            self.assertEqual(vault.read(scope=f.scope, intent_id=f.intent), f.data)
        before = snapshot(self.f)
        for scope in (other.scope, VaultScope(other.scope.org_id, self.f.scope.case_id)):
            with self.assertRaises(VaultMissing):
                other_vault.read(scope=scope, intent_id=self.f.intent)
        with self.assertRaises(VaultMissing):
            self.vault.read(scope=self.f.scope, intent_id=other.intent)
        self.assertEqual(snapshot(self.f), before)
        # Scope-filtering proof under a fixture owner, NOT runtime Auth/RLS proof.

    def test_pending_bytes_recovered_in_separate_process(self):
        intent = begin(self.vault, self.f)
        self.assertEqual(snapshot(self.f), (2, 1, 1, 0, 1))
        with self.assertRaises(VaultUnavailable):
            self.vault.read(scope=self.f.scope, intent_id=self.f.intent)
        pending = self.vault.reconcile_pending(scope=self.f.scope, intent_id=self.f.intent)
        self.assertEqual(pending.state, VaultState.PENDING)
        # Crash boundary: original PUT reached disk, DB publish has not happened.
        PrivateFilesystemByteStore(self.root).put_once(intent.object_key, self.f.data)
        recover_in_new_process(self.root, self.f)
        self.assertEqual(snapshot(self.f), (3, 2, 2, 1, 1))
        self.assertEqual(self.vault.read(scope=self.f.scope, intent_id=self.f.intent), self.f.data)

    def test_stable_retry_preserves_key_and_exactly_once_effects(self):
        intent, _ = self.upload()
        before = snapshot(self.f)
        for _ in range(2):
            self.assertEqual(begin(coordinator(self.root, self.f), self.f), intent)
            recover_in_new_process(self.root, self.f)
        self.assertEqual(snapshot(self.f), before)
        with self.assertRaises(VaultConflict):
            self.vault.begin(
                scope=self.f.scope, intent_id=self.f.intent, sha256_hex="b" * 64,
                byte_length=len(self.f.data), media_type="text/plain",
            )
        with self.assertRaises(VaultConflict):
            self.vault.upload(scope=self.f.scope, intent_id=self.f.intent, data=self.f.data)
        self.assertEqual(snapshot(self.f), before)

    def test_missing_and_corrupt_bytes_append_one_audited_invalidation(self):
        for reason in ("missing", "digest_mismatch"):
            with self.subTest(reason=reason):
                f = seed()
                vault = coordinator(self.root, f)
                intent, _ = self.upload(vault, f)
                path = self.root / intent.object_key
                before = snapshot(f)
                if reason == "missing":
                    path.unlink()
                else:
                    path.write_bytes(b"x" * len(f.data))  # same length, wrong digest
                with self.assertRaises(VaultUnavailable):
                    vault.read(scope=f.scope, intent_id=f.intent)
                self.assertEqual(snapshot(f), tuple(a + b for a, b in zip(
                    before, (1, 1, 1, 1, 0), strict=True,
                )))
                with connect() as conn:
                    self.assertEqual(conn.execute(
                        "select status,reason from caseproof._s2_009b_availability_events "
                        "where org_id=%s and case_id=%s order by intent_revision desc limit 1",
                        (f.scope.org_id, f.scope.case_id),
                    ).fetchone(), ("unavailable", reason))
                after = snapshot(f)
                with self.assertRaises(VaultUnavailable):
                    coordinator(self.root, f).read(scope=f.scope, intent_id=f.intent)
                self.assertEqual(snapshot(f), after)

    def test_audit_failure_rolls_back_publication_and_retains_pending_bytes(self):
        intent = begin(self.vault, self.f)
        before = snapshot(self.f)
        faulty = coordinator(self.root, self.f, lambda: connect(cursor_factory=AuditFailureCursor))
        with self.assertRaises(VaultUnknownOutcome):
            faulty.upload(scope=self.f.scope, intent_id=self.f.intent, data=self.f.data)
        self.assertEqual(snapshot(self.f), before)
        self.assertEqual(PrivateFilesystemByteStore(self.root).read_exact(intent.object_key), self.f.data)
        with self.assertRaises(VaultUnavailable):
            self.vault.read(scope=self.f.scope, intent_id=self.f.intent)
        recover_in_new_process(self.root, self.f)
        self.assertEqual(snapshot(self.f), (3, 2, 2, 1, 1))

    def test_lost_commit_ack_reconciles_without_second_publication(self):
        lost = LostAcknowledgmentLedger(
            connect, DisposableVaultActorContext(self.f.actor, self.f.version),
        )
        vault = VaultCoordinator(store=PrivateFilesystemByteStore(self.root), ledger=lost)
        begin(vault, self.f)
        with self.assertRaises(VaultUnknownOutcome):
            vault.upload(scope=self.f.scope, intent_id=self.f.intent, data=self.f.data)
        before = snapshot(self.f)
        self.assertEqual(before, (3, 2, 2, 1, 1))
        recover_in_new_process(self.root, self.f)
        self.assertEqual(snapshot(self.f), before)

    def test_concurrent_publications_replay_one_committed_receipt(self):
        intent = begin(self.vault, self.f)
        store = PrivateFilesystemByteStore(self.root)
        store.put_once(intent.object_key, self.f.data)
        self.assertEqual(store.read_exact(intent.object_key), self.f.data)
        pending = ledger(self.f).get_scoped(self.f.scope, self.f.intent)
        before = snapshot(self.f)
        barrier = Barrier(2)

        def publish():
            barrier.wait(timeout=10)
            return ledger(self.f).publish_verified(pending)

        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = list(pool.map(lambda _: publish(), range(2)))
        self.assertEqual(first, second)
        self.assertEqual(first.state, VaultState.VERIFIED)
        self.assertEqual(snapshot(self.f), tuple(a + b for a, b in zip(
            before, (1, 1, 1, 1, 0), strict=True,
        )))

    def test_revoked_actor_cannot_publish_pending_bytes(self):
        intent = begin(self.vault, self.f)
        with connect() as conn:
            conn.execute(
                "update caseproof.organization_members set active=false "
                "where org_id=%s and user_id=%s", (self.f.scope.org_id, self.f.actor),
            )
        before = snapshot(self.f)
        with self.assertRaises(VaultUnknownOutcome):
            self.vault.upload(scope=self.f.scope, intent_id=self.f.intent, data=self.f.data)
        self.assertEqual(snapshot(self.f), before)
        # This test intentionally exposes the reference limitation: the writer
        # rejects revoked membership, but byte dispatch precedes that DB check.
        # Real pre-dispatch authorization is still a customer-release blocker.
        self.assertEqual(PrivateFilesystemByteStore(self.root).read_exact(intent.object_key), self.f.data)
        with self.assertRaises(VaultUnavailable):
            self.vault.read(scope=self.f.scope, intent_id=self.f.intent)


def recover(manifest):
    payload = json.loads(Path(manifest).read_text(encoding="utf-8"))
    f = Fixture(
        VaultScope(UUID(payload["org"]), UUID(payload["case"])),
        UUID(payload["actor"]), UUID(payload["version"]), UUID(payload["intent"]),
    )
    vault = coordinator(Path(payload["root"]), f)
    result = vault.reconcile_pending(scope=f.scope, intent_id=f.intent)
    if result.state != VaultState.VERIFIED or vault.read(scope=f.scope, intent_id=f.intent) != f.data:
        raise AssertionError("Restart did not restore exact verified bytes")
    print("VAULT_RESTART_RECOVERY_PASSED")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--recover":
        recover(sys.argv[2])
    else:
        unittest.main(verbosity=2)
