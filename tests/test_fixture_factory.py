"""Offline contract tests for synthetic evidence fixtures."""
from __future__ import annotations

import base64
import hashlib
import json
from unittest.mock import patch

from tests.fixtures.factory import FixtureFactory, SyntheticSource


def test_source_metadata_sha_is_from_exact_original() -> None:
    source = SyntheticSource("stuk-1.pdf", "exhibit", "application/pdf", b"fake")
    assert source.metadata()["sha256"] == hashlib.sha256(b"fake").hexdigest()
    assert source.metadata()["byte_length"] == 4


def test_signed_bundle_uses_registered_versions_and_verified_uploads() -> None:
    source = SyntheticSource("draft.docx", "draft", "application/octet-stream", b"synthetic")
    calls = []

    def api(token, method, path, payload):
        calls.append((token, method, path, payload))
        if path == "/dev/live/matters":
            return {"case_id": "case-test"}
        assert path == "/dev/live/matters/case-test/sources/doc-test/ver-test/upload"
        assert base64.b64decode(payload["content_base64"]) == source.content
        return {"verified": True}

    def rpc(token, key, path, method, payload):
        assert token == "signed-owner"
        assert key == "publishable"
        assert path == "/rest/v1/rpc/caseproof_dev_register_bundle"
        assert payload["p_sources"] == [source.metadata()]
        return 200, json.dumps({"sources": [
            {"document_id": "doc-test", "version_id": "ver-test"}
        ]}).encode()

    with patch("tests.fixtures.factory.generate_bundle", return_value=(source,)):
        result = FixtureFactory(api=api, rpc=rpc, publishable_key="publishable").create_bundle(
            "signed-owner", "org-test"
        )
    assert result.matter_id == "case-test"
    assert result.sources == (("draft.docx", "doc-test", "ver-test"),)
    assert all(call[0] == "signed-owner" for call in calls)


def test_unverified_upload_fails_closed() -> None:
    source = SyntheticSource("scan.pdf", "exhibit", "application/pdf", b"synthetic")

    def api(_token, _method, path, _payload):
        return {"case_id": "case"} if path == "/dev/live/matters" else {"verified": False}

    def rpc(*_args):
        return 200, b'{"sources":[{"document_id":"doc","version_id":"ver"}]}'

    import pytest

    with patch("tests.fixtures.factory.generate_bundle", return_value=(source,)):
        with pytest.raises(RuntimeError, match="fixture_original_hash_unverified"):
            FixtureFactory(api=api, rpc=rpc, publishable_key="key").create_bundle("token", "org")
