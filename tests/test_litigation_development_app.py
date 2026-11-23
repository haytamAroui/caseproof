"""Combined API tests use synthetic identity and source bytes only."""
import shutil
from hashlib import sha256
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from application.litigation.brief_checks import DraftReference, VersionedBrief
from application.litigation.library import EvidencePreview, EvidenceRow
from application.litigation.unified_review import BriefRepresentation, SourceScope
from apps.api.access_control import AccessRejected
from apps.api.litigation_check_service import CheckBundle
from apps.api.litigation_development_app import create_litigation_development_app
from apps.api.litigation_original_reader import AuthorizedOriginalReader, Original
from domains.disputes.exhibits import ExhibitEntry, ExhibitPage, ExhibitRegister
from tests.test_litigation_evidence_search import ACTOR, CASE, DRAFT, search_rig


class Originals:
    calls = 0
    tamper = False

    def read(self, *, access, source_id, version_id):
        self.calls += 1
        raw = b"De betaling is vastgesteld."
        return Original(b"tampered" if self.tamper else raw, sha256(raw).hexdigest(), "text/plain")


def client_rig():
    search, store = search_rig()
    originals = Originals()
    reader = AuthorizedOriginalReader(search.checker, originals)
    client = TestClient(create_litigation_development_app(checker=search.checker, originals=reader),
                        client=("127.0.0.1", 50000))
    return client, search, store, originals


def test_one_composed_api_checks_searches_and_downloads_same_snapshot():
    client, _, _, _ = client_rig()
    headers = {"Authorization": "Bearer signed-dev-fixture"}
    root = f"/v2/matters/{CASE}/briefs/{DRAFT}"
    checked = client.post(f"{root}/check", headers=headers)
    search = client.post(f"{root}/evidence/search", headers=headers, json={"query": "betaling"})
    original = client.get(f"{root}/evidence/s1/versions/v1/original", headers=headers)
    assert checked.status_code == search.status_code == original.status_code == 200
    assert checked.json()["case_id"] == search.json()["case_id"] == CASE
    assert search.json()["hits"][0]["source_version_id"] == "v1"
    assert original.content == b"De betaling is vastgesteld."
    assert original.headers["x-caseproof-original-sha256"] == sha256(original.content).hexdigest()
    assert original.headers["content-disposition"].startswith("attachment")
    assert original.headers["cache-control"] == "no-store"


def test_denies_unverified_and_out_of_scope_originals_before_reading():
    client, _, _, originals = client_rig()
    root = f"/v2/matters/{CASE}/briefs/{DRAFT}/evidence"
    assert client.get(f"{root}/s1/versions/v1/original").status_code == 401
    headers = {"Authorization": "Bearer signed-dev-fixture"}
    assert client.get(f"{root}/foreign/versions/v1/original", headers=headers).status_code == 404
    assert originals.calls == 0
    assert client.get(f"{root}/s1/versions/v2/original", headers=headers).status_code == 404
    assert originals.calls == 0


def test_stale_and_tampered_source_never_return_original():
    client, _, store, originals = client_rig()
    headers = {"Authorization": "Bearer signed-dev-fixture"}
    path = f"/v2/matters/{CASE}/briefs/{DRAFT}/evidence/s1/versions/v1/original"
    originals.tamper = True
    assert client.get(path, headers=headers).status_code == 503
    originals.tamper = False
    store.snapshot_current = False
    assert client.get(path, headers=headers).status_code == 503


def test_loopback_boundary_and_unconfigured_composition_fail_closed():
    client, search, _, originals = client_rig()
    remote = TestClient(create_litigation_development_app(
        checker=search.checker, originals=AuthorizedOriginalReader(search.checker, originals)),
        client=("192.0.2.1", 50000))
    assert remote.post(f"/v2/matters/{CASE}/briefs/{DRAFT}/check").status_code == 403
    unconfigured = TestClient(create_litigation_development_app(), client=("127.0.0.1", 50000))
    assert unconfigured.post(f"/v2/matters/{CASE}/briefs/{DRAFT}/check").status_code == 503


def test_original_reader_requires_explicit_evidence_grant():
    _, search, store, originals = client_rig()
    original = store.current_access
    def deny_evidence(subject_id, case_id):
        from application.litigation.matter_policy import CurrentMatterGrant, MatterPermission
        from apps.api.litigation_check_service import PrivateMatterAccess
        scope = original(subject_id, case_id)
        assert scope is not None
        grant = CurrentMatterGrant(ACTOR, scope.org_id, scope.case_id, True,
                                   frozenset({MatterPermission.READ, MatterPermission.DRAFT_CHECK}), 1)
        return PrivateMatterAccess(scope.case_id, scope.org_id, scope.member, grant, 1)
    store.current_access = deny_evidence
    with pytest.raises(AccessRejected):
        AuthorizedOriginalReader(search.checker, originals).read(
            bearer="signed-dev-fixture", case_id=CASE, brief_version_id=DRAFT, source_id="s1", version_id="v1")
    assert originals.calls == 0


def test_stale_published_snapshot_is_typed_conflict_not_unavailable():
    from apps.api.litigation_check_service import MatterCheckUnavailable
    client, _, store, _ = client_rig()
    headers = {"Authorization": "Bearer signed-dev-fixture"}
    root = f"/v2/matters/{CASE}/briefs/{DRAFT}"
    assert client.post(f"{root}/check", headers=headers).status_code == 200
    load_bundle = store.load_bundle

    def stale_bundle(**kwargs):
        raise MatterCheckUnavailable()

    store.load_bundle = stale_bundle
    try:
        stale = client.post(f"{root}/check", headers=headers)
    finally:
        store.load_bundle = load_bundle
    assert stale.status_code == 409
    assert stale.json()["error"] == "stale_snapshot"
    still_current = store.still_current
    store.still_current = lambda **kwargs: False
    try:
        drifted = client.post(f"{root}/check", headers=headers)
    finally:
        store.still_current = still_current
    assert drifted.status_code == 409
    assert drifted.json()["error"] == "stale_snapshot"


def test_preview_page_mappings_keep_numbering_spaces_distinct():
    client, _, _, _ = client_rig()
    headers = {"Authorization": "Bearer signed-dev-fixture"}
    preview = client.get(f"/v2/matters/{CASE}/briefs/{DRAFT}/sources/s1", headers=headers)
    assert preview.status_code == 200
    assert preview.json()["page_mappings"] == [
        {"pdf_page": 1, "printed_page": None, "bundle_page": None}
    ]
    # Wire spans are 1-based physical PDF pages (store blocks are zero-based).
    assert preview.json()["spans"] == [[0, 27, "pdf", 1]]


def _pdf_bytes() -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


PDF_BYTES = _pdf_bytes()
PNG_MAGIC = bytes((137, 80, 78, 71, 13, 10, 26, 10))


def _pdf_bundle(*, case_id: str, brief_version_id: str, previews=None) -> CheckBundle:
    text = "Page PDF synthetique de test."
    brief = VersionedBrief(case_id, brief_version_id, sha256(text.encode()).hexdigest(),
                           (DraftReference("r1", "Stuk 1", None, 1),))
    representation = BriefRepresentation(
        brief, text, sha256(text.encode()).hexdigest(), "fixture-parser", (),
    )
    registered = ExhibitRegister(1, (
        ExhibitEntry("e1", "Stuk 1", (ExhibitPage("s1", "v1", 1),), confirmed=True),
    ))
    row = EvidenceRow("s1", "d1", "v1", sha256(PDF_BYTES).hexdigest(),
                      "application/pdf", "ready", "fixture-parser", "rep1", (), ())
    return CheckBundle(representation, registered,
                       previews if previews is not None else (EvidencePreview(row, "", ()),),
                       SourceScope((("s1", "v1"),)))


class PdfOriginals:
    calls = 0
    tamper = False

    def read(self, *, access, source_id, version_id):
        self.calls += 1
        return Original(b"tampered" if self.tamper else PDF_BYTES,
                        sha256(PDF_BYTES).hexdigest(), "application/pdf")


def pdf_client_rig(*, previews=None):
    search, store = search_rig()
    originals = PdfOriginals()

    def load_bundle(*, case_id, brief_version_id, access):
        store.load_calls += 1
        return _pdf_bundle(case_id=case_id, brief_version_id=brief_version_id, previews=previews)

    store.load_bundle = load_bundle
    reader = AuthorizedOriginalReader(search.checker, originals)
    client = TestClient(create_litigation_development_app(checker=search.checker, originals=reader),
                        client=("127.0.0.1", 50000))
    return client, originals


PAGE_PATH = f"/v2/matters/{CASE}/briefs/{DRAFT}/evidence/s1/versions/v1/pages"


@pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="pdftoppm rasterizer not installed")
def test_physical_page_render_is_authorized_and_digest_bound():
    client, _ = pdf_client_rig()
    headers = {"Authorization": "Bearer signed-dev-fixture"}
    page = client.get(f"{PAGE_PATH}/1", headers=headers)
    assert page.status_code == 200
    assert page.headers["content-type"] == "image/png"
    assert page.content[:8] == PNG_MAGIC
    assert page.headers["x-caseproof-original-sha256"] == sha256(PDF_BYTES).hexdigest()
    assert page.headers["x-caseproof-physical-page"] == "1"
    assert page.headers["cache-control"] == "no-store"
    assert page.headers["x-content-type-options"] == "nosniff"


def test_physical_page_rejects_non_pdf_and_out_of_range():
    client, _ = pdf_client_rig()
    headers = {"Authorization": "Bearer signed-dev-fixture"}
    assert client.get(f"{PAGE_PATH}/0", headers=headers).status_code == 404
    assert client.get(f"{PAGE_PATH}/99", headers=headers).status_code == 404
    # Non-PDF original: no physical page rendering, fail closed.
    plain, _, _, _ = client_rig()
    response = plain.get(
        f"/v2/matters/{CASE}/briefs/{DRAFT}/evidence/s1/versions/v1/pages/1", headers=headers)
    assert response.status_code == 404


def test_physical_page_masks_unknown_source_and_requires_bearer():
    client, originals = pdf_client_rig()
    headers = {"Authorization": "Bearer signed-dev-fixture"}
    assert client.get(f"/v2/matters/{CASE}/briefs/{DRAFT}/evidence/foreign/versions/v1/pages/1",
                      headers=headers).status_code == 404
    assert originals.calls == 0
    assert client.get(f"{PAGE_PATH}/1").status_code == 401
    assert originals.calls == 0


def test_physical_page_fail_closed_on_tamper_and_ambiguous_binding():
    client, originals = pdf_client_rig()
    headers = {"Authorization": "Bearer signed-dev-fixture"}
    originals.tamper = True
    assert client.get(f"{PAGE_PATH}/1", headers=headers).status_code == 503
    # Ambiguous source binding (two preview rows for one source version):
    # masked before any byte read or rasterization.
    row = EvidenceRow("s1", "d1", "v1", sha256(PDF_BYTES).hexdigest(),
                      "application/pdf", "ready", "fixture-parser", "rep1", (), ())
    dup, dup_originals = pdf_client_rig(previews=(EvidencePreview(row, "", ()),
                                                  EvidencePreview(row, "", ())))
    assert dup.get(f"{PAGE_PATH}/1", headers=headers).status_code == 404
    assert dup_originals.calls == 0


