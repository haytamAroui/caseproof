"""Regression tests for the protected development multi-source probe."""
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pypdf import PdfReader

from scripts import verify_dev_live_multisource as probe


def test_synthetic_pdf_sources_have_valid_text_and_image_only_pages():
    sources = probe._sources()
    assert sources[0][2].endswith(b"\n")
    for _, _, payload in sources[1:]:
        reader = PdfReader(BytesIO(payload), strict=True)
        assert len(reader.pages) == 1
    assert "invoice 125 EUR" in PdfReader(BytesIO(sources[1][2]), strict=True).pages[0].extract_text()
    assert not PdfReader(BytesIO(sources[3][2]), strict=True).pages[0].extract_text().strip()


def test_restart_failure_still_cleans_every_uploaded_object(monkeypatch):
    actors = [str(uuid4()) for _ in range(3)]
    sessions = [SimpleNamespace(user_id=a, access_token=f"token-{i}") for i, a in enumerate(actors)]
    org, case = str(uuid4()), str(uuid4())
    sources = probe._sources()
    registered = {"sources": [{"document_id": str(uuid4()), "version_id": str(uuid4())}
                              for _ in sources]}

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
