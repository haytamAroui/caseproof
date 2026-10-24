"""Review recommendations and offline draft integrity, never approval/authenticity proof."""

from __future__ import annotations

import io
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier
from uuid import UUID, uuid4
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import pytest
from fastapi.testclient import TestClient

from application.dossiers.pack import build_pack, verify_pack
from application.extraction.contracts import ExtractionError, Scope, canonical, digest
from application.review.contracts import ReviewCommand, ReviewConflict, ReviewKind, ReviewSnapshot
from application.review.memory import MemoryReviewRepository
from apps.api.synthetic_review_app import create_demo_app
from scripts.review_demo_fixture import ACTOR, demo_material


@pytest.fixture(scope="module")
def material():
    return demo_material()


def command(
    snapshot,
    *,
    revision=0,
    kind=ReviewKind.RETAIN,
    note="The source needs commercial confirmation",
    correction=None,
):
    return ReviewCommand(
        uuid4(),
        snapshot.snapshot_hash,
        revision,
        snapshot.data["extraction"]["atoms"][0]["candidate_id"],
        kind,
        note,
        correction,
    )


def repository(material):
    snapshot, _ = material
    repo = MemoryReviewRepository()
    repo.publish(snapshot, ACTOR)
    return repo


@pytest.mark.parametrize("kind", list(ReviewKind))
def test_each_review_action_is_separate_unapproved_revision(material, kind):
    snapshot, docs = material
    repo = repository(material)
    before = snapshot.payload_json
    cmd = command(
        snapshot,
        kind=kind,
        correction="Proposed revised interpretation"
        if kind in {ReviewKind.CORRECT, ReviewKind.QUALIFY}
        else None,
    )
    receipt = repo.record(snapshot.scope, ACTOR, cmd)
    state = repo.state(snapshot.scope, ACTOR)
    assert receipt["revision"] == 1 and receipt["approved"] is False
    assert snapshot.payload_json == before and state["snapshot"]["extraction"]["coverage_complete"] is False
    raw, manifest = build_pack(snapshot, docs, state)
    verified = verify_pack(raw, expected_manifest=manifest)
    assert (
        verified["review_events"] == 1
        and not verified["authenticity_established"]
        and not verified["approved"]
    )


def test_idempotency_changed_payload_actor_and_stale_revision(material):
    snapshot, _ = material
    repo = repository(material)
    cmd = command(snapshot)
    first = repo.record(snapshot.scope, ACTOR, cmd)
    second = repo.record(snapshot.scope, ACTOR, cmd)
    assert second == {**first, "replayed": True}
    for changed in (replace(cmd, note="Different rationale"),):
        with pytest.raises(ReviewConflict):
            repo.record(snapshot.scope, ACTOR, changed)
    with pytest.raises(ReviewConflict):
        repo.record(snapshot.scope, UUID(int=999), cmd)
    with pytest.raises(ReviewConflict, match="revision"):
        repo.record(snapshot.scope, ACTOR, command(snapshot))
    assert len(repo.state(snapshot.scope, ACTOR)["events"]) == 1


def test_wrong_case_snapshot_or_item_fail_closed(material):
    snapshot, _ = material
    repo = repository(material)
    for changed in (
        replace(command(snapshot), snapshot_hash="f" * 64),
        replace(command(snapshot), item_id="unknown"),
    ):
        with pytest.raises(ExtractionError):
            repo.record(snapshot.scope, ACTOR, changed)
    with pytest.raises(ExtractionError):
        repo.state(Scope(UUID(int=999), snapshot.scope.case_id), ACTOR)


def test_concurrent_review_revisions_only_one_winner(material):
    snapshot, _ = material
    repo = repository(material)
    barrier = Barrier(2)

    def race(_):
        barrier.wait()
        try:
            repo.record(snapshot.scope, ACTOR, command(snapshot))
            return "saved"
        except ReviewConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(race, range(2))) == ["conflict", "saved"]


def test_corrections_keep_original_and_previous_revisions(material):
    snapshot, _ = material
    repo = repository(material)
    repo.record(
        snapshot.scope, ACTOR, command(snapshot, kind=ReviewKind.CORRECT, correction="First proposal")
    )
    repo.record(
        snapshot.scope,
        ACTOR,
        command(snapshot, revision=1, kind=ReviewKind.QUALIFY, correction="Second qualification"),
    )
    state = repo.state(snapshot.scope, ACTOR)
    assert [e["command"]["correction"] for e in state["events"]] == ["First proposal", "Second qualification"]
    assert state["snapshot"] == snapshot.data