# Offline review-record replay (scripts/verify_review_record_file.py): synthetic
# records only, no server involved. Lives in this CI-listed file because
# clearbrief-workspace.yml runs explicit file lists, not pytest discovery.
def _record_canonical(value):
    import json
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _record_digest(text):
    return sha256(text.encode("utf-8")).hexdigest()


def valid_offline_record():
    run = {"schema": "check-run", "snapshot": "x", "observations": []}
    snapshot = _record_digest("snapshot-a")
    decision = {"actor_id": "11111111-1111-4111-8111-111111111111",
                "disposition": "verified", "rationale": "synthetique"}
    event = {
        "run": snapshot,
        "revision": 1,
        "request": "22222222-2222-4222-8222-222222222222",
        "actor": decision["actor_id"],
        "previous_sha": "0" * 64,
        "decision": decision,
    }
    event_sha = _record_digest(_record_canonical(event))
    body = {
        "schema": "caseproof-review-record-v1",
        "case_id": "case-a",
        "document_role": "own_draft",
        "brief": {
            "brief_id": "b", "head_revision": 1, "head_version_id": "v",
            "graph_sha256": _record_digest("g"), "original_sha256": _record_digest("o"),
            "document_id": "d", "document_version_id": "dv",
            "case_revision": 1, "exhibit_revision": 1,
        },
        "checks": [{
            "snapshot_sha256": snapshot, "payload_sha256": _record_digest(_record_canonical(run)),
            "payload_sha256_verified": True, "case_revision": 1, "exhibit_revision": 1,
            "run": run,
        }],
        "reviews": [{
            "snapshot_sha256": snapshot, "head_sha256": event_sha, "chain_verified": True,
            "decisions": [{
                "revision": 1, "request_id": event["request"],
                "actor_id": decision["actor_id"], "event_sha256": event_sha,
                "decision": decision,
            }],
        }],
        "note": "synthetique",
    }
    body["record_sha256"] = _record_digest(_record_canonical(body))
    return body


def _recompute_body_digest(body):
    return _record_digest(_record_canonical(
        {k: v for k, v in body.items() if k != "record_sha256"}))


def test_valid_offline_record_replays():
    from scripts.verify_review_record_file import verify_record_document
    steps = verify_record_document(valid_offline_record())
    assert any("payload digest replayed" in s for s in steps)
    assert any("replayed from genesis" in s for s in steps)
    assert any("record body digest" in s for s in steps)


def test_offline_record_tampered_decision_fails_closed():
    from scripts.verify_review_record_file import (
        RecordVerificationError,
        verify_record_document,
    )
    body = valid_offline_record()
    body["reviews"][0]["decisions"][0]["decision"]["disposition"] = "approved"
    body["record_sha256"] = _recompute_body_digest(body)
    with pytest.raises(RecordVerificationError, match="tampered recorded review event"):
        verify_record_document(body)


def test_offline_record_tampered_run_payload_fails_closed():
    from scripts.verify_review_record_file import (
        RecordVerificationError,
        verify_record_document,
    )
    body = valid_offline_record()
    body["checks"][0]["run"]["observations"] = ["forged"]
    body["record_sha256"] = _recompute_body_digest(body)
    with pytest.raises(RecordVerificationError, match="payload digest mismatch"):
        verify_record_document(body)


def test_offline_record_tampered_body_digest_fails_closed():
    from scripts.verify_review_record_file import (
        RecordVerificationError,
        verify_record_document,
    )
    body = valid_offline_record()
    body["brief"]["head_revision"] = 2
    with pytest.raises(RecordVerificationError, match="record body digest mismatch"):
        verify_record_document(body)


def test_offline_record_wrong_schema_rejected():
    from scripts.verify_review_record_file import (
        RecordVerificationError,
        verify_record_document,
    )
    with pytest.raises(RecordVerificationError, match="not a caseproof-review-record-v1"):
        verify_record_document({"schema": "other"})


def test_offline_record_broken_chain_head_fails_closed():
    from scripts.verify_review_record_file import (
        RecordVerificationError,
        verify_record_document,
    )
    body = valid_offline_record()
    body["reviews"][0]["head_sha256"] = _record_digest("other-head")
    body["record_sha256"] = _recompute_body_digest(body)
    with pytest.raises(RecordVerificationError, match="review head mismatch"):
        verify_record_document(body)


# Ed25519 receipt on the exported record: installation signature, never a
# personal/legal/eIDAS signature. Three outcomes, no silent downgrade.
def _signed_offline_record():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
        PublicFormat,
    )

    from apps.api.disposable_review_record import sign_record_body
    private = Ed25519PrivateKey.generate()
    seed = private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    body = valid_offline_record()
    body["receipt"] = sign_record_body(body, seed)
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return body, seed, public


def test_sign_record_body_strict_key():
    from apps.api.disposable_review_record import RecordConflict, sign_record_body
    with pytest.raises(RecordConflict):
        sign_record_body(valid_offline_record(), b"short")
    with pytest.raises(RecordConflict):
        sign_record_body({"schema": "caseproof-review-record-v1"}, b"k" * 32)


def test_signed_record_verifies_against_trusted_key():
    from scripts.verify_review_record_file import verify_record_document
    body, _seed, public = _signed_offline_record()
    steps = verify_record_document(body, trusted_public_key=public)
    assert any("VERIFIED against the trusted installation key" in s for s in steps)


def test_signed_record_without_trusted_key_is_self_asserted():
    from scripts.verify_review_record_file import verify_record_document
    body, _seed, _public = _signed_offline_record()
    steps = verify_record_document(body)
    assert any("SELF-ASSERTED" in s for s in steps)


def test_tampered_signed_record_fails_signature():
    from scripts.verify_review_record_file import (
        RecordVerificationError,
        verify_record_document,
    )
    body, _seed, public = _signed_offline_record()
    body["brief"]["head_revision"] = 7
    body["record_sha256"] = _recompute_body_digest(
        {k: v for k, v in body.items() if k != "receipt"})
    with pytest.raises(RecordVerificationError, match="invalid receipt signature"):
        verify_record_document(body, trusted_public_key=public)


def test_key_substitution_fails_against_trusted_key():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
        PublicFormat,
    )

    from apps.api.disposable_review_record import sign_record_body
    from scripts.verify_review_record_file import (
        RecordVerificationError,
        verify_record_document,
    )
    body, _seed, trusted = _signed_offline_record()
    body["brief"]["head_revision"] = 7
    body["record_sha256"] = _recompute_body_digest(
        {k: v for k, v in body.items() if k != "receipt"})
    forger = Ed25519PrivateKey.generate()
    forged_seed = forger.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    signed_record = {k: v for k, v in body.items() if k != "receipt"}
    body["receipt"] = sign_record_body(signed_record, forged_seed)
    assert body["receipt"]["public_key"] == forger.public_key().public_bytes(
        Encoding.Raw, PublicFormat.Raw).hex()
    # Internally valid signature, substituted key: embedded-only check reports
    # self-asserted; trusted-key verification must fail closed.
    steps = verify_record_document(body)
    assert any("SELF-ASSERTED" in s for s in steps)
    with pytest.raises(RecordVerificationError, match="untrusted issuer"):
        verify_record_document(body, trusted_public_key=trusted)


def test_unsigned_record_with_trusted_key_fails_closed():
    from scripts.verify_review_record_file import (
        RecordVerificationError,
        verify_record_document,
    )
    _body, _seed, public = _signed_offline_record()
    with pytest.raises(RecordVerificationError, match="no receipt"):
        verify_record_document(valid_offline_record(), trusted_public_key=public)
    steps = verify_record_document(valid_offline_record())
    assert any("integrity-only record" in s for s in steps)


# User-declared exhibit page mappings: independent numbering spaces, no
# inference, duplicate physical pages fail closed, hardcoded printed page
# removed.
def test_confirmed_pages_absent_mappings_pdf_inventory_is_complete():
    from apps.api.disposable_signed_brief_publisher import _confirmed_pages
    pages = _confirmed_pages("doc", "ver", None, page_count=3)
    assert [p.pdf_page for p in pages] == [1, 2, 3]
    assert all(p.printed_page is None and p.bundle_page is None for p in pages)


def test_confirmed_pages_absent_mappings_non_pdf_is_explicit_unpaginated():
    from apps.api.disposable_signed_brief_publisher import _confirmed_pages
    pages = _confirmed_pages("doc", "ver", None, page_count=None)
    assert len(pages) == 1
    assert pages[0].unpaginated
    assert pages[0].pdf_page is None and pages[0].printed_page is None
    assert pages[0].bundle_page is None


def test_confirmed_pages_user_declared_labels_merge_onto_real_pages():
    from apps.api.disposable_signed_brief_publisher import _confirmed_pages
    pages = _confirmed_pages("doc", "ver", [
        {"pdf_page": 1, "printed_page": 3, "bundle_page": 7},
        {"pdf_page": 2},
    ], page_count=4)
    assert [p.pdf_page for p in pages] == [1, 2, 3, 4]
    assert (pages[0].printed_page, pages[0].bundle_page) == (3, 7)
    assert (pages[1].printed_page, pages[1].bundle_page) == (None, None)
    assert (pages[3].printed_page, pages[3].bundle_page) == (None, None)


def test_confirmed_pages_reject_invalid_input():
    from apps.api.disposable_signed_brief_publisher import _confirmed_pages
    bad = [
        [{"pdf_page": 1}, {"pdf_page": 1}],              # duplicate physical page
        [{"pdf_page": 0}],                                # out of range
        [{"pdf_page": "1"}],                              # wrong type
        [{"printed_page": 3}],                            # physical page required
        [{"pdf_page": 1, "printed_page": 0}],             # invalid printed space
        [{"pdf_page": 1, "bundle_page": -2}],             # invalid bundle space
        [{"pdf_page": 1, "other": 2}],                    # unknown key
        [],                                               # empty list
        [{"pdf_page": 1}] * 513,                          # over bound
        "not-a-list",
    ]
    for payload in bad:
        with pytest.raises(ValueError):
            _confirmed_pages("doc", "ver", payload, page_count=3)


def test_confirmed_pages_reject_out_of_inventory_physical_page():
    from apps.api.disposable_signed_brief_publisher import _confirmed_pages
    with pytest.raises(ValueError):
        _confirmed_pages("doc", "ver", [{"pdf_page": 5}], page_count=3)


def test_confirmed_pages_reject_mappings_on_unpaginated_source():
    from apps.api.disposable_signed_brief_publisher import _confirmed_pages
    with pytest.raises(ValueError):
        _confirmed_pages("doc", "ver", [{"pdf_page": 1}], page_count=None)


def test_unpaginated_marker_must_be_sole_row():
    from domains.disputes.exhibits import ExhibitEntry, ExhibitError, ExhibitPage
    single = ExhibitEntry("e1", "Stuk 1", (ExhibitPage("s1", "v1"),), confirmed=True)
    assert single.pages[0].unpaginated
    with pytest.raises(ExhibitError):
        ExhibitEntry(
            "e2", "Stuk 2",
            (ExhibitPage("s1", "v1"), ExhibitPage("s1", "v1", pdf_page=1)),
            confirmed=True,
        )


# --- Live RPC transport + adapter contracts (no live calls) -----------------

