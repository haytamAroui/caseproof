"""Rights policy PostgREST transport is read-only, signed and nonblocking."""
from __future__ import annotations

import http.client
import json
import logging
from uuid import uuid4

import pytest

from application.data_rights import Decision, RightsPolicy, evaluate
from apps.api.data_rights_shadow import observe_authorized_read
from apps.api.data_rights_signed import ShadowLookupUnavailable, SignedRightsPolicyReader


class FakeResponse:
    def __init__(self, status: int, value: object):
        self.status, self.data = status, json.dumps(value).encode()

    def read(self, size: int) -> bytes:
        return self.data[:size]


def transport(monkeypatch: pytest.MonkeyPatch, status: int, value: object):
    sent = []

    class Connection:
        def __init__(self, host, timeout):
            assert host == "ldwmocpxwskvhoojndrd.supabase.co"
            assert timeout == 3.0

        def request(self, method, path, body=None, headers=None):
            sent.append((method, path, json.loads(body), headers))

        def getresponse(self):
            return FakeResponse(status, value)

        def close(self):
            pass

    monkeypatch.setattr(http.client, "HTTPSConnection", Connection)
    return sent


def inputs():
    return {
        "bearer": "synthetic.signed.jwt",
        "case_id": str(uuid4()),
        "document_id": str(uuid4()),
        "version_id": str(uuid4()),
    }


def test_legacy_signed_policy_missing_not_approved(monkeypatch):
    sent = transport(monkeypatch, 200, {"policy_status": "missing"})
    assert SignedRightsPolicyReader("sb_publishable_fixture").read(**inputs()) is None
    assert sent[0][0:2] == ("POST", "/rest/v1/rpc/caseproof_rights_current")
    assert sent[0][3]["Authorization"] == "Bearer synthetic.signed.jwt"
    assert sent[0][3]["apikey"] == "sb_publishable_fixture"


def test_signed_policy_projection_is_minimal_and_strict(monkeypatch):
    sent = transport(monkeypatch, 200, {
        "policy_status": "present", "policy_version": 2,
        "origin": "CLIENT_UPLOAD", "classification": "CLIENT_CONFIDENTIAL",
        "authorization_reference_present": True,
        "process": True, "export": True,
        "indexForSearch": False, "useAcrossMatters": False,
    })
    policy = SignedRightsPolicyReader("sb_publishable_fixture").read(**inputs())
    assert policy is not None
    assert policy.authorization_reference == "recorded"
    assert evaluate(policy, "process", same_matter=True) == Decision.ALLOW
    assert evaluate(policy, "indexForSearch", same_matter=True) == Decision.DENY
    assert set(sent[0][2]) == {"p_case", "p_document", "p_version"}


@pytest.mark.parametrize("status,reply", [
    (404, {"error": "not installed"}),
    (403, {"error": "forbidden"}),
    (200, {"policy_status": "present", "policy_version": True}),
    (200, {"policy_status": "present", "policy_version": 1, "origin": "CLIENT_UPLOAD"}),
    (200, {"policy_status": "unknown"}),
])
def test_malformed_or_denied_projection_never_invents_approval(monkeypatch, status, reply):
    transport(monkeypatch, status, reply)
    with pytest.raises(ShadowLookupUnavailable):
        SignedRightsPolicyReader("sb_publishable_fixture").read(**inputs())


def test_shadow_errors_never_change_authorized_data_or_log_private_values(caplog):
    def unavailable():
        raise ShadowLookupUnavailable("sensitive response hidden")
    with caplog.at_level(logging.WARNING, logger="caseproof.rights.shadow"):
        observe_authorized_read(policy_lookup=unavailable)
    assert "evaluation_unavailable" in caplog.text
    assert "sensitive response" not in caplog.text


def test_cross_matter_denied_even_when_policy_export_true():
    policy = RightsPolicy(1, "firm-authorization", {"export": True})
    assert evaluate(policy, "export", same_matter=False) == Decision.DENY
