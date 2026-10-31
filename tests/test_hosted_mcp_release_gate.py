"""Per-call, OAuth-client and matter-bound revocable content release acceptance."""
from datetime import UTC, datetime

from apps.api.hosted_mcp_release_gate import CallbackHostContentGate

CASE = "matter"
BRIEF = "draft"
HASH = "a" * 64
ACTOR = "signed-user"
CLIENT = "approved-mcp-client"
BEARER = "verified-oauth-user-bearer"


def invoke(gate, *, client=CLIENT, case=CASE):
    return gate.resolve(subject=ACTOR, client_id=client, bearer=BEARER,
                        destination="approved-firm-host", case_id=case,
                        brief_id=BRIEF, snapshot_hash=HASH)


def test_current_consent_granted_then_revoked_even_for_same_bearer():
    allowed = {(ACTOR, CLIENT, "approved-firm-host", CASE, BRIEF, HASH)}
    calls = []
    def authorize(subject, client_id, destination, case_id, brief_id, snapshot_hash):
        key = (subject, client_id, destination, case_id, brief_id, snapshot_hash)
        calls.append(key)
        return key in allowed
    gate = CallbackHostContentGate(authorize)
    approved = invoke(gate)
    assert approved is not None
    assert approved.permits(bearer=BEARER, case_id=CASE, brief_id=BRIEF,
                            snapshot_hash=HASH, destination="approved-firm-host",
                            now=datetime.now(UTC))
    assert not approved.permits(bearer="other", case_id=CASE, brief_id=BRIEF,
                                snapshot_hash=HASH, destination="approved-firm-host",
                                now=datetime.now(UTC))
    assert invoke(gate, client="ungranted-client") is None
    assert invoke(gate, case="other-matter") is None
    allowed.clear()
    assert invoke(gate) is None
    assert len(calls) == 4


def test_host_consent_outage_or_non_boolean_response_fails_closed():
    def down(*_):
        raise ConnectionError("consent store offline")
    assert invoke(CallbackHostContentGate(down)) is None
    assert invoke(CallbackHostContentGate(lambda *_: 1)) is None
    assert invoke(CallbackHostContentGate(lambda *_: "true")) is None


def test_release_clock_must_be_timezone_aware():
    gate = CallbackHostContentGate(lambda *_: True,
                                   clock=lambda: datetime(2026, 10, 31))
    assert invoke(gate) is None