class _StubResponse:
    def __init__(self, status, body=b""):
        self.status = status
        self._body = body

    def read(self, _limit=-1):
        return self._body


class _StubConn:
    def __init__(self, status=200, body=b"{}", error=None):
        self._response = _StubResponse(status, body)
        self._error = error
        self.requests = []
        self.closed = False

    def request(self, method, path, body=None, headers=None):
        if self._error is not None:
            raise self._error
        self.requests.append((method, path, body, headers))

    def getresponse(self):
        return self._response

    def close(self):
        self.closed = True


def _rpc_with(conn):
    from apps.api.signed_supabase_rpc import call_rpc
    return call_rpc(publishable_key="sb_publishable_testkey", bearer="jwt",
                    name="caseproof_signed_test", args={"p_case": "x"},
                    _conn_factory=lambda: conn)


def test_live_rpc_transport_contract():
    import json as jsonlib

    from apps.api.signed_supabase_originals import (
        PrivateStorageDenied,
        PrivateStorageFailure,
        PrivateStorageOutcomeUnknown,
    )
    conn = _StubResponse is None or _StubConn(200, jsonlib.dumps({"ok": True}).encode())
    assert _rpc_with(conn) == {"ok": True}
    method, path, body, headers = conn.requests[0]
    assert (method, path) == ("POST", "/rest/v1/rpc/caseproof_signed_test")
    assert headers["apikey"] == "sb_publishable_testkey"
    assert headers["Authorization"] == "Bearer jwt"
    assert jsonlib.loads(body.decode()) == {"p_case": "x"}
    assert conn.closed
    with pytest.raises(PrivateStorageDenied):
        _rpc_with(_StubConn(403, b"{}"))
    with pytest.raises(PrivateStorageDenied):
        _rpc_with(_StubConn(400, jsonlib.dumps({"code": "PGRST202"}).encode()))
    with pytest.raises(PrivateStorageOutcomeUnknown):
        _rpc_with(_StubConn(error=OSError("down")))
    with pytest.raises(PrivateStorageFailure):
        _rpc_with(_StubConn(200, b"not-json"))
    with pytest.raises(PrivateStorageFailure):
        _rpc_with(_StubConn(500, b"{}"))


def test_live_rpc_transport_rejects_bad_input():
    from apps.api.signed_supabase_rpc import call_rpc
    for kwargs in (
        {"publishable_key": "sb_secret_nope"},
        {"bearer": ""},
        {"bearer": "a\r\nb"},
        {"name": "drop table"},
        {"args": ["not-a-dict"]},
        {"args": {"p_case": "x" * 16384}},
    ):
        merged = {"publishable_key": "sb_publishable_testkey", "bearer": "jwt",
                  "name": "caseproof_signed_test", "args": {}, **kwargs}
        with pytest.raises(ValueError):
            call_rpc(**merged)


def _publisher_stub(result):
    from apps.api.signed_supabase_brief_publisher import LiveSignedBriefPublisher
    calls = []

    def fake_rpc(*, publishable_key, bearer, name, args):
        calls.append((name, args))
        return result(calls) if callable(result) else result

    return LiveSignedBriefPublisher(call_rpc=fake_rpc, publishable_key="sb_publishable_k"), calls


_UUID_A = "0" * 8 + "-0000-4000-8000-" + "0" * 12
_UUID_B = "1" * 8 + "-0000-4000-8000-" + "1" * 12
_UUID_C = "2" * 8 + "-0000-4000-8000-" + "2" * 12
_SHA = "a" * 64


def _live_publish_kwargs():
    import hashlib
    rep = "Mémoire synthétique."
    graph = "graphe synthétique v1"
    return {
        "bearer": "jwt", "case_id": _UUID_A, "document_id": _UUID_B, "version_id": _UUID_C,
        "intent_id": "3" * 8 + "-0000-4000-8000-" + "3" * 12,
        "document_role": "own_draft", "expected_revision": 1,
        "brief_version_id": "4" * 8 + "-0000-4000-8000-" + "4" * 12,
        "request_id": "5" * 8 + "-0000-4000-8000-" + "5" * 12,
        "representation": rep,
        "representation_sha256": hashlib.sha256(rep.encode("utf-8")).hexdigest(),
        "parser_id": "parser-synthétique-v1",
        "references": [{"reference_id": "ref-1", "exhibit_label": "Contrat",
                        "exact_quote": "paiement", "pdf_page": 2}],
        "assertions": [{"claim_id": "c1", "reference_id": "ref-1", "text_start": 0,
                        "text_end": 7, "assertion_text": rep[0:7], "kind": "money",
                        "fact_role": "payment", "language": "fr", "source_language": "nl"}],
        "graph_text": graph,
        "graph_sha256": hashlib.sha256(graph.encode("utf-8")).hexdigest(),
    }


def test_live_publisher_publish_contract():
    import hashlib
    import uuid
    publisher, calls = _publisher_stub({"ok": True, "replay": False, "revision": 2})
    kwargs = _live_publish_kwargs()
    outcome = publisher.publish_uploaded(**kwargs)
    assert outcome.published_revision == 2
    assert outcome.brief_version_id == kwargs["brief_version_id"]
    name, args = calls[0]
    assert name == "caseproof_signed_publish_uploaded"
    raw = bytearray(
        hashlib.sha256(f"caseproof-working-brief:own_draft:{_UUID_A}".encode()).digest()[:16])
    raw[6] = (raw[6] & 0x0F) | 0x40
    raw[8] = (raw[8] & 0x3F) | 0x80
    assert args["p_brief"] == str(uuid.UUID(bytes=bytes(raw)))
    assert outcome.brief_id == args["p_brief"]
    assert args["p_expected"] == 1 and args["p_intent"] == kwargs["intent_id"]
    assert args["p_references"] == kwargs["references"]
    assert args["p_assertions"] == kwargs["assertions"]
    assert args["p_representation"] == kwargs["representation"]
    assert args["p_representation_sha"] == kwargs["representation_sha256"]
    assert args["p_graph_sha"] == kwargs["graph_sha256"]


def test_live_publisher_confirm_exhibit_mappings_contract():
    import hashlib
    import json
    existing = {"exhibit_id": "piece-aaa111bbb222", "display_label": "Contrat", "aliases": [],
                "confirmed": True, "manual_inclusion": False,
                "pages": [{"source_id": _UUID_B, "version_id": _UUID_C, "pdf_page": 1,
                           "printed_page": None, "bundle_page": None}]}

    def stub(calls):
        if calls[-1][0] == "caseproof_signed_exhibit_register":
            return {"ok": True, "register_revision": 3,
                    "payload": {"schema": "caseproof-exhibit-register-v1", "entries": [existing]},
                    "media_type": "application/pdf", "page_count": 3}
        return {"ok": True, "exhibit_revision": 4, "replay": False}

    publisher, calls = _publisher_stub(stub)
    confirmed = publisher.confirm_exhibit(
        bearer="jwt", case_id=_UUID_A, document_id=_UUID_B, version_id=_UUID_C,
        display_label="Pièce 4",
        page_mappings=[{"pdf_page": 1, "printed_page": 3, "bundle_page": 7}])
    assert confirmed.exhibit_revision == 4
    assert confirmed.exhibit_id.startswith("piece-")
    assert calls[0][0] == "caseproof_signed_exhibit_register"
    name, args = calls[1]
    assert name == "caseproof_signed_confirm_exhibit"
    assert args["p_expected"] == 3
    assert args["p_sha"] == hashlib.sha256(args["p_payload"].encode("utf-8")).hexdigest()
    register = json.loads(args["p_payload"])
    assert register["schema"] == "caseproof-exhibit-register-v1"
    assert register["entries"][0] == existing
    new = register["entries"][1]
    assert new["exhibit_id"] == confirmed.exhibit_id
    assert new["display_label"] == "Pièce 4" and new["confirmed"] is True
    assert new["manual_inclusion"] is False and new["aliases"] == []
    assert new["pages"] == [
        {"source_id": _UUID_B, "version_id": _UUID_C, "pdf_page": 1,
         "printed_page": 3, "bundle_page": 7},
        {"source_id": _UUID_B, "version_id": _UUID_C, "pdf_page": 2,
         "printed_page": None, "bundle_page": None},
        {"source_id": _UUID_B, "version_id": _UUID_C, "pdf_page": 3,
         "printed_page": None, "bundle_page": None}]


def test_live_publisher_error_mapping():
    from apps.api.signed_supabase_originals import PrivateStorageDenied
    for error, expected in (
        ("denied", PrivateStorageDenied),
        ("forbidden", PrivateStorageDenied),
        ("stale_revision", ValueError),
        ("duplicate_version", ValueError),
        ("conflict", ValueError),
        ("invalid", ValueError),
    ):
        publisher, _ = _publisher_stub({"ok": False, "error": error})
        with pytest.raises(expected):
            publisher.publish_uploaded(**_live_publish_kwargs())


def test_live_publisher_strict_response_and_input():
    from apps.api.signed_supabase_originals import PrivateStorageFailure
    bad_results = [
        {"ok": True, "replay": False, "revision": "1"},
        {"ok": True, "revision": 1},
        {"ok": True, "replay": False},
        ["not-a-dict"],
    ]
    for result in bad_results:
        publisher, _ = _publisher_stub(result)
        with pytest.raises(PrivateStorageFailure):
            publisher.publish_uploaded(**_live_publish_kwargs())
    publisher, _ = _publisher_stub({"ok": True, "replay": False, "revision": 2})
    bad_inputs = []
    wrong_sha = _live_publish_kwargs()
    wrong_sha["representation_sha256"] = "0" * 64
    bad_inputs.append(wrong_sha)
    dup_refs = _live_publish_kwargs()
    dup_refs["references"] = dup_refs["references"] * 2
    bad_inputs.append(dup_refs)
    ghost_ref = _live_publish_kwargs()
    ghost_ref["assertions"] = [dict(ghost_ref["assertions"][0], reference_id="fantôme")]
    bad_inputs.append(ghost_ref)
    bad_role = _live_publish_kwargs()
    bad_role["document_role"] = "judge"
    bad_inputs.append(bad_role)
    for kwargs in bad_inputs:
        with pytest.raises(ValueError):
            publisher.publish_uploaded(**kwargs)
    publisher, _ = _publisher_stub({"ok": True, "exhibit_id": _UUID_A, "exhibit_revision": 1})
    for bad_mappings in (
        [{"pdf_page": 1}, {"pdf_page": 1}],
        [{"pdf_page": "1"}],
        [{"printed_page": 3}],
        [{"pdf_page": 1, "unknown": 2}],
        [{"pdf_page": 0}],
        "not-a-list",
    ):
        with pytest.raises(ValueError):
            publisher.confirm_exhibit(
                bearer="jwt", case_id=_UUID_A, document_id=_UUID_B, version_id=_UUID_C,
                display_label="Pièce 4", page_mappings=bad_mappings)
    with pytest.raises(ValueError):
        publisher.register_source_version(
            bearer="jwt", case_id=_UUID_A, label="x", media_type="application/x-msdownload",
            byte_length=1, sha256_hex=_SHA)


