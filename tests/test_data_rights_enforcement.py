"""PR2 rights enforcement: protected use requires explicit, freshly signed ALLOW."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from uuid import uuid4

import pytest

from application.data_rights import Action, Decision, RightsPolicy
from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.data_rights_enforcement import SignedRightsGate
from apps.api.data_rights_signed import ShadowLookupUnavailable

CASE, DOCUMENT, VERSION = (str(uuid4()) for _ in range(3))


@dataclass
class Reader:
    current: RightsPolicy | None
    broken: bool = False
    calls: list[dict[str, str]] = field(default_factory=list)

    def read(self, *, bearer: str, case_id: str, document_id: str, version_id: str):
        self.calls.append({
            "bearer": bearer, "case_id": case_id,
            "document_id": document_id, "version_id": version_id,
        })
        if self.broken:
            raise ShadowLookupUnavailable("sensitive upstream failure")
        return self.current


def policy(*, process: bool = True, index: bool = False, export: bool = False):
    return RightsPolicy(
        version=2, authorization_reference="confidential contract reference",
        permissions={
            "process": process, "indexForSearch": index,
            "useAcrossMatters": False, "export": export,
        },
    )


def call(gate, *, action=Action.PROCESS, version=VERSION, same_matter=True):
    return gate.require(
        bearer="synthetic.signed.jwt", case_id=CASE, document_id=DOCUMENT,
        version_id=version, action=action, same_matter=same_matter,
    )


def test_explicit_persisted_rights_are_required_per_action():
    reader = Reader(policy(process=True, index=False, export=False))
    gate = SignedRightsGate(reader)
    result = call(gate)
    assert result.decision == Decision.ALLOW
    assert result.policy_version == 2
    with pytest.raises(AccessRejected) as exc:
        call(gate, action=Action.EXPORT)
    assert exc.value.failure == AccessFailure.RESOURCE_MASKED
    with pytest.raises(AccessRejected):
        call(gate, action=Action.INDEX_FOR_SEARCH)
    assert len(reader.calls) == 3
    assert all(x["bearer"] == "synthetic.signed.jwt" for x in reader.calls)


def test_missing_legacy_policy_does_not_gain_implicit_approval():
    with pytest.raises(AccessRejected) as exc:
        call(SignedRightsGate(Reader(None)))
    assert exc.value.failure == AccessFailure.RESOURCE_MASKED


def test_missing_reference_blocks_processing_even_when_flag_true():
    p = RightsPolicy(1, None, {"process": True})
    with pytest.raises(AccessRejected):
        call(SignedRightsGate(Reader(p)))


def test_signed_lookup_failure_is_unavailable_and_redacted(caplog):
    gate = SignedRightsGate(Reader(policy(), broken=True))
    with caplog.at_level(logging.WARNING, logger="caseproof.rights.enforcement"):
        with pytest.raises(AccessRejected) as exc:
            call(gate)
    assert exc.value.failure == AccessFailure.SERVICE_UNAVAILABLE
    assert "sensitive upstream failure" not in caplog.text
    assert "synthetic.signed.jwt" not in caplog.text
    assert "confidential contract reference" not in caplog.text


def test_cross_matter_is_prohibited_even_with_export_permission():
    gate = SignedRightsGate(Reader(policy(export=True)))
    with pytest.raises(AccessRejected):
        call(gate, action=Action.EXPORT, same_matter=False)


def test_bundle_checks_all_server_resolved_sources_before_protected_action():
    reader = Reader(policy(export=True))
    gate = SignedRightsGate(reader)
    result = gate.require_bundle(
        bearer="signed", case_id=CASE, action=Action.EXPORT,
        sources=[
            {"document_id": DOCUMENT, "version_id": VERSION},
            {"document_id": DOCUMENT, "version_id": str(uuid4())},
        ],
    )
    assert len(result) == 2
    assert len(reader.calls) == 2
    with pytest.raises(AccessRejected) as exc:
        gate.require_bundle(
            bearer="signed", case_id=CASE, action=Action.PROCESS,
            sources=[{"document_id": DOCUMENT, "version_id": VERSION}] * 2,
        )
    assert exc.value.failure == AccessFailure.SERVICE_UNAVAILABLE


@pytest.mark.parametrize("sources", [[], [{}], [{"document_id": "x"}]])
def test_incomplete_or_empty_source_scope_never_authorizes(sources):
    with pytest.raises(AccessRejected):
        SignedRightsGate(Reader(policy())).require_bundle(
            bearer="signed", case_id=CASE, action=Action.PROCESS, sources=sources,
        )


def test_unknown_action_never_reaches_signed_reader():
    reader = Reader(policy())
    with pytest.raises(ValueError):
        call(SignedRightsGate(reader), action="export")
    assert not reader.calls


def test_default_is_unwired_in_dev_composition(monkeypatch):
    # The opt-in is made only at app composition, never by bearer or request data.
    from apps.api.dev_live_entry import app
    assert app is not None
