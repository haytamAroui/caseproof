"""Regression tests for the protected development multi-source probe."""
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pypdf import PdfReader

from scripts import verify_dev_live_multisource as probe


def test_synthetic_pdf_sources_have_valid_text_and_image_only_pages():
    sources = probe._sources()
    assert sources[0][0].endswith(".docx")
    assert sources[1][2].endswith(b"\n")
    for _, _, payload in sources[2:]:
        reader = PdfReader(BytesIO(payload), strict=True)
        assert len(reader.pages) == 1
    assert "invoice EUR 1250" in PdfReader(BytesIO(sources[2][2]), strict=True).pages[0].extract_text()
    assert not PdfReader(BytesIO(sources[3][2]), strict=True).pages[0].extract_text().strip()


def test_restart_failure_still_cleans_every_uploaded_object(monkeypatch):
    actors = [str(uuid4()) for _ in range(3)]
    sessions = [SimpleNamespace(user_id=a, access_token=f"token-{i}") for i, a in enumerate(actors)]
    org, case = str(uuid4()), str(uuid4())
    sources = probe._sources()
    # DOCX ZIP timestamps can change across calls: registration and upload
    # must use the same captured bytes to reach the restart failure.
    monkeypatch.setattr(probe, "_sources", lambda: sources)
    registered = {"case_id": case, "sources": [
        {"document_id": str(uuid4()), "version_id": str(uuid4()),
         "role": ("draft", "inventory", "exhibit", "exhibit")[index],
         "filename": filename, "media_type": media_type, "byte_length": len(payload),
         "sha256": probe.hashlib.sha256(payload).hexdigest()}
        for index, (filename, media_type, payload) in enumerate(sources)]}

    class Signin:
        def __init__(self, *_args):
            pass

        def sign_in(self, credential):
            return sessions[credential]

    class Response:
        status = 200

        def read(self, _limit):
            import json
            return json.dumps(registered).encode()

    class Connection:
        def __init__(self, *_args, **_kwargs):
            pass

        def request(self, *_args, **_kwargs):
            pass

        def getresponse(self):
            return Response()

        def close(self):
            pass

    class Storage:
        def __init__(self, _key):
            pass

        def get_verified(self, ref, token):
            if token != "token-0":
                raise probe.PrivateStorageDenied("denied")
            return next(payload for _, _, payload in sources
                        if probe.hashlib.sha256(payload).hexdigest() == ref.sha256_hex)

    starts = iter([object(), RuntimeError("restart failed")])

    def start():
        result = next(starts)
        if isinstance(result, Exception):
            raise result
        return result

    cleaned = []
    monkeypatch.setattr(probe, "SupabasePasswordSignin", Signin)
    monkeypatch.setattr(probe, "HttpsSupabaseUserLookup", lambda *_args: object())
    monkeypatch.setattr(probe, "SupabaseAuthUserVerifier", lambda *_args: SimpleNamespace(
        verify_bearer=lambda token: SimpleNamespace(
            subject_id=actors[int(token[-1])], issuer=probe.ISSUER, audience="authenticated")))
    monkeypatch.setattr(probe.http.client, "HTTPSConnection", Connection)
    monkeypatch.setattr(probe, "SignedOriginalsStorage", Storage)
    monkeypatch.setattr(probe, "admin_rpc", lambda _key, action, _params: {"org_id": org} if action == "setup" else True)
    monkeypatch.setattr(probe, "_server_start", start)
    monkeypatch.setattr(probe, "_server_stop", lambda _proc: None)
    monkeypatch.setattr(probe, "_request", lambda *_args: (403, {}))
    import base64

    import scripts.verify_m1_live_positive_original as positive

    def success(_token, _method, path, body):
        if path == "/dev/live/matters":
            return {"case_id": case}
        return {"verified": True, "sha256": probe.hashlib.sha256(
            base64.b64decode(body["content_base64"])).hexdigest()}

    monkeypatch.setattr(probe, "success", success)
    monkeypatch.setattr(positive, "_remove_original", lambda _key, ref: cleaned.append(ref.path))
    with pytest.raises(RuntimeError, match="restart failed"):
        probe.verify_registration((0, 1, 2), admin_key="test", publishable="test")
    assert len(cleaned) == 4
    assert len(set(cleaned)) == 4


def test_registration_must_match_scope_content_and_unique_versions():
    metadata = [{"role": "draft", "sha256": "a" * 64},
                {"role": "inventory", "sha256": "b" * 64}]
    rows = [dict(item, document_id=str(uuid4()), version_id=str(uuid4())) for item in metadata]
    assert probe._validate_registration({"case_id": "case", "sources": rows}, "case", metadata) == rows
    bad_scope = {"case_id": "foreign", "sources": rows}
    bad_hash = {"case_id": "case", "sources": [dict(rows[0], sha256="c" * 64), rows[1]]}
    duplicate = {"case_id": "case", "sources": [rows[0], dict(rows[1], version_id=rows[0]["version_id"])]}
    for response in (bad_scope, bad_hash, duplicate):
        with pytest.raises(probe.LiveFixtureError):
            probe._validate_registration(response, "case", metadata)