def test_live_publisher_register_and_list_contract():
    publisher, calls = _publisher_stub(lambda calls: (
        {"ok": True, "document_id": _UUID_B, "version_id": _UUID_C}
        if calls[-1][0] == "caseproof_signed_register_source"
        else {"ok": True, "documents": [
            {"document_id": _UUID_B, "label": "conclusions",
             "versions": [{"version_id": _UUID_C, "version_number": 1,
                           "media_type": "application/pdf", "byte_length": 100,
                           "sha256_hex": _SHA}]}]}
    ))
    registration = publisher.register_source_version(
        bearer="jwt", case_id=_UUID_A, label="conclusions", media_type="application/pdf",
        byte_length=100, sha256_hex=_SHA)
    assert registration.document_id == _UUID_B
    documents = publisher.list_documents(bearer="jwt", case_id=_UUID_A)
    assert len(documents) == 1
    assert documents[0].versions[0].sha256_hex == _SHA


def _raw_record_fixture(actor=None):
    import json as _json

    actor = actor or _UUID_A
    version = "bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb"
    snapshot = "f" * 64
    payload = _json.dumps({"schema": "caseproof-m2-check-headless-v1"})
    request_id = "cccccccc-3333-4333-8333-cccccccccccc"
    decision = {"actor_id": actor, "disposition": "verified",
                "observation_id": "citation:ref-01", "rationale": "contrôle synthétique"}
    # Known-answer vector, frozen out of the implementation under test: if
    # the canonicalization or digest ever drifts, the assembly replay rejects
    # this fixture instead of self-validating the same bug.
    event_sha = "a9a3aa5c9c6ecfe5244696091622e64deafb0220d55cfef9923bde6d47e65ab9"
    payload_sha = "a7254fa5a8ceedb1db20175b94f7b062f77c0c737728adb1fbe0798875ab506c"
    brief = {"brief_id": "dddddddd-4444-4444-8444-dddddddddddd", "head_revision": 1,
             "version_id": version, "graph_sha256": "1" * 64, "original_sha256": "2" * 64,
             "document_id": "eeeeeeee-5555-4555-8555-eeeeeeeeeeee",
             "document_version_id": "ffffffff-6666-4666-8666-ffffffffffff",
             "case_revision": 1, "exhibit_revision": 1}
    checks = [{"snapshot_sha256": snapshot, "payload_sha256": payload_sha,
               "case_revision": 1, "exhibit_revision": 1, "payload": payload}]
    heads = [{"snapshot_sha256": snapshot, "event_sha256": event_sha}]
    events = [{"snapshot_sha256": snapshot, "revision": 1, "request_id": request_id,
               "actor_id": actor, "event_sha256": event_sha,
               "decision": _json.dumps(decision, ensure_ascii=False, sort_keys=True,
                                       separators=(",", ":"))}]
    return {"ok": True, "brief": brief, "checks": checks,
            "review_heads": heads, "review_events": events}


def test_live_review_record_contract_and_signature():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )

    from apps.api.disposable_review_record import SIGNATURE_DOMAIN, _canonical
    from apps.api.signed_supabase_review_record import LiveSignedReviewRecord
    key = Ed25519PrivateKey.generate()
    seed = key.private_bytes_raw()
    calls = []
    raw = _raw_record_fixture()

    def fake_rpc(*, publishable_key, bearer, name, args):
        calls.append((name, args))
        return dict(raw)

    record_port = LiveSignedReviewRecord(
        call_rpc=fake_rpc, publishable_key="sb_publishable_k", signing_key=seed)
    signed = record_port.record(bearer="jwt", case_id=_UUID_A, document_role="own_draft")
    assert calls == [("caseproof_signed_review_record",
                      {"p_case": _UUID_A, "p_role": "own_draft"})]
    assert signed["schema"] == "caseproof-review-record-v1"
    assert signed["checks"][0]["payload_sha256_verified"] is True
    assert signed["reviews"][0]["chain_verified"] is True
    receipt = signed.pop("receipt")
    assert receipt["scheme"] == "ed25519" and receipt["domain"] == SIGNATURE_DOMAIN
    public = Ed25519PublicKey.from_public_bytes(bytes.fromhex(receipt["public_key"]))
    public.verify(bytes.fromhex(receipt["signature"]),
                  _canonical({"domain": SIGNATURE_DOMAIN, "record": signed}).encode())
    unsigned = LiveSignedReviewRecord(call_rpc=fake_rpc, publishable_key="sb_publishable_k")
    assert "receipt" not in unsigned.record(
        bearer="jwt", case_id=_UUID_A, document_role="own_draft")


def test_live_review_record_denial_and_shape():
    from apps.api.signed_supabase_originals import PrivateStorageDenied, PrivateStorageFailure
    from apps.api.signed_supabase_review_record import LiveSignedReviewRecord
    denied = LiveSignedReviewRecord(
        call_rpc=lambda **kwargs: {"ok": False, "error": "denied"},
        publishable_key="sb_publishable_k")
    with pytest.raises(PrivateStorageDenied):
        denied.record(bearer="jwt", case_id=_UUID_A, document_role="own_draft")
    for bad in (
        {"ok": True, "brief": "not-a-dict"},
        {"ok": True, "brief": {}, "checks": "not-a-list"},
        {"ok": False, "error": "weird"},
        "not-a-dict",
    ):
        port = LiveSignedReviewRecord(call_rpc=lambda **kwargs: bad,  # noqa: B023
                                      publishable_key="sb_publishable_k")
        with pytest.raises(PrivateStorageFailure):
            port.record(bearer="jwt", case_id=_UUID_A, document_role="own_draft")


def test_live_review_record_replay_rejects_tamper():
    from apps.api.signed_supabase_originals import PrivateStorageFailure
    from apps.api.signed_supabase_review_record import LiveSignedReviewRecord
    raw = _raw_record_fixture()

    def variant(**mutate):
        import copy

        body = copy.deepcopy(raw)
        for key_path, value in mutate.items():
            target = body
            parts = key_path.split(".")
            for part in parts[:-1]:
                target = target[int(part)] if isinstance(target, list) else target[part]
            last = parts[-1]
            if isinstance(target, list):
                target[int(last)] = value
            else:
                target[last] = value
        return body

    tampered_event = variant(**{"review_events.0.decision": '{"actor_id":"' + _UUID_A
                                + '","disposition":"verified","observation_id":'
                                  '"citation:ref-01","rationale":"ALTÉRÉ"}'})
    wrong_head = variant(**{"review_heads.0.event_sha256": "9" * 64})
    bad_payload = variant(**{"checks.0.payload_sha256": "9" * 64})
    for body in (tampered_event, wrong_head, bad_payload):
        port = LiveSignedReviewRecord(call_rpc=lambda **kwargs: body,  # noqa: B023
                                      publishable_key="sb_publishable_k")
        with pytest.raises(PrivateStorageFailure):
            port.record(bearer="jwt", case_id=_UUID_A, document_role="own_draft")


def test_qr_payload_is_bounded_and_text_free():
    from apps.api.review_record_qr import build_qr_payload

    digest = "a" * 64
    pubkey = "b" * 64
    signed = {"record_sha256": digest, "receipt": {"public_key": pubkey}}
    payload = build_qr_payload(signed)
    assert payload == f"caseproof-review-record-v1|sha256:{digest}|key:{pubkey}"
    assert len(payload) <= 256
    assert "http" not in payload
    unsigned = build_qr_payload({"record_sha256": digest})
    assert unsigned == f"caseproof-review-record-v1|sha256:{digest}|key:unsigned"
    with pytest.raises(ValueError):
        build_qr_payload({"record_sha256": "not-a-digest"})
    with pytest.raises(ValueError):
        build_qr_payload({"record_sha256": digest, "receipt": {"public_key": "not-hex!"}})
    with pytest.raises(ValueError):
        build_qr_payload({"record_sha256": digest, "receipt": "tampered"})


def test_qr_png_renders_and_is_deterministic():
    from apps.api.review_record_qr import build_qr_payload, render_qr_png

    payload = build_qr_payload({"record_sha256": "c" * 64,
                                "receipt": {"public_key": "d" * 64}})
    png = render_qr_png(payload)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert png == render_qr_png(payload)
    assert render_qr_png(payload + "x") != png
    assert len(png) < 16384


def test_live_ports_absent_without_configuration():
    from apps.api.signed_live_composition import live_signed_ports

    assert live_signed_ports({}) is None
    assert live_signed_ports({"CASEPROOF_REVIEW_RECORD_SIGNING_KEY_HEX": "ab" * 32}) is None


def test_live_ports_composition_validation():
    from apps.api.signed_live_composition import live_signed_ports

    key = "sb_publishable_" + "A" * 24
    publisher, record = live_signed_ports({"CASEPROOF_SUPABASE_PUBLISHABLE_KEY": key})
    assert publisher is not None and record is not None
    with pytest.raises(ValueError):
        live_signed_ports({"CASEPROOF_SUPABASE_PUBLISHABLE_KEY": "sb_secret_" + "A" * 24})
    with pytest.raises(ValueError):
        live_signed_ports({"CASEPROOF_SUPABASE_PUBLISHABLE_KEY": "not-a-key"})
    with pytest.raises(ValueError):
        live_signed_ports({"CASEPROOF_SUPABASE_PUBLISHABLE_KEY": key,
                           "CASEPROOF_REVIEW_RECORD_SIGNING_KEY_HEX": "not-hex"})
    with pytest.raises(ValueError):
        live_signed_ports({"CASEPROOF_SUPABASE_PUBLISHABLE_KEY": key,
                           "CASEPROOF_REVIEW_RECORD_SIGNING_KEY_HEX": "ab"})


def test_workbench_documents_route_uses_wired_live_publisher():
    from apps.api.signed_supabase_brief_publisher import LiveSignedBriefPublisher

    case_id = "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa"
    calls = []

    def stub_rpc(*, publishable_key, bearer, name, args):
        calls.append((publishable_key, bearer, name, args))
        return {"ok": True, "documents": [{"document_id": case_id, "label": "synthétique",
                                           "versions": []}]}

    key = "sb_publishable_" + "B" * 24
    publisher = LiveSignedBriefPublisher(call_rpc=stub_rpc, publishable_key=key)
    search, _ = search_rig()
    reader = AuthorizedOriginalReader(search.checker, Originals())
    client = TestClient(
        create_litigation_development_app(checker=search.checker, originals=reader,
                                          signed_brief_publisher=publisher),
        client=("127.0.0.1", 50000),
    )
    response = client.get(f"/dev/signed/matters/{case_id}/documents",
                          headers={"Authorization": "Bearer signed-user-token"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema"] == "caseproof-signed-documents-v1"
    assert body["documents"][0]["document_id"] == case_id
    assert calls == [(key, "signed-user-token", "caseproof_signed_list_documents",
                      {"p_case": case_id})]


def test_workbench_without_wired_publisher_stays_503():
    search, _ = search_rig()
    reader = AuthorizedOriginalReader(search.checker, Originals())
    client = TestClient(create_litigation_development_app(checker=search.checker, originals=reader),
                        client=("127.0.0.1", 50000))
    response = client.get(f"/dev/signed/matters/{CASE}/documents",
                          headers={"Authorization": "Bearer signed-user-token"})
    assert response.status_code == 503


def test_live_workbench_assembly_refuses_mixed_backends():
    from apps.api.signed_live_composition import assemble_live_workbench

    with pytest.raises(ValueError):
        assemble_live_workbench({})
    key = "sb_publishable_" + "C" * 24
    ports = assemble_live_workbench({"CASEPROOF_SUPABASE_PUBLISHABLE_KEY": key})
    from apps.api.signed_supabase_brief_publisher import LiveSignedBriefPublisher
    from apps.api.signed_supabase_review_record import LiveSignedReviewRecord

    assert isinstance(ports.publisher, LiveSignedBriefPublisher)
    assert isinstance(ports.review_record, LiveSignedReviewRecord)
    assert "SignedReviewWorkspace" in ports.missing
    assert "AuthorizedLitigationChecker" in ports.missing


def test_live_workbench_entry_point_fails_closed():
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "run_signed_workbench_live.py"
    no_config = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                               env={"PYTHONPATH": str(root), "PATH": "/usr/bin:/bin"}, check=False)
    assert no_config.returncode == 2
    configured = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True,
        env={"PYTHONPATH": str(root), "PATH": "/usr/bin:/bin",
             "CASEPROOF_SUPABASE_PUBLISHABLE_KEY": "sb_publishable_" + "D" * 24}, check=False)
    assert configured.returncode == 3
    assert "fail-closed" in configured.stderr


