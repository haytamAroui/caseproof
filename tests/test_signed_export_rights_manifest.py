"""PR203: signed, frozen, privacy-minimal export-rights evidence tests."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import uuid4

import pytest

from application.data_rights import RightsPolicy
from apps.api.access_control import AccessRejected
from apps.api.data_rights_enforcement import SignedRightsGate
from apps.api.dossier_journey import canonical
from apps.api.export_rights_manifest import (
    attest_export_rights,
    validate_export_rights,
)
from tests.test_f6_reviewed_exports import base, client, header

CASE = str(uuid4())
DOC = str(uuid4())
VERSION = str(uuid4())
SHA = hashlib.sha256(b"artificial signed source").hexdigest()


@dataclass
class Reader:
    version: int = 3
    export: bool = True
    policy_missing: bool = False

    def read(self, *, bearer: str, case_id: str, document_id: str, version_id: str):
        if self.policy_missing:
            return None
        return RightsPolicy(
            version=self.version,
            authorization_reference="PRIVATE-NEVER-IN-RELEASE",
            classification="CLIENT_CONFIDENTIAL",
            origin="CLIENT_UPLOAD",
            permissions={
                "process": True, "indexForSearch": True,
                "useAcrossMatters": False, "export": self.export,
            },
        )


def source():
    return {"document_id": DOC, "version_id": VERSION, "sha256": SHA, "role": "draft"}


def test_attestation_is_deterministic_source_bound_and_excludes_sensitive_reference():
    gate = SignedRightsGate(Reader())
    first = attest_export_rights(gate, bearer="signed", case_id=CASE, sources=[source()])
    second = attest_export_rights(gate, bearer="signed", case_id=CASE, sources=[source()])
    assert first == second
    assert first == {
        "schema": "caseproof-export-rights-v1",
        "action": "export",
        "scope": "same_matter",
        "decision": "allow",
        "sources": [{
            "document_id": DOC, "version_id": VERSION,
            "original_sha256": SHA, "policy_version": 3,
            "decision": "allow",
        }],
    }
    assert "PRIVATE-NEVER-IN-RELEASE" not in canonical(first)


@pytest.mark.parametrize("options", [
    {"policy_missing": True}, {"export": False}, {"version": 0},
])
def test_unknown_revoked_or_invalid_policy_never_signs_a_release(options):
    with pytest.raises(AccessRejected):
        attest_export_rights(
            SignedRightsGate(Reader(**options)),
            bearer="signed", case_id=CASE, sources=[source()],
        )


@pytest.mark.parametrize("change", [
    lambda a: a["sources"][0].update(policy_version=True),
    lambda a: a["sources"][0].update(original_sha256="f" * 64),
    lambda a: a["sources"][0].update(document_id=str(uuid4())),
    lambda a: a["sources"][0].update(decision="deny"),
    lambda a: a.update(action="process"),
    lambda a: a.update(scope="other_matter"),
    lambda a: a["sources"].append(dict(a["sources"][0])),
    lambda a: a["sources"][0].update(secret="forged"),
])
def test_historical_proof_structure_must_not_be_silently_reinterpreted(change):
    evidence = attest_export_rights(
        SignedRightsGate(Reader()), bearer="signed", case_id=CASE, sources=[source()],
    )
    change(evidence)
    with pytest.raises(AccessRejected):
        validate_export_rights(evidence, [source()])


def test_signed_f6_release_includes_policy_versions_under_existing_hmac_and_replay():
    api, store = client()
    reader = Reader(version=7)
    store.rights_gate = SignedRightsGate(reader)
    store.report["sources"][0]["document_id"] = str(uuid4())
    url = base()
    request = {"release_id": str(uuid4()), "snapshot_hash": store.report["snapshot_hash"]}
    response = api.post(url, json=request, headers=header())
    assert response.status_code == 200
    manifest = response.json()["manifest"]
    evidence = manifest["rights_attestation"]
    assert evidence["sources"][0]["policy_version"] == 7
    assert evidence["sources"][0]["version_id"] == store.report["sources"][0]["version_id"]
    assert evidence["sources"][0]["original_sha256"] == store.report["sources"][0]["sha256"]
    assert "PRIVATE-NEVER-IN-RELEASE" not in canonical(manifest)
    assert api.post(url, json=request, headers=header()).status_code == 200
    assert api.get(url + "/" + request["release_id"], headers=header()).status_code == 200
    reader.export = False
    # Old artifacts are historical; source policies are not re-granted on read.
    assert api.get(
        url + "/" + request["release_id"] + "/artifacts/json", headers=header(),
    ).status_code == 200
    # But a NEW release of that source may not be signed.
    assert api.post(
        url, json={**request, "release_id": str(uuid4())}, headers=header(),
    ).status_code in (403, 404)


def test_signed_release_policy_version_race_cannot_commit(monkeypatch):
    api, store = client()
    reader = Reader(version=4)
    store.rights_gate = SignedRightsGate(reader)
    store.report["sources"][0]["document_id"] = str(uuid4())
    import apps.api.dossier_export_release as route

    original = route._checked_artifacts

    def changed_in_flight(report, raw):
        result = original(report, raw)
        reader.version = 5
        return result

    monkeypatch.setattr(route, "_checked_artifacts", changed_in_flight)
    result = api.post(
        base(), json={"release_id": str(uuid4()), "snapshot_hash": store.report["snapshot_hash"]},
        headers=header(),
    )
    assert result.status_code == 409
    assert not store.saved


def test_post_release_tampering_of_rights_evidence_is_detected_even_if_receipt_rebuilt():
    api, store = client()
    store.rights_gate = SignedRightsGate(Reader())
    store.report["sources"][0]["document_id"] = str(uuid4())
    rid = str(uuid4())
    assert api.post(
        base(), json={"release_id": rid, "snapshot_hash": store.report["snapshot_hash"]},
        headers=header(),
    ).status_code == 200
    manifest = store.saved[rid]["status"]["manifest"]
    manifest["rights_attestation"]["sources"][0]["policy_version"] = -1
    # Even a privileged, malformed re-sign attempt cannot bypass schema checks.
    unsigned = {k: v for k, v in manifest.items() if k != "server_receipt"}
    from apps.api.dossier_export_release import _hash

    manifest["manifest_sha256"] = _hash(canonical(
        {k: v for k, v in unsigned.items() if k != "manifest_sha256"}
    ).encode())
    manifest["server_receipt"] = store.receipt({
        k: v for k, v in manifest.items() if k != "server_receipt"
    })
    assert api.get(base() + "/" + rid, headers=header()).status_code in (403, 404, 503)
