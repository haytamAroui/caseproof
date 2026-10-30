"""Signed multi-source readback: complete success or fail closed."""

from hashlib import sha256

import pytest

from domains.disputes.multisource_manifest import MultiSourceManifest, SourceItem, SourceRole
from infrastructure.supabase.multisource_readback import verify_multisource_originals


def _item(identifier: str, role: SourceRole, payload: bytes) -> SourceItem:
    return SourceItem(identifier, role, sha256(payload).hexdigest())


def _manifest() -> tuple[MultiSourceManifest, dict[str, bytes]]:
    data = {"inventory": b"Inventory: Stuk 1, Stuk 2", "one": b"%PDF-one", "two": b"%PDF-two"}
    manifest = MultiSourceManifest("matter", _item("inventory", SourceRole.INVENTORY, data["inventory"]), (
        _item("one", SourceRole.EXHIBIT, data["one"]),
        _item("two", SourceRole.EXHIBIT, data["two"]),
    ))
    return manifest, data


def test_all_three_signed_sources_are_verified() -> None:
    manifest, data = _manifest()
    calls: list[tuple[str, str]] = []

    def read(matter: str, version: str) -> bytes:
        calls.append((matter, version))
        return data[version]

    result = verify_multisource_originals(manifest, authorized_version_ids=frozenset(data), signed_read_original=read)
    assert len(result) == 3
    assert calls == [("matter", "inventory"), ("matter", "one"), ("matter", "two")]


def test_one_tampered_exhibit_fails_whole_readback() -> None:
    manifest, data = _manifest()
    data["two"] = b"tampered"
    with pytest.raises(ValueError, match="SHA-256"):
        verify_multisource_originals(manifest, authorized_version_ids=frozenset(data), signed_read_original=lambda matter, version: data[version])


def test_revoked_exhibit_is_not_read() -> None:
    manifest, data = _manifest()
    calls: list[str] = []

    def read(matter: str, version: str) -> bytes:
        calls.append(version)
        return data[version]

    with pytest.raises(PermissionError):
        verify_multisource_originals(manifest, authorized_version_ids=frozenset({"inventory", "one"}), signed_read_original=read)
    assert calls == []


def test_signed_reader_denial_propagates() -> None:
    manifest, data = _manifest()

    def read(matter: str, version: str) -> bytes:
        if version == "two":
            raise PermissionError("revoked")
        return data[version]

    with pytest.raises(PermissionError):
        verify_multisource_originals(manifest, authorized_version_ids=frozenset(data), signed_read_original=read)