@pytest.mark.parametrize(
    "kwargs",
    [
        {"note": " "},
        {"note": "x" * 4001},
        {"expected_revision": True},
        {"correction": "unexpected"},
        {"kind": "approve"},
        {"snapshot_hash": "bad"},
    ],
)
def test_strict_review_input(material, kwargs):
    snapshot, _ = material
    base = dict(
        request_id=uuid4(),
        snapshot_hash=snapshot.snapshot_hash,
        expected_revision=0,
        item_id="case",
        kind=ReviewKind.RETAIN,
        note="Rationale",
    )
    with pytest.raises(ExtractionError):
        ReviewCommand(**{**base, **kwargs})


def test_missing_snapshot_integrity_is_rejected(material):
    snapshot, _ = material
    with pytest.raises(ExtractionError):
        ReviewSnapshot(snapshot.scope, "0" * 64, snapshot.payload_json)


def rewrite(raw, change, compression=ZIP_STORED):
    with ZipFile(io.BytesIO(raw)) as z:
        files = {n: z.read(n) for n in z.namelist()}
    change(files)
    output = io.BytesIO()
    with ZipFile(output, "w", compression=compression) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return output.getvalue()


def test_pack_is_reproducible_and_preserves_all_unresolved_evidence(material):
    snapshot, docs = material
    repo = repository(material)
    state = repo.state(snapshot.scope, ACTOR)
    first, sha = build_pack(snapshot, docs, state)
    assert build_pack(snapshot, docs, state) == (first, sha)
    result = verify_pack(first)
    assert result["external_checkpoint_matched"] is False and result["resolved_citations"] == 4
    with ZipFile(io.BytesIO(first)) as z:
        case = json.loads(z.read("case.json"))
        assert case["extraction"]["conflicts"] and any(
            s["state"] == "missing" for s in case["extraction"]["slots"]
        )
        for i, doc in enumerate(docs):
            assert z.read(f"sources/{i:03d}/original.bin") == doc.evidence.source.content


@pytest.mark.parametrize(
    "path",
    [
        "case.json",
        "reviews.json",
        "report.html",
        "sources/000/original.bin",
        "sources/000/text.txt",
        "sources/000/normalization.json",
    ],
)
def test_tampering_any_part_denies_pack(material, path):
    snapshot, docs = material
    raw, _ = build_pack(snapshot, docs, repository(material).state(snapshot.scope, ACTOR))
    broken = rewrite(raw, lambda files: files.__setitem__(path, files[path] + b"modified"))
    with pytest.raises(ExtractionError):
        verify_pack(broken)


@pytest.mark.parametrize(
    "path",
    ["../escape", "/absolute", "sources/../escape", "verify.py", "sources\\escape", "report.html/evil"],
)
def test_archive_traversal_or_executable_entries_are_rejected(material, path):
    snapshot, docs = material
    raw, _ = build_pack(snapshot, docs, repository(material).state(snapshot.scope, ACTOR))
    with pytest.raises(ExtractionError):
        verify_pack(rewrite(raw, lambda files: files.__setitem__(path, b"untrusted")))


def test_compressed_duplicate_and_wrong_external_manifest_are_rejected(material):
    snapshot, docs = material
    raw, sha = build_pack(snapshot, docs, repository(material).state(snapshot.scope, ACTOR))
    with pytest.raises(ExtractionError):
        verify_pack(rewrite(raw, lambda _: None, ZIP_DEFLATED))
    with pytest.raises(ExtractionError, match="external"):
        verify_pack(raw, expected_manifest="f" * 64)
    output = io.BytesIO(raw)
    with ZipFile(output, "a") as z:
        z.writestr("case.json", b"duplicate")
    with pytest.raises(ExtractionError):
        verify_pack(output.getvalue())


def test_review_and_report_injection_is_escaped(material):
    snapshot, docs = material
    repo = repository(material)
    repo.record(
        snapshot.scope,
        ACTOR,
        command(
            snapshot,
            note='<script>alert("x")</script>',
            kind=ReviewKind.CORRECT,
            correction='<img src=x onerror="alert(1)">',
        ),
    )
    raw, _ = build_pack(snapshot, docs, repo.state(snapshot.scope, ACTOR))
    with ZipFile(io.BytesIO(raw)) as z:
        report = z.read("report.html").decode()
        assert "<script>" not in report and "<img src=" not in report and "&lt;script&gt;" in report


def test_export_detects_changed_source_inventory_or_authority(material):
    snapshot, docs = material
    state = repository(material).state(snapshot.scope, ACTOR)
    with pytest.raises(ExtractionError):
        build_pack(snapshot, docs[:-1], state)
    with pytest.raises(ExtractionError):
        build_pack(snapshot, docs, {**state, "approved": True})


@pytest.fixture(scope="module")
def client():
    with TestClient(create_demo_app(), raise_server_exceptions=False) as c:
        yield c


def test_ui_assets_and_synthetic_security_headers(client):
    for path in ("/demo", "/demo/assets/workbench.css", "/demo/assets/workbench.js"):
        response = client.get(path)
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert client.get("/v2/reviews").status_code == 404
    assert client.get("/demo/assets/unknown").status_code == 404
    assert client.get("/demo/api/state", headers={"Host": "attacker.invalid"}).status_code == 403


