"""Deterministic 200-page worker recovery and adversarial checkpoint tests.

These are unit-level simulations, not a claim of live OCR, SQL or cloud acceptance.
"""
from __future__ import annotations

import hashlib
from threading import Lock
from types import SimpleNamespace

import pytest

from application.extraction.contracts import ExtractionError
from apps.api.access_control import AccessRejected
from apps.api.dossier_journey import canonical
from apps.api.signed_page_jobs import SignedPageJobs
from apps.worker import signed_page_worker as module


class InMemoryJobs(SignedPageJobs):
    def __init__(self, manifest):
        super().__init__(SimpleNamespace(), "dedicated-fixture-page-worker-secret-2026")
        self.manifest = manifest
        self.serialized = canonical(manifest)
        self.manifest_hash = hashlib.sha256(self.serialized.encode()).hexdigest()
        self.results = {}
        self.state = "queued"
        self.lease_counter = 0
        self.lease = None
        self.actions = []
        self.lock = Lock()

    def call(self, bearer, case, request, action, data=None):
        assert bearer == "signed-owner" and case == "matter" and request == "request"
        with self.lock:
            self.actions.append(action)
            if action == "status":
                return {
                    "state": self.state, "manifest": self.serialized,
                    "manifest_hash": self.manifest_hash, "org_id": "org",
                    "actor_id": "owner",
                    "results": [{"page_key": key} for key in self.results],
                }
            if action == "claim":
                assert self.state in ("queued", "yielded")
                self.lease_counter += 1
                self.lease = f"lease-{self.lease_counter}"
                self.state = "running"
                return {"lease_token": self.lease, "org_id": "org", "actor_id": "owner"}
            if action == "heartbeat":
                assert data["lease_token"] == self.lease
                return {"state": "running"}
            if action == "page":
                return self.results[data["page_key"]]
            if action == "put":
                assert self.state == "running" and data["lease_token"] == self.lease
                key = data["page_key"]
                if key in self.results:
                    assert self.results[key]["serialized"] == data["serialized"]
                self.results[key] = {
                    "serialized": data["serialized"], "artifact_hash": data["artifact_hash"]
                }
                return {"page_key": key}
            if action in ("yield", "finish"):
                assert data["lease_token"] == self.lease
                self.state = "succeeded" if action == "finish" else "yielded"
                return self.call_status_without_relocking()
            raise AssertionError(f"unexpected operation: {action}")

    def call_status_without_relocking(self):
        return {
            "state": self.state, "manifest": self.serialized,
            "manifest_hash": self.manifest_hash, "org_id": "org", "actor_id": "owner",
            "results": [{"page_key": key} for key in self.results],
        }


def make_worker(monkeypatch, page_count=200):
    original = b"synthetic-pdf-content"
    sha = hashlib.sha256(original).hexdigest()
    pages = [
        {
            "document_id": "doc", "version_id": "version",
            "original_sha256": sha, "pdf_page": n, "needs_ocr": False,
        }
        for n in range(1, page_count + 1)
    ]
    manifest = {
        "schema": "caseproof-page-job-v1", "case_id": "matter",
        "request_id": "request", "bundle_signature": "bundle",
        "engine_version": "synthetic-engine", "pages": pages,
    }
    jobs = InMemoryJobs(manifest)
    worker = module.SignedPageWorker(jobs, ocr=SimpleNamespace())
    worker.engine = "synthetic-engine"
    monkeypatch.setattr(worker, "inputs", lambda *_: (manifest, {"version": original}))
    parse_calls = []
    def parse_once(**kwargs):
        parse_calls.append(kwargs["version_id"])
        return ("X", {
            "blocks": [
                {"page_index": n - 1, "start": 0, "end": 1}
                for n in range(1, page_count + 1)
            ]
        })
    monkeypatch.setattr(module, "parse_verified_original", parse_once)
    worker.parse_calls = parse_calls
    return worker, jobs, manifest