def test_signed_review_record_rpc_access_and_contract():
    """Proposed read RPC (db/proposals): real access denial + bounded contract.

    Runs only on the disposable PostgreSQL cluster; never applied to live.
    """
    import json
    import os
    from pathlib import Path
    from uuid import uuid4

    if os.environ.get("CASEPROOF_DISPOSABLE_DB") != "YES":
        pytest.skip("disposable PostgreSQL required")
    from psycopg import errors

    from apps.api.disposable_litigation_review_ledger import ZERO_HASH, _canonical, _digest
    from scripts.verify_vault_integration import connect

    proposal = (
        Path(__file__).resolve().parents[1] / "db" / "proposals" / "SIGNED_review_record_read.sql"
    ).read_text(encoding="utf-8")
    org, case, brief, version = uuid4(), uuid4(), uuid4(), uuid4()
    doc, doc_version = uuid4(), uuid4()
    user_a, user_b, user_c = uuid4(), uuid4(), uuid4()
    snapshot = "a" * 64
    payload = json.dumps({"schema": "caseproof-m2-check-headless-v1"})
    payload_sha = _digest(payload)
    decision = {"actor_id": str(user_a), "disposition": "verified",
                "observation_id": "citation:ref-01", "rationale": "contrôle synthétique"}
    request_id, audit_id = uuid4(), uuid4()
    event_sha = _digest(_canonical({
        "run": snapshot, "revision": 1, "request": str(request_id),
        "actor": str(user_a), "previous_sha": ZERO_HASH, "decision": decision}))
    with connect() as conn:
        conn.execute(
            "create or replace function auth.jwt() returns jsonb language sql stable as "
            "$$ select nullif(current_setting('request.jwt.claims', true), '')::jsonb $$")
        conn.execute(proposal)
        conn.execute("insert into caseproof.organizations(id, display_name) values(%s, %s)",
                     (org, "synthétique"))
        conn.execute("insert into auth.users(id, instance_id) values(%s, %s),(%s, %s),(%s, %s) "
                     "on conflict (id) do nothing",
                     (user_a, org, user_b, org, user_c, org))
        conn.execute(
            "insert into caseproof.organization_members(org_id, user_id, actions)"
            " values(%s, %s, array['case:read','evidence:read']::text[]),"
            " (%s, %s, array['case:read','evidence:read']::text[])",
            (org, user_a, org, user_b))
        conn.execute(
            "insert into caseproof.cases(id, org_id, created_by_user, effective_policy_version)"
            " values(%s, %s, %s, 'v1')", (case, org, user_a))
        conn.execute(
            "insert into caseproof._m1_matter_grants(org_id, case_id, user_id, role, permissions)"
            " values(%s, %s, %s, 'reviewer', array['case:read','evidence:read']::text[])",
            (org, case, user_a))
        conn.execute(
            "insert into caseproof.documents(id, org_id, case_id, source_label)"
            " values(%s, %s, %s, 'synthétique')", (doc, org, case))
        conn.execute(
            "insert into caseproof.document_versions(id, org_id, document_id, version_number,"
            " original_sha256_hex, byte_length, media_type)"
            " values(%s, %s, %s, 1, %s, 4, 'text/plain')", (doc_version, org, doc, "b" * 64))
        conn.execute(
            "insert into caseproof._m2_brief_versions(org_id, case_id, brief_id, version_id,"
            " revision, document_id, document_version_id, vault_intent_id, original_sha256,"
            " representation_sha256, parser_id, representation, document_role, graph_sha256,"
            " case_revision, exhibit_revision, actor_id)"
            " values(%s,%s,%s,%s,1,%s,%s,%s,%s,%s,'synthetic-parser','{}','own_draft',%s,1,1,%s)",
            (org, case, brief, version, doc, doc_version, uuid4(), "b" * 64, "c" * 64,
             "d" * 64, user_a))
        conn.execute(
            "insert into caseproof._m2_brief_heads(org_id, case_id, brief_id, revision, version_id)"
            " values(%s, %s, %s, 1, %s)", (org, case, brief, version))
        conn.execute(
            "insert into caseproof._m2_check_runs(org_id, case_id, snapshot_sha, payload_sha,"
            " payload, brief_version_id, case_revision, exhibit_revision, actor_id)"
            " values(%s, %s, %s, %s, %s, %s, 1, 1, %s)",
            (org, case, snapshot, payload_sha, payload, str(version), user_a))
        conn.execute(
            "insert into caseproof.audit_events(id, org_id, case_id, actor_type,"
            " actor_user_id, action, event_schema_version, correlation_id, input_sha256_hex)"
            " values(%s, %s, %s, 'human', %s, 'review', 'v1', %s, %s)",
            (audit_id, org, case, user_a, uuid4(), "e" * 64))
        conn.execute(
            "insert into caseproof._m2_review_events(org_id, case_id, snapshot_sha, revision,"
            " request_id, actor_id, previous_sha, event_sha, decision, audit_id)"
            " values(%s, %s, %s, 1, %s, %s, %s, %s, %s, %s)",
            (org, case, snapshot, request_id, user_a, ZERO_HASH, event_sha,
             json.dumps(decision, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
             audit_id))
        conn.execute(
            "insert into caseproof._m2_review_heads(org_id, case_id, snapshot_sha, revision,"
            " event_sha) values(%s, %s, %s, 1, %s)", (org, case, snapshot, event_sha))

        def call(sub, role="authenticated", doc_role="own_draft"):
            claims = json.dumps({"role": role, "is_anonymous": "false"})
            conn.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(sub),))
            conn.execute("select set_config('request.jwt.claims', %s, true)", (claims,))
            return conn.execute(
                "select public.caseproof_signed_review_record(%s, %s)",
                (str(case), doc_role)).fetchone()[0]

        result = call(user_a)
        assert result["ok"] is True
        assert result["brief"]["version_id"] == str(version)
        assert result["brief"]["head_revision"] == 1
        assert len(result["checks"]) == 1
        assert result["checks"][0]["payload_sha256"] == payload_sha
        assert result["review_heads"] == [
            {"snapshot_sha256": snapshot, "event_sha256": event_sha}]
        assert len(result["review_events"]) == 1
        assert result["review_events"][0]["event_sha256"] == event_sha

        for sub, role, doc_role in (
            (user_b, "authenticated", "own_draft"),  # member without matter grant
            (user_c, "authenticated", "own_draft"),  # not a member at all
            (user_a, "anon", "own_draft"),           # not the authenticated role
            (user_a, "authenticated", "judge"),      # unknown document role
            (uuid4(), "authenticated", "own_draft"),  # unknown subject
        ):
            with conn.transaction(force_rollback=True):
                with pytest.raises(errors.InsufficientPrivilege):
                    call(sub, role, doc_role)
        # Unknown case is masked the same way as a denied one.
        with conn.transaction(force_rollback=True):
            conn.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(user_a),))
            with pytest.raises(errors.InsufficientPrivilege):
                conn.execute("select public.caseproof_signed_review_record(%s, 'own_draft')",
                             (str(uuid4()),))


def test_signed_document_inventory_proposal_rpc_access_and_contract():
    import json
    import os
    from pathlib import Path
    from uuid import uuid4

    if os.environ.get("CASEPROOF_DISPOSABLE_DB") != "YES":
        pytest.skip("disposable PostgreSQL required")
    from psycopg import errors

    from scripts.verify_vault_integration import connect

    proposal = (
        Path(__file__).resolve().parents[1] / "db" / "proposals" / "SIGNED_document_inventory.sql"
    ).read_text(encoding="utf-8")
    org, case = uuid4(), uuid4()
    user_a, user_b, user_c, user_d = uuid4(), uuid4(), uuid4(), uuid4()
    with connect() as conn:
        conn.execute(
            "create or replace function auth.jwt() returns jsonb language sql stable as "
            "$$ select nullif(current_setting('request.jwt.claims', true), '')::jsonb $$")
        conn.execute(proposal)
        conn.execute("insert into caseproof.organizations(id, display_name) values(%s, %s)",
                     (org, "synthétique"))
        conn.execute("insert into auth.users(id, instance_id) values(%s, %s),(%s, %s),(%s, %s),"
                     "(%s, %s) on conflict (id) do nothing",
                     (user_a, org, user_b, org, user_c, org, user_d, org))
        # user_a: full reviewer member; user_b: member without write actions;
        # user_c: not a member; user_d: member with read actions but a viewer grant.
        conn.execute(
            "insert into caseproof.organization_members(org_id, user_id, actions)"
            " values(%s, %s, array['case:read','evidence:read','finding:write','review:request']::text[]),"
            " (%s, %s, array['case:read','evidence:read']::text[]),"
            " (%s, %s, array['case:read','evidence:read','finding:write','review:request']::text[])",
            (org, user_a, org, user_b, org, user_d))
        conn.execute(
            "insert into caseproof.cases(id, org_id, created_by_user, effective_policy_version)"
            " values(%s, %s, %s, 'v1')", (case, org, user_a))
        conn.execute(
            "insert into caseproof._m1_matter_grants(org_id, case_id, user_id, role, permissions)"
            " values(%s, %s, %s, 'reviewer', array['case:read','evidence:read','evidence:upload']::text[]),"
            " (%s, %s, %s, 'viewer', array['case:read','evidence:read']::text[])",
            (org, case, user_a, org, case, user_d))

        def as_user(sub, role="authenticated"):
            claims = json.dumps({"role": role, "is_anonymous": "false"})
            conn.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(sub),))
            conn.execute("select set_config('request.jwt.claims', %s, true)", (claims,))

        def register(sub, label="pièce synthétique", media="text/plain", size=4,
                     sha="b" * 64, role="authenticated"):
            as_user(sub, role)
            return conn.execute(
                "select public.caseproof_signed_register_source(%s, %s, %s, %s, %s)",
                (str(case), label, media, size, sha)).fetchone()[0]

        def listing(sub, role="authenticated"):
            as_user(sub, role)
            return conn.execute("select public.caseproof_signed_list_documents(%s)",
                                (str(case),)).fetchone()[0]

        # Happy path: register declares the document and its first version,
        # the inventory lists them in the bounded contract shape.
        created = register(user_a)
        assert created["ok"] is True
        document_id, version_id = created["document_id"], created["version_id"]
        result = listing(user_a)
        assert result["ok"] is True
        assert len(result["documents"]) == 1
        document = result["documents"][0]
        assert document["document_id"] == document_id
        assert document["label"] == "pièce synthétique"
        assert document["versions"] == [{
            "version_id": version_id, "version_number": 1, "media_type": "text/plain",
            "byte_length": 4, "sha256_hex": "b" * 64}]

        # Invalid declarations are contract errors, never silent inserts.
        for label, media, size, sha in (
            ("", "text/plain", 4, "b" * 64),
            ("x" * 201, "text/plain", 4, "b" * 64),
            ("saut\nde ligne", "text/plain", 4, "b" * 64),
            ("pièce", "application/zip", 4, "b" * 64),
            ("pièce", "text/plain", 0, "b" * 64),
            ("pièce", "text/plain", 3145729, "b" * 64),
            ("pièce", "text/plain", 4, "B" * 64),
            ("pièce", "text/plain", 4, "b" * 63),
        ):
            with conn.transaction(force_rollback=True):
                outcome = register(user_a, label=label, media=media, size=size, sha=sha)
                assert outcome == {"ok": False, "error": "invalid"}
        assert conn.execute("select count(*) from caseproof.documents where case_id=%s",
                            (str(case),)).fetchone()[0] == 1

        # Reads denied: member without grant, non-member, anonymous role, unknown case.
        for sub, role in ((user_b, "authenticated"), (user_c, "authenticated"),
                          (user_a, "anon"), (uuid4(), "authenticated")):
            with conn.transaction(force_rollback=True):
                with pytest.raises(errors.InsufficientPrivilege):
                    listing(sub, role)
        with conn.transaction(force_rollback=True):
            as_user(user_a)
            with pytest.raises(errors.InsufficientPrivilege):
                conn.execute("select public.caseproof_signed_list_documents(%s)",
                             (str(uuid4()),))

        # Writes denied: read-only member actions, viewer grant role, non-member,
        # anonymous role; an unknown case is masked the same way.
        for sub, role in ((user_b, "authenticated"), (user_d, "authenticated"),
                          (user_c, "authenticated"), (user_a, "anon"),
                          (uuid4(), "authenticated")):
            with conn.transaction(force_rollback=True):
                with pytest.raises(errors.InsufficientPrivilege):
                    register(sub, role=role)
        with conn.transaction(force_rollback=True):
            as_user(user_a)
            with pytest.raises(errors.InsufficientPrivilege):
                conn.execute(
                    "select public.caseproof_signed_register_source(%s, 'pièce', 'text/plain',"
                    " 4, %s)", (str(uuid4()), "b" * 64))
        assert conn.execute("select count(*) from caseproof.documents where case_id=%s",
                            (str(case),)).fetchone()[0] == 1