def test_cross_origin_missing_session_and_authority_fields_denied(client):
    state = client.get("/demo/api/state").json()
    body = command(
        ReviewSnapshot(
            Scope(*map(UUID, state["snapshot"]["scope"].split(":"))),
            state["snapshot_hash"],
            canonical(state["snapshot"]),
        )
    ).payload()
    assert client.post("/demo/api/reviews", json=body).status_code == 403
    headers = {"Origin": "http://testserver", "X-Review-Session": state["session"]}
    assert (
        client.post("/demo/api/reviews", json={**body, "actor_id": str(ACTOR)}, headers=headers).status_code
        == 422
    )
    assert (
        client.post(
            "/demo/api/reviews", json=body, headers={**headers, "Origin": "https://attacker.invalid"}
        ).status_code
        == 403
    )
    assert (
        client.post("/demo/api/reviews", json={**body, "kind": "approve"}, headers=headers).status_code == 422
    )


def test_http_save_replay_conflict_and_pack_download(client):
    state = client.get("/demo/api/state").json()
    snap = ReviewSnapshot(
        Scope(*map(UUID, state["snapshot"]["scope"].split(":"))),
        state["snapshot_hash"],
        canonical(state["snapshot"]),
    )
    body = command(snap, revision=state["revision"]).payload()
    headers = {"Origin": "http://testserver", "X-Review-Session": state["session"]}
    first = client.post("/demo/api/reviews", json=body, headers=headers)
    assert first.status_code == 200 and not first.json()["approved"]
    assert client.post("/demo/api/reviews", json=body, headers=headers).json()["replayed"]
    assert (
        client.post(
            "/demo/api/reviews", json={**body, "request_id": str(uuid4())}, headers=headers
        ).status_code
        == 409
    )
    downloaded = client.get("/demo/api/export")
    assert downloaded.status_code == 200
    assert (
        verify_pack(downloaded.content, expected_manifest=downloaded.headers["x-pack-manifest-sha256"])[
            "review_events"
        ]
        >= 1
    )
    original = client.get("/demo/api/source/invoice")
    assert original.status_code == 200 and "attachment" in original.headers["content-disposition"]


def test_snapshot_cannot_claim_approval_even_with_recomputed_hash(material):
    snapshot, _ = material
    data = snapshot.data
    data["approved"] = True
    with pytest.raises(ExtractionError, match="approval"):
        ReviewSnapshot(snapshot.scope, digest(data), canonical(data))


def test_same_snapshot_newer_review_does_not_change_case_evidence(material):
    snapshot, docs = material
    repo = repository(material)
    before = snapshot.snapshot_hash
    repo.record(snapshot.scope, ACTOR, command(snapshot))
    repo.publish(snapshot, ACTOR)
    assert repo.state(snapshot.scope, ACTOR)["snapshot_hash"] == before
    assert repo.state(snapshot.scope, ACTOR)["revision"] == 1
    _, sha = build_pack(snapshot, docs, repo.state(snapshot.scope, ACTOR))
    assert len(sha) == 64


def test_http_session_input_limits_and_invalid_origin(client):
    state = client.get("/demo/api/state").json()
    headers = {"Origin": "http://testserver", "X-Review-Session": state["session"]}
    assert (
        client.post(
            "/demo/api/reviews", content="x" * 20001, headers={**headers, "Content-Type": "application/json"}
        ).status_code
        == 413
    )
    assert (
        client.post(
            "/demo/api/reviews", json={}, headers={**headers, "Origin": "http://[invalid"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/demo/api/reviews", json={}, headers={**headers, "X-Review-Session": "wrong"}
        ).status_code
        == 403
    )
    assert client.get("/demo/api/source/unknown").status_code == 404


def test_rehashed_wrong_citation_still_fails_internal_verification(material):
    import hashlib

    snapshot, docs = material
    raw, _ = build_pack(snapshot, docs, repository(material).state(snapshot.scope, ACTOR))

    def forge(files):
        case = json.loads(files["case.json"])
        case["extraction"]["atoms"][0]["quote"] = "Not in preserved source"
        new_snapshot = digest(case)
        state = json.loads(files["reviews.json"])
        state["snapshot"] = case
        state["snapshot_hash"] = new_snapshot
        files["case.json"] = canonical(case).encode()
        files["reviews.json"] = canonical(state).encode()
        manifest = json.loads(files["manifest.json"])
        manifest["snapshot_hash"] = new_snapshot
        for name, content in files.items():
            if name != "manifest.json":
                manifest["files"][name] = {
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "bytes": len(content),
                }
        files["manifest.json"] = canonical(manifest).encode()

    with pytest.raises(ExtractionError, match="citation"):
        verify_pack(rewrite(raw, forge))