def test_200_page_checkpoint_resume_with_fresh_worker(monkeypatch):
    worker, jobs, manifest = make_worker(monkeypatch)
    first = worker.run("signed-owner", "matter", "request", max_pages=100)
    assert first["state"] == "yielded"
    assert len(first["results"]) == 100

    # New worker instance, same durable job store and independently verified receipts.
    restarted = module.SignedPageWorker(jobs, ocr=SimpleNamespace())
    restarted.engine = worker.engine
    monkeypatch.setattr(restarted, "inputs", lambda *_: (manifest, {"version": b"synthetic-pdf-content"}))
    second = restarted.run("signed-owner", "matter", "request", max_pages=100)
    assert second["state"] == "succeeded"
    assert len(second["results"]) == 200
    assert jobs.lease_counter == 2
    assert jobs.actions.count("put") == 200
    assert len(worker.parse_calls) == 2
    assert jobs.actions.count("page") >= 100

    # A completed job must not acquire another lease or rewrite pages.
    assert restarted.run("signed-owner", "matter", "request")["state"] == "succeeded"
    assert jobs.lease_counter == 2
    assert jobs.actions.count("put") == 200


@pytest.mark.parametrize("corruption", ["unknown", "duplicate", "tampered"])
def test_resume_fails_closed_on_corrupt_checkpoint(monkeypatch, corruption):
    worker, jobs, _ = make_worker(monkeypatch, page_count=2)
    worker.run("signed-owner", "matter", "request", max_pages=1)
    key = next(iter(jobs.results))
    if corruption == "unknown":
        jobs.results["unlisted:999"] = jobs.results.pop(key)
    elif corruption == "duplicate":
        original_call = jobs.call
        def duplicate_status(*args, **kwargs):
            result = original_call(*args, **kwargs)
            if args[3] == "status":
                result["results"].append(result["results"][0])
            return result
        jobs.call = duplicate_status
    else:
        jobs.results[key]["artifact_hash"] = "0" * 64
    with pytest.raises((ExtractionError, AccessRejected)):
        worker.run("signed-owner", "matter", "request")
    assert jobs.lease_counter == 1


def test_completion_requires_exact_page_identity_not_just_count(monkeypatch):
    worker, jobs, _ = make_worker(monkeypatch, page_count=2)
    original_call = jobs.call
    def falsified_status(*args, **kwargs):
        result = original_call(*args, **kwargs)
        if args[3] == "status" and len(jobs.results) == 2:
            result["results"] = [{"page_key": "version:1"}, {"page_key": "alien:2"}]
        return result
    jobs.call = falsified_status
    with pytest.raises(ExtractionError, match="worker_invalid_checkpoint"):
        worker.run("signed-owner", "matter", "request")
    assert jobs.state == "running"


def test_finish_rechecks_all_receipts_and_rejects_late_corruption(monkeypatch):
    worker, jobs, _ = make_worker(monkeypatch, page_count=4)
    original_call = jobs.call
    def corrupt_at_final_status(*args, **kwargs):
        result = original_call(*args, **kwargs)
        if args[3] == "status" and len(jobs.results) == 4:
            key = next(iter(jobs.results))
            jobs.results[key]["artifact_hash"] = "0" * 64
        return result
    jobs.call = corrupt_at_final_status
    with pytest.raises(AccessRejected):
        worker.run("signed-owner", "matter", "request")
    assert jobs.state != "succeeded"
    assert "finish" not in jobs.actions


def test_checkpointed_page_is_not_reprocessed_after_resume(monkeypatch):
    worker, jobs, manifest = make_worker(monkeypatch, page_count=6)
    worker.run("signed-owner", "matter", "request", max_pages=2)
    checkpoint_hashes = {key: row["artifact_hash"] for key, row in jobs.results.items()}
    fresh = module.SignedPageWorker(jobs, ocr=SimpleNamespace())
    fresh.engine = worker.engine
    monkeypatch.setattr(fresh, "inputs", lambda *_: (manifest, {"version": b"synthetic-pdf-content"}))
    fresh.run("signed-owner", "matter", "request", max_pages=4)
    assert len(jobs.results) == 6
    assert all(jobs.results[key]["artifact_hash"] == value for key, value in checkpoint_hashes.items())
    assert jobs.actions.count("put") == 6
