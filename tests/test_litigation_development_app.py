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
