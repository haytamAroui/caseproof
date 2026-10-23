"""Local private vault storage integration and adversarial filesystem tests."""

import hashlib
import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from apps.api.evidence_vault_protocol import (
    VaultCoordinator, VaultScope, VaultState, VaultUnavailable,
)
from apps.api.private_filesystem_byte_store import (
    PrivateFilesystemByteStore, PrivateObjectConflict,
)
from test_s2_009a_vault_protocol import FakeAtomicLedger

ORG = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CASE = UUID("aaaaaaaa-1111-4111-8111-111111111111")
DATA = b"%PDF-1.7\nsynthetic document\n"


def key() -> str:
    return f"org/{ORG.hex}/case/{CASE.hex}/sources/{uuid4().hex}"


def test_immutable_bytes_survive_adapter_restart(tmp_path: Path) -> None:
    root = tmp_path / "private"
    store = PrivateFilesystemByteStore(root)
    object_key = key()
    store.put_once(object_key, DATA)
    assert PrivateFilesystemByteStore(root).read_exact(object_key) == DATA
    with pytest.raises(PrivateObjectConflict):
        store.put_once(object_key, b"replacement")
    assert store.read_exact(object_key) == DATA
    assert not (root / "public").exists()


@pytest.mark.parametrize("bad_key", [
    "../outside", "/tmp/object", "org/a/case/b/sources/c",
    "org/" + "a" * 32 + "/case/" + "b" * 32 + "/sources/../evil",
])
def test_invalid_keys_never_write(tmp_path: Path, bad_key: str) -> None:
    store = PrivateFilesystemByteStore(tmp_path / "private")
    with pytest.raises(ValueError):
        store.put_once(bad_key, DATA)


def test_symlink_in_parent_chain_rejected(tmp_path: Path) -> None:
    store = PrivateFilesystemByteStore(tmp_path / "private")
    (store.root / "org").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(OSError):
        store.put_once(key(), DATA)


def test_untrusted_object_symlink_rejected(tmp_path: Path) -> None:
    store = PrivateFilesystemByteStore(tmp_path / "private")
    object_key = key()
    store.put_once(object_key, DATA)
    object_path = store.root.joinpath(*object_key.split("/"))
    object_path.unlink()
    object_path.symlink_to(tmp_path / "secret")
    with pytest.raises(OSError):
        store.read_exact(object_key)


def test_coordinator_readback_and_tamper_detection(tmp_path: Path) -> None:
    store = PrivateFilesystemByteStore(tmp_path / "private")
    ledger = FakeAtomicLedger()
    coordinator = VaultCoordinator(store=store, ledger=ledger)
    scope = VaultScope(ORG, CASE)
    intent_id = uuid4()
    intent = coordinator.begin(
        scope=scope, intent_id=intent_id,
        sha256_hex=hashlib.sha256(DATA).hexdigest(),
        byte_length=len(DATA), media_type="application/pdf",
    )
    assert coordinator.upload(scope=scope, intent_id=intent_id, data=DATA).state == VaultState.VERIFIED
    assert coordinator.read(scope=scope, intent_id=intent_id) == DATA
    obj = store.root.joinpath(*intent.object_key.split("/"))
    obj.write_bytes(b"tampered")
    with pytest.raises(VaultUnavailable):
        coordinator.read(scope=scope, intent_id=intent_id)
    assert ledger.get_scoped(scope, intent_id).state == VaultState.UNAVAILABLE


def test_wrong_tenant_cannot_retrieve_even_known_object_key(tmp_path: Path) -> None:
    from apps.api.evidence_vault_protocol import VaultMissing
    store = PrivateFilesystemByteStore(tmp_path / "private")
    coordinator = VaultCoordinator(store=store, ledger=FakeAtomicLedger())
    scope = VaultScope(ORG, CASE)
    intent_id = uuid4()
    coordinator.begin(scope=scope, intent_id=intent_id,
        sha256_hex=hashlib.sha256(DATA).hexdigest(),
        byte_length=len(DATA), media_type="application/pdf")
    coordinator.upload(scope=scope, intent_id=intent_id, data=DATA)
    with pytest.raises(VaultMissing):
        coordinator.read(scope=VaultScope(uuid4(), CASE), intent_id=intent_id)