def test_signed_exhibit_confirm_proposal_rpc_access_and_contract():
    import json
    import os
    from pathlib import Path
    from uuid import uuid4

    if os.environ.get("CASEPROOF_DISPOSABLE_DB") != "YES":
        pytest.skip("disposable PostgreSQL required")
    from psycopg import errors

    from scripts.verify_vault_integration import connect

    proposal = (
        Path(__file__).resolve().parents[1] / "db" / "proposals" / "SIGNED_exhibit_confirm.sql"
    ).read_text(encoding="utf-8")
    org, case = uuid4(), uuid4()
    user_a, user_b, user_c, user_d, user_e = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    doc_pdf, ver_pdf = uuid4(), uuid4()
    doc_txt, ver_txt = uuid4(), uuid4()

    def entry(exhibit_id, label, pages, **overrides):
        base = {"exhibit_id": exhibit_id, "display_label": label, "aliases": [],
                "confirmed": True, "manual_inclusion": False, "pages": pages}
        base.update(overrides)
        return base

    def pdf_pages(source=doc_pdf, version=ver_pdf, count=3, printed=None):
        return [{"source_id": str(source), "version_id": str(version),
                 "pdf_page": page,
                 "printed_page": printed.get(page) if printed else None,
                 "bundle_page": None}
                for page in range(1, count + 1)]

    first = entry("piece-aaa111bbb222", "Contrat synthétique", pdf_pages())
    register = {"schema": "caseproof-exhibit-register-v1", "entries": [first]}
    register_sha = "c" * 64
    with connect() as conn:
        conn.execute(
            "create or replace function auth.jwt() returns jsonb language sql stable as "
            "$$ select nullif(current_setting('request.jwt.claims', true), '')::jsonb $$")
        conn.execute(
            "drop function if exists public.caseproof_signed_confirm_exhibit"
            "(uuid,uuid,uuid,uuid,bigint,jsonb,text,jsonb)")
        conn.execute(proposal)
        conn.execute("insert into caseproof.organizations(id, display_name) values(%s, %s)",
                     (org, "synthétique"))
        conn.execute("insert into auth.users(id, instance_id) values(%s, %s),(%s, %s),(%s, %s),"
                     "(%s, %s),(%s, %s) on conflict (id) do nothing",
                     (user_a, org, user_b, org, user_c, org, user_d, org, user_e, org))
        conn.execute(
            "insert into caseproof.organization_members(org_id, user_id, actions)"
            " values(%s, %s, array['case:read','evidence:read','review:request']::text[]),"
            " (%s, %s, array['case:read','review:request']::text[]),"
            " (%s, %s, array['case:read','review:request']::text[]),"
            " (%s, %s, array['case:read','evidence:read','review:request']::text[])",
            (org, user_a, org, user_b, org, user_d, org, user_e))
        conn.execute(
            "insert into caseproof.cases(id, org_id, created_by_user, effective_policy_version)"
            " values(%s, %s, %s, 'v1')", (case, org, user_a))
        conn.execute(
            "insert into caseproof._m1_matter_grants(org_id, case_id, user_id, role, permissions)"
            " values(%s, %s, %s, 'reviewer',"
            " array['case:read','evidence:read','exhibit:confirm']::text[]),"
            " (%s, %s, %s, 'viewer', array['case:read','exhibit:confirm']::text[]),"
            " (%s, %s, %s, 'reviewer', array['case:read','evidence:read']::text[])",
            (org, case, user_a, org, case, user_d, org, case, user_e))
        conn.execute(
            "insert into caseproof.documents(id, org_id, case_id, source_label)"
            " values(%s, %s, %s, 'pdf synthétique'),(%s, %s, %s, 'txt synthétique')",
            (doc_pdf, org, case, doc_txt, org, case))
        conn.execute(
            "insert into caseproof.document_versions(id, org_id, document_id, version_number,"
            " original_sha256_hex, byte_length, media_type)"
            " values(%s, %s, %s, 1, %s, 4, 'application/pdf'),(%s, %s, %s, 1, %s, 4, 'text/plain')",
            (ver_pdf, org, doc_pdf, "b" * 64, ver_txt, org, doc_txt, "d" * 64))
        source_audit = uuid4()
        conn.execute(
            "insert into caseproof.audit_events(id, org_id, case_id, actor_type,"
            " actor_user_id, action, event_schema_version, correlation_id, input_sha256_hex)"
            " values(%s, %s, %s, 'human', %s, 'ingest', 'v1', %s, %s)",
            (source_audit, org, case, user_a, uuid4(), "a" * 64))
        conn.execute(
            "insert into caseproof._dev_journey_sources(org_id, case_id, document_id,"
            " version_id, original_sha, representation_sha, snapshot_sha, representation,"
            " audit_id) values(%s, %s, %s, %s, %s, %s, %s, 'représentation synthétique', %s)",
            (org, case, doc_pdf, ver_pdf, "b" * 64, "e" * 64, "f" * 64, source_audit))
        conn.execute(
            "insert into caseproof._dev_journey_parse_manifests(org_id, case_id, version_id,"
            " original_sha256, representation_sha256, manifest_sha256, manifest)"
            " values(%s, %s, %s, %s, %s, %s, %s::jsonb)",
            (org, case, ver_pdf, "b" * 64, "e" * 64, "f" * 64,
             json.dumps({"schema": "dev-document-parse-v1", "complete": True,
                         "blocks": [], "warnings": [],
                         "pages": [{"index": 1}, {"index": 2}, {"index": 3}]})))

        def as_user(sub, role="authenticated"):
            claims = json.dumps({"role": role, "is_anonymous": "false"})
            conn.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(sub),))
            conn.execute("select set_config('request.jwt.claims', %s, true)", (claims,))

        def canonical(payload, **dump_kwargs):
            return json.dumps(payload, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":"), **dump_kwargs)

        def digest_of(text_payload):
            import hashlib
            return hashlib.sha256(text_payload.encode("utf-8")).hexdigest()

        def confirm(sub, *, request=None, expected=0, payload=register, sha=None,
                    document=doc_pdf, version=ver_pdf, role="authenticated",
                    text_payload=None):
            as_user(sub, role)
            body = text_payload if text_payload is not None else canonical(payload)
            return conn.execute(
                "select public.caseproof_signed_confirm_exhibit"
                "(%s, %s, %s, %s, %s, %s, %s)",
                (str(case), str(document), str(version), str(request or uuid4()),
                 expected, body, sha if sha is not None else digest_of(body))).fetchone()[0]

        appended_preview = {"schema": "caseproof-exhibit-register-v1",
                            "entries": [first, entry("piece-zzz999yyy888",
                                        "Autre", pdf_pages())]}
        # Happy path: compare-and-swap commits revision 1 with audit and event.
        request = uuid4()
        outcome = confirm(user_a, request=request)
        assert outcome == {"ok": True, "exhibit_revision": 1, "replay": False}
        register_sha = digest_of(canonical(register))
        head = conn.execute(
            "select revision, payload_sha256 from caseproof._m1_exhibit_heads"
            " where case_id=%s", (str(case),)).fetchone()
        assert head == (1, register_sha)
        assert conn.execute(
            "select count(*) from caseproof._m1_exhibit_events where case_id=%s",
            (str(case),)).fetchone()[0] == 1

        # Identical replay returns the committed revision without a new write;
        # the same request with any different command is a conflict.
        assert confirm(user_a, request=request) == {
            "ok": True, "exhibit_revision": 1, "replay": True}
        assert confirm(user_a, request=request, payload=appended_preview) == {
            "ok": False, "error": "conflict"}
        assert conn.execute(
            "select count(*) from caseproof._m1_exhibit_events where case_id=%s",
            (str(case),)).fetchone()[0] == 1

        # Stale expected revision fails closed without writing.
        assert confirm(user_a, expected=0) == {"ok": False, "error": "stale_revision"}

        # A valid second confirmation appends exactly one entry.
        second = entry("piece-ccc333ddd444", "Annexe synthétique",
                       pdf_pages(printed={1: 12, 2: 13, 3: 14}))
        appended = {"schema": "caseproof-exhibit-register-v1",
                    "entries": [first, second]}
        outcome = confirm(user_a, expected=1, payload=appended)
        assert outcome == {"ok": True, "exhibit_revision": 2, "replay": False}

        # Adversarial direct calls, all refused without writing: a caller
        # reaching the RPC with the authenticated role cannot smuggle content
        # past the enforced contract.
        adversarial = [
            # rewriting history: prefix entries altered
            {"expected": 2, "payload": {"schema": "caseproof-exhibit-register-v1",
             "entries": [entry("piece-aaa111bbb222", "Falsifié", pdf_pages()), second,
                         entry("piece-eee555fff666", "Troisième", pdf_pages())]}},
            # dropping a confirmed entry
            {"expected": 2, "payload": register},
            # confirming a foreign document as pages source
            {"expected": 2, "payload": {"schema": "caseproof-exhibit-register-v1",
             "entries": [first, second, entry("piece-eee555fff666", "Troisième",
                         pdf_pages(source=doc_txt, version=ver_txt))]}},
            # shrinking the physical inventory (page 2 missing)
            {"expected": 2, "payload": {"schema": "caseproof-exhibit-register-v1",
             "entries": [first, second, entry("piece-eee555fff666", "Troisième",
                         pdf_pages(count=3)[:1] + pdf_pages(count=3)[2:])]}},
            # page beyond the manifest inventory
            {"expected": 2, "payload": {"schema": "caseproof-exhibit-register-v1",
             "entries": [first, second, entry("piece-eee555fff666", "Troisième",
                         pdf_pages(count=4))]}},
            # duplicate exhibit identity
            {"expected": 2, "payload": {"schema": "caseproof-exhibit-register-v1",
             "entries": [first, second, entry("piece-aaa111bbb222", "Doublon", pdf_pages())]}},
            # unconfirmed or manually included new entry
            {"expected": 2, "payload": {"schema": "caseproof-exhibit-register-v1",
             "entries": [first, second, entry("piece-eee555fff666", "Troisième",
                         pdf_pages(), confirmed=False)]}},
            {"expected": 2, "payload": {"schema": "caseproof-exhibit-register-v1",
             "entries": [first, second, entry("piece-eee555fff666", "Troisième",
                         pdf_pages(), manual_inclusion=True)]}},
            # case-insensitive alias colliding with the label
            {"expected": 2, "payload": {"schema": "caseproof-exhibit-register-v1",
             "entries": [first, second, entry("piece-eee555fff666", "Troisième",
                         pdf_pages(), aliases=["TROISIÈME"])]}},
            # mapping on an unpaginated source
            {"expected": 2, "document": doc_txt, "version": ver_txt,
             "payload": {"schema": "caseproof-exhibit-register-v1",
             "entries": [first, second, entry("piece-eee555fff666", "Troisième",
                         [{"source_id": str(doc_txt), "version_id": str(ver_txt),
                           "pdf_page": 1, "printed_page": None, "bundle_page": None}])]}},
            # wrong payload schema
            {"expected": 2, "payload": {"schema": "autre", "entries": []}},
        ]
        for kwargs in adversarial:
            assert confirm(user_a, **kwargs) == {"ok": False, "error": "invalid"}, kwargs
        # A non-boolean confirmed flag must be an invalid contract error, not
        # an unhandled cast exception.
        assert confirm(user_a, expected=2, payload={
            "schema": "caseproof-exhibit-register-v1",
            "entries": [first, second, entry("piece-eee555fff666", "Troisième",
                        pdf_pages(), confirmed="oui")]}) == {
            "ok": False, "error": "invalid"}
        # Digest gate: a syntactically valid but FALSE digest (64 hex) is
        # refused at write, as is a malformed one — no poisoning is possible.
        assert confirm(user_a, expected=2, payload=appended, sha="9" * 64) == {
            "ok": False, "error": "invalid"}
        assert confirm(user_a, expected=2, payload=appended, sha="E" * 64) == {
            "ok": False, "error": "invalid"}
        # A digest verified for the exact submitted bytes, however
        # serialized, commits: the digest binds bytes, jsonb binds content.
        third = {"schema": "caseproof-exhibit-register-v1",
                 "entries": [first, second, entry("piece-eee555fff666",
                             "Troisième", pdf_pages())]}
        with conn.transaction(force_rollback=True):
            outcome = confirm(user_a, expected=2, payload=third,
                              text_payload=canonical(third) + " ")
            assert outcome == {"ok": True, "exhibit_revision": 3, "replay": False}
        assert conn.execute(
            "select revision from caseproof._m1_exhibit_heads where case_id=%s",
            (str(case),)).fetchone()[0] == 2
        assert conn.execute(
            "select count(*) from caseproof._m1_exhibit_events where case_id=%s",
            (str(case),)).fetchone()[0] == 2

        # Denials: member without grant, viewer grant, non-member, anonymous
        # role, unknown subject; an unknown case is masked the same way.
        for sub, role in ((user_b, "authenticated"), (user_d, "authenticated"),
                          (user_c, "authenticated"), (user_a, "anon"),
                          (uuid4(), "authenticated")):
            with conn.transaction(force_rollback=True):
                with pytest.raises(errors.InsufficientPrivilege):
                    confirm(sub, expected=2, payload=appended, sha="d" * 64, role=role)

        # Same JSON content reserialized differently (key order, whitespace),
        # with the verified digest of THOSE bytes: content equality makes it
        # an exact replay, neither a new write nor a false conflict.
        reorder = json.dumps({"entries": [first],
                              "schema": "caseproof-exhibit-register-v1"},
                             ensure_ascii=False, indent=2)
        assert confirm(user_a, request=request, expected=0,
                       text_payload=reorder) == {
            "ok": True, "exhibit_revision": 1, "replay": True}
        assert conn.execute(
            "select count(*) from caseproof._m1_exhibit_events where case_id=%s",
            (str(case),)).fetchone()[0] == 2
        # The demanded real path: a hostile authorized caller tries to
        # poison the SHARED register with a well-formed but FALSE digest
        # (64 hex). The write is refused at the digest gate, the register
        # stays at revision 2, and ANOTHER authorized user then reads it
        # normally. No poisoning is possible at write; readers additionally
        # derive the digest from content and never gate on the stored
        # column (proven in the disposable publisher suite).
        poison = uuid4()
        assert confirm(user_a, request=poison, expected=2, payload=third,
                       sha="9" * 64) == {"ok": False, "error": "invalid"}
        assert conn.execute(
            "select revision from caseproof._m1_exhibit_heads where case_id=%s",
            (str(case),)).fetchone()[0] == 2
        as_user(user_e)
        clean_read = conn.execute(
            "select public.caseproof_signed_exhibit_register(%s, %s)",
            (str(case), str(ver_pdf))).fetchone()[0]
        assert clean_read["ok"] is True
        assert clean_read["register_revision"] == 2
        assert len(clean_read["payload"]["entries"]) == 2
        # Content validation still rejects an invalid payload even with a
        # digest correctly computed over the invalid content:
        assert confirm(user_a, expected=2, payload={
            "schema": "caseproof-exhibit-register-v1",
            "entries": [first, second, entry("piece-eee555fff666", "Falsifié",
                        pdf_pages(count=4))]}) == {"ok": False, "error": "invalid"}
        with conn.transaction(force_rollback=True):
            as_user(user_a)
            with pytest.raises(errors.InsufficientPrivilege):
                conn.execute(
                    "select public.caseproof_signed_confirm_exhibit(%s, %s, %s, %s, 2,"
                    " %s::jsonb, %s)",
                    (str(uuid4()), str(doc_pdf), str(ver_pdf), str(uuid4()),
                     json.dumps(appended), "d" * 64))

        # Preparation read RPC: raw head + media/page inventory for the
        # confirm flow, same masking rules.
        read_proposal = (
            Path(__file__).resolve().parents[1] / "db" / "proposals"
            / "SIGNED_exhibit_register_read.sql"
        ).read_text(encoding="utf-8")
        conn.execute(read_proposal)

        def read_register(sub, version=ver_pdf, role="authenticated"):
            as_user(sub, role)
            return conn.execute(
                "select public.caseproof_signed_exhibit_register(%s, %s)",
                (str(case), str(version) if version else None)).fetchone()[0]

        state = read_register(user_a)
        assert state["ok"] is True
        assert state["register_revision"] == 2
        assert state["media_type"] == "application/pdf"
        assert state["page_count"] == 3
        assert state["payload"]["schema"] == "caseproof-exhibit-register-v1"
        assert len(state["payload"]["entries"]) == 2
        txt_state = read_register(user_a, version=ver_txt)
        assert txt_state["media_type"] == "text/plain"
        assert txt_state["page_count"] is None
        for sub, role in ((user_b, "authenticated"), (user_c, "authenticated"),
                          (user_a, "anon"), (uuid4(), "authenticated")):
            with conn.transaction(force_rollback=True):
                with pytest.raises(errors.InsufficientPrivilege):
                    read_register(sub, role=role)
        with conn.transaction(force_rollback=True):
            with pytest.raises(errors.InsufficientPrivilege):
                read_register(user_a, version=uuid4())


