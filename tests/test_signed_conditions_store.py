"""SupabaseConditionsStore against a FAKE rpc (no PostgREST, no network). Shape validation only."""
from __future__ import annotations

import hashlib

import pytest

from apps.api.signed_conditions_store import SupabaseConditionsStore
from apps.api.signed_workbench_routes import ConflictError

CASE = "11111111-1111-4111-8111-111111111111"
TEXT = '{"conditions":[],"format":"x"}'
SHA = hashlib.sha256(TEXT.encode()).hexdigest()


def store(answer):
    calls = []

    def rpc(**kw):
        calls.append(kw)
        if isinstance(answer, Exception):
            raise answer
        return answer
    return SupabaseConditionsStore(call_rpc=rpc, publishable_key="sb_publishable_x"), calls


def test_read_none_and_valid_and_forwards_bearer():
    s, calls = store({"revision": 0})
    assert s.read("tok", CASE) is None
    assert calls[0]["bearer"] == "tok" and calls[0]["name"] == "caseproof_read_conditions"
    s, _ = store({"revision": 2, "spec_text": TEXT, "spec_sha256": SHA})
    assert s.read("tok", CASE)["revision"] == 2


@pytest.mark.parametrize("bad", [
    None, [], {"revision": "1"}, {"revision": True}, {"revision": -1}, {"revision": 1},
    {"revision": 1, "spec_text": TEXT, "spec_sha256": "0" * 64},
    {"revision": 1, "spec_text": 5, "spec_sha256": SHA},
])
def test_read_refuses_untrusted_answers(bad):
    s, _ = store(bad)
    with pytest.raises(ValueError):
        s.read("tok", CASE)


def test_read_denial_is_an_error_not_empty():
    s, _ = store(PermissionError("denied"))
    with pytest.raises(PermissionError):
        s.read("tok", CASE)


def test_append_ok_conflict_and_bad_receipts():
    s, calls = store({"revision": 1, "spec_sha256": SHA})
    assert s.append("tok", CASE, 0, TEXT, SHA) == 1
    assert calls[0]["args"] == {"p_case": CASE, "p_expected": 0, "p_spec_text": TEXT, "p_sha": SHA}
    s, _ = store({"conflict": True, "revision": 3})
    with pytest.raises(ConflictError):
        s.append("tok", CASE, 0, TEXT, SHA)
    for bad in ({"revision": 2, "spec_sha256": SHA}, {"revision": 1, "spec_sha256": "0" * 64}, {}, None):
        s, _ = store(bad)
        with pytest.raises(ValueError):
            s.append("tok", CASE, 0, TEXT, SHA)


def test_append_refuses_inputs_before_calling():
    s, calls = store({"revision": 1, "spec_sha256": SHA})
    for args in (("nope", 0, TEXT, SHA), (CASE, 0, TEXT + " ", SHA), (CASE, 0, TEXT, "x")):
        with pytest.raises(ValueError):
            s.append("tok", *args)
    assert calls == []


def test_dev_app_wires_store_only_with_key_and_signed_workbench():
    from apps.api.litigation_development_app import _conditions_store
    assert _conditions_store(None, lambda b: None) is None
    assert _conditions_store("sb_publishable_x", None) is None
    assert isinstance(_conditions_store("sb_publishable_x", lambda b: None), SupabaseConditionsStore)
