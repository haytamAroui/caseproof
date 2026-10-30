"""Multi-source intake contract and fail-closed authorization fixtures."""

import pytest

from domains.disputes.multisource_manifest import MultiSourceManifest, SourceItem, SourceRole


def _item(identifier: str, role: SourceRole) -> SourceItem:
    return SourceItem(identifier, role, "a" * 64)


def test_inventory_and_multiple_exhibits() -> None:
    manifest = MultiSourceManifest("matter-1", _item("inventory-v1", SourceRole.INVENTORY), (
        _item("exhibit-1-v1", SourceRole.EXHIBIT),
        _item("exhibit-2-v1", SourceRole.EXHIBIT),
    ))
    assert len(manifest.all_sources) == 3
    manifest.assert_authorized(frozenset({"inventory-v1", "exhibit-1-v1", "exhibit-2-v1"}))


def test_one_unauthorized_exhibit_fails_entire_intake() -> None:
    manifest = MultiSourceManifest("matter-1", _item("inventory-v1", SourceRole.INVENTORY), (
        _item("exhibit-1-v1", SourceRole.EXHIBIT),
        _item("exhibit-2-v1", SourceRole.EXHIBIT),
    ))
    with pytest.raises(PermissionError):
        manifest.assert_authorized(frozenset({"inventory-v1", "exhibit-1-v1"}))


def test_inventory_and_exhibit_cannot_share_version() -> None:
    with pytest.raises(ValueError):
        MultiSourceManifest("matter-1", _item("same", SourceRole.INVENTORY), (_item("same", SourceRole.EXHIBIT),))


def test_wrong_inventory_role_rejected() -> None:
    with pytest.raises(ValueError):
        MultiSourceManifest("matter-1", _item("a", SourceRole.EXHIBIT), (_item("b", SourceRole.EXHIBIT),))


def test_malformed_hash_rejected() -> None:
    with pytest.raises(ValueError):
        SourceItem("a", SourceRole.EXHIBIT, "not-a-hash")