def test_signed_publish_uploaded_proposal_rpc_access_and_contract():
    import hashlib
    import json
    import os
    from pathlib import Path
    from uuid import uuid4

    if os.environ.get("CASEPROOF_DISPOSABLE_DB") != "YES":
        pytest.skip("disposable PostgreSQL required")
    from psycopg import errors

    from scripts.verify_vault_integration import connect

    proposal = (
        Path(__file__).resolve().parents[1] / "db" / "proposals" / "SIGNED_publish_uploaded.sql"
    ).read_text(encoding="utf-8")
    org, case = uuid4(), uuid4()
    user_a, user_b, user_e = uuid4(), uuid4(), uuid4()
    doc_up, ver_up, ver_up2 = uuid4(), uuid4(), uuid4()
    doc_ex, ver_ex = uuid4(), uuid4()
    intent = uuid4()
    brief_v1, brief_v2 = uuid4(), uuid4()

    rep_text = "Mémoire synthétique: le contrat exige le paiement."
    rep_sha = hashlib.sha256(rep_text.encode("utf-8")).hexdigest()
    graph_text = "graphe synthétique v1"
    graph_sha = hashlib.sha256(graph_text.encode("utf-8")).hexdigest()
    exhibit_rep = "Contrat synthétique: paiement sous 30 jours. Livraison incluse."
    quote = "paiement sous 30 jours"

    def working_brief(role):
        raw = bytearray(hashlib.sha256(
            ("caseproof-working-brief:" + role + ":" + str(case)).encode()).digest()[:16])
        raw[6] = (raw[6] & 0x0F) | 0x40
        raw[8] = (raw[8] & 0x3F) | 0x80
        import uuid as _uuid
        return str(_uuid.UUID(bytes=bytes(raw)))

    def refs(quote_text=quote, label="contrat", pdf_page=2):
        return json.dumps([{"reference_id": "ref-1", "exhibit_label": label,
                            "exact_quote": quote_text, "pdf_page": pdf_page}])

    def assertions(start=0, end=5, text=None, ref="ref-1"):
        return json.dumps([{"claim_id": "c1", "reference_id": ref,
                            "text_start": start, "text_end": end,
                            "assertion_text": text if text is not None else rep_text[start:end],
                            "kind": "money", "fact_role": "payment",
                            "language": "fr", "source_language": "nl"}])

    exhibit_entry = {"exhibit_id": "piece-aaa111bbb222", "display_label": "Contrat",
                     "aliases": [], "confirmed": True, "manual_inclusion": False,
                     "pages": [{"source_id": str(doc_ex), "version_id": str(ver_ex),
                                "pdf_page": n, "printed_page": None, "bundle_page": None}
                               for n in (1, 2, 3)]}

    with connect() as conn:
        conn.execute(
            "create or replace function auth.jwt() returns jsonb language sql stable as "
            "$$ select nullif(current_setting('request.jwt.claims', true), '')::jsonb $$")
        conn.execute(proposal)
        conn.execute("insert into caseproof.organizations(id, display_name) values(%s, %s)",
                     (org, "synthétique"))
        conn.execute("insert into auth.users(id, instance_id) values(%s, %s),(%s, %s),(%s, %s)"
                     " on conflict (id) do nothing", (user_a, org, user_b, org, user_e, org))
        full_actions = ("array['case:read','evidence:read','finding:write','review:request']"
                        "::text[]")
        conn.execute(
            "insert into caseproof.organization_members(org_id, user_id, actions)"
            " values(%s, %s, " + full_actions + "),(%s, %s, "
            " array['case:read','review:request']::text[]),(%s, %s, " + full_actions + ")",
            (org, user_a, org, user_b, org, user_e))
        conn.execute(
            "insert into caseproof.cases(id, org_id, created_by_user, effective_policy_version)"
            " values(%s, %s, %s, 'v1')", (case, org, user_a))
        reviewer_perms = ("array['case:read','evidence:read','evidence:upload','draft:check',"
                          "'review:request']::text[]")
        conn.execute(
            "insert into caseproof._m1_matter_grants(org_id, case_id, user_id, role, permissions)"
            " values(%s, %s, %s, 'reviewer', " + reviewer_perms + "),"
            " (%s, %s, %s, 'viewer', array['case:read']::text[]),"
            " (%s, %s, %s, 'reviewer', " + reviewer_perms + ")",
            (org, case, user_a, org, case, user_b, org, case, user_e))
        conn.execute(
            "insert into caseproof.documents(id, org_id, case_id, source_label)"
            " values(%s, %s, %s, 'mémoire synthétique'),(%s, %s, %s, 'contrat synthétique')",
            (doc_up, org, case, doc_ex, org, case))
        conn.execute(
            "insert into caseproof.document_versions(id, org_id, document_id, version_number,"
            " original_sha256_hex, byte_length, media_type)"
            " values(%s, %s, %s, 1, %s, 4, 'text/plain'),(%s, %s, %s, 2, %s, 4, 'text/plain'),"
            " (%s, %s, %s, 1, %s, 4, 'application/pdf')",
            (ver_up, org, doc_up, "d" * 64, ver_up2, org, doc_up, "1" * 64,
             ver_ex, org, doc_ex, "b" * 64))
        audits = [uuid4() for _ in range(4)]
        for audit in audits:
            conn.execute(
                "insert into caseproof.audit_events(id, org_id, case_id, actor_type,"
                " actor_user_id, action, event_schema_version, correlation_id,"
                " input_sha256_hex) values(%s, %s, %s, 'human', %s, 'ingest', 'v1', %s, %s)",
                (audit, org, case, user_a, uuid4(), "a" * 64))
        conn.execute(
            "insert into caseproof._s2_009b_vault_intents(org_id, case_id, intent_id,"
            " actor_user_id, document_id, document_version_id, object_key, sha256_hex,"
            " byte_length, media_type, state, created_audit_id, created_case_revision,"
            " last_audit_id) values(%s, %s, %s, %s, %s, %s, %s, %s, 4, 'text/plain',"
            " 'verified', %s, 1, %s)",
            (org, case, intent, user_a, doc_up, ver_up,
             str(org) + "/" + str(case) + "/" + str(doc_up) + "/" + str(ver_up) + "/" + "d" * 64,
             "d" * 64, audits[0], audits[1]))
        conn.execute(
            "insert into caseproof._dev_journey_sources(org_id, case_id, document_id,"
            " version_id, original_sha, representation_sha, snapshot_sha, representation,"
            " audit_id) values(%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (org, case, doc_up, ver_up, "d" * 64, rep_sha, "2" * 64, rep_text, audits[2]))
        conn.execute(
            "insert into caseproof._dev_journey_sources(org_id, case_id, document_id,"
            " version_id, original_sha, representation_sha, snapshot_sha, representation,"
            " audit_id) values(%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (org, case, doc_ex, ver_ex, "b" * 64, "3" * 64, "4" * 64, exhibit_rep, audits[3]))
        conn.execute(
            "insert into caseproof._m1_exhibit_heads(org_id, case_id, revision, payload)"
            " values(%s, %s, 1, %s::jsonb)",
            (org, case, json.dumps({"schema": "caseproof-exhibit-register-v1",
                                    "entries": [exhibit_entry]})))

        def as_user(sub, role="authenticated"):
            claims = json.dumps({"role": role, "is_anonymous": "false"})
            conn.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(sub),))
            conn.execute("select set_config('request.jwt.claims', %s, true)", (claims,))

        def publish(sub, *, request=None, expected=0, brief=None, version=brief_v1,
                    document=doc_up, doc_version=ver_up, intent_id=intent, role="own_draft",
                    text=rep_text, text_sha=None, graph=graph_text, g_sha=None,
                    references=None, asserts=None, jwt_role="authenticated"):
            as_user(sub, jwt_role)
            return conn.execute(
                "select public.caseproof_signed_publish_uploaded"
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s)",
                (str(case), brief or working_brief(role), str(version),
                 str(request or uuid4()), expected, str(document), str(doc_version),
                 str(intent_id), role, text,
                 text_sha or hashlib.sha256(text.encode("utf-8")).hexdigest(),
                 "parser-synthétique-v1", references if references is not None else refs(),
                 asserts if asserts is not None else assertions(), graph,
                 g_sha or hashlib.sha256(graph.encode("utf-8")).hexdigest())).fetchone()[0]

        # Unauthenticated and anonymous contexts are refused before any work.
        assert publish(user_a, jwt_role="anon") == {"ok": False, "error": "invalid"}
        # Wrong working brief identity (caller cannot steer another brief's head).
        assert publish(user_a, brief=str(uuid4())) == {"ok": False, "error": "invalid"}
        # Member without the reviewer grant.
        assert publish(user_b) == {"ok": False, "error": "forbidden"}
        # Falsified representation (never derived by the trusted path).
        assert publish(user_a, text="Texte falsifié jamais vérifié") == {
            "ok": False, "error": "invalid"}
        # Correct representation but a digest over other bytes.
        assert publish(user_a, text_sha="0" * 64) == {"ok": False, "error": "invalid"}
        # Unknown intent / unverified binding.
        assert publish(user_a, intent_id=uuid4()) == {"ok": False, "error": "invalid"}
        # Reference whose quote does not occur in the exhibit's source.
        assert publish(user_a, references=refs(quote_text="citation absente")) == {
            "ok": False, "error": "invalid"}
        # Reference to an exhibit label absent from the confirmed register.
        assert publish(user_a, references=refs(label="Inconnu")) == {
            "ok": False, "error": "invalid"}
        # pdf_page outside the confirmed pages of the entry.
        assert publish(user_a, references=refs(pdf_page=9)) == {"ok": False, "error": "invalid"}
        # Assertion whose text does not match the claimed slice.
        assert publish(user_a, asserts=assertions(text="autre")) == {
            "ok": False, "error": "invalid"}
        # Assertion citing a reference that was not passed.
        assert publish(user_a, asserts=assertions(ref="fantôme")) == {
            "ok": False, "error": "invalid"}

        # Happy path: revision 1, all rows committed.
        request = uuid4()
        outcome = publish(user_a, request=request)
        assert outcome == {"ok": True, "replay": False, "revision": 1}
        head = conn.execute(
            "select revision, version_id from caseproof._m2_brief_heads"
            " where case_id=%s and brief_id=%s",
            (str(case), working_brief("own_draft"))).fetchone()
        assert head == (1, brief_v1)
        assert conn.execute(
            "select representation_sha256, graph_sha256, document_role"
            " from caseproof._m2_brief_versions where case_id=%s and version_id=%s",
            (str(case), str(brief_v1))).fetchone() == (rep_sha, graph_sha, "own_draft")
        assert conn.execute(
            "select count(*) from caseproof._m2_brief_references where case_id=%s"
            " and version_id=%s", (str(case), str(brief_v1))).fetchone()[0] == 1
        assert conn.execute(
            "select count(*) from caseproof._m2_brief_assertions where case_id=%s"
            " and version_id=%s", (str(case), str(brief_v1))).fetchone()[0] == 1
        assert conn.execute(
            "select count(*) from caseproof.audit_events where case_id=%s"
            " and action='m2_brief_graph_publish'", (str(case),)).fetchone()[0] == 1

        # Identical request replays; same request id with different content conflicts.
        assert publish(user_a, request=request) == {"ok": True, "replay": True, "revision": 1}
        assert publish(user_a, request=request, graph="graphe altéré") == {
            "ok": False, "error": "conflict"}
        # Stale expected revision conflicts.
        assert publish(user_a, expected=0) == {"ok": False, "error": "conflict", "revision": 1}
        # Reusing the head version id is invalid.
        assert publish(user_a, expected=1, version=brief_v1) == {"ok": False, "error": "invalid"}
        # Reusing the preserved source version is invalid.
        assert publish(user_a, expected=1, version=brief_v2) == {"ok": False, "error": "invalid"}

        # Second authorized user operates the independent opponent brief head.
        assert publish(user_e, role="opponent_brief") == {"ok": True, "replay": False,
                                                          "revision": 1}

        # Brief-head read proposal: masked authorization, recomputed identity,
        # revision 0 before first publication, head after publication.
        head_proposal = (
            Path(__file__).resolve().parents[1] / "db" / "proposals"
            / "SIGNED_brief_head_read.sql"
        ).read_text(encoding="utf-8")
        conn.execute(head_proposal)

        def head(sub, role="own_draft", jwt_role="authenticated"):
            as_user(sub, jwt_role)
            return conn.execute(
                "select public.caseproof_signed_brief_head(%s, %s)",
                (str(case), role)).fetchone()[0]

        other_case_head = head(user_e, role="opponent_brief")
        assert other_case_head["ok"] is True and other_case_head["revision"] == 1
        assert other_case_head["brief_id"] == working_brief("opponent_brief")
        own_head = head(user_a)
        assert own_head == {"ok": True, "brief_id": working_brief("own_draft"),
                            "revision": 1, "version_id": str(brief_v1)}
        empty_case = uuid4()
        conn.execute(
            "insert into caseproof.cases(id, org_id, created_by_user, effective_policy_version)"
            " values(%s, %s, %s, 'v1')", (empty_case, org, user_a))
        conn.execute(
            "insert into caseproof._m1_matter_grants(org_id, case_id, user_id, role, permissions)"
            " values(%s, %s, %s, 'reviewer', "
            "array['case:read','evidence:read','draft:check']::text[])",
            (org, empty_case, user_a))
        as_user(user_a)
        empty_head = conn.execute(
            "select public.caseproof_signed_brief_head(%s, 'own_draft')",
            (str(empty_case),)).fetchone()[0]
        assert empty_head == {"ok": True, "brief_id": empty_head["brief_id"],
                              "revision": 0, "version_id": None}
        for sub, role in ((user_b, "authenticated"), (user_a, "anon")):
            as_user(sub, role)
            with pytest.raises(errors.InsufficientPrivilege):
                conn.execute("select public.caseproof_signed_brief_head(%s, 'own_draft')",
                             (str(case),))
            conn.rollback()
