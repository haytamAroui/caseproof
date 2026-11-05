"""64-page bounded local recovery; signed SQL leases have separate CI coverage."""

from __future__ import annotations

from uuid import uuid4

import pytest

from application.capacity_envelope import MAX_PDF_PAGES
from application.extraction.contracts import ExtractionError, Scope
from application.extraction.journal import MemoryJournal
from application.runtime.pages import PageCoordinator, PageInput, PagePlan


def test_bounded_64_page_interruption_resume_and_no_duplicate_checkpoints():
    pages = tuple(PageInput("synthetic-v1", "a" * 64, i) for i in range(1, MAX_PDF_PAGES + 1))
    plan = PagePlan(pages, "synthetic-capacity-v1", concurrency=1)
    scope = Scope(uuid4(), uuid4())
    journal = MemoryJournal()
    cancelled = {"value": False}
    calls: list[int] = []

    def work(page):
        calls.append(page.pdf_page)
        if page.pdf_page == 12:
            cancelled["value"] = True
        return {"artifact_sha256": "b" * 64, "uncertain": True}

    first = PageCoordinator(journal, authorize=lambda: None, cancelled=lambda: cancelled["value"])
    with pytest.raises(ExtractionError, match="page_job_cancelled"):
        first.run(scope, "capacity-recovery", plan, work)
    assert 12 in calls
    assert len(calls) < MAX_PDF_PAGES
    cancelled["value"] = False
    resumed = PageCoordinator(journal, authorize=lambda: None, cancelled=lambda: False)
    result = resumed.run(
        scope,
        "capacity-recovery",
        plan,
        lambda p: (calls.append(p.pdf_page), {"artifact_sha256": "b" * 64, "uncertain": True})[1],
    )
    assert result["completed"] == MAX_PDF_PAGES
    assert result["failed"] == 0 and result["coverage_complete"] is True
    assert all(calls.count(p) == (2 if p == 12 else 1) for p in range(1, MAX_PDF_PAGES + 1))
    assert (
        resumed.run(
            scope,
            "capacity-recovery",
            plan,
            lambda p: pytest.fail("replayed completed worker page"),
        )
        == result
    )


def test_no_unbounded_parallel_plan_disguised_as_supported_envelope():
    page = PageInput("synthetic-v1", "a" * 64, 1)
    with pytest.raises(ExtractionError):
        PagePlan((page,) * 2, "duplicate")
    with pytest.raises(ExtractionError):
        PagePlan((page,), "synthetic", concurrency=5)



def test_full_current_page_plan_bounded_four_worker_concurrency_and_replay():
    """A current-boundary local processor never exceeds the configured workers."""
    from threading import Lock
    from time import sleep

    pages = tuple(
        PageInput("synthetic-v2", "c" * 64, i)
        for i in range(1, MAX_PDF_PAGES + 1)
    )
    plan = PagePlan(pages, "synthetic-capacity-v2", concurrency=4)
    scope = Scope(uuid4(), uuid4())
    journal = MemoryJournal()
    counts = {"in_flight": 0, "max_in_flight": 0, "processed": 0}
    lock = Lock()

    def work(page):
        with lock:
            counts["in_flight"] += 1
            counts["processed"] += 1
            counts["max_in_flight"] = max(
                counts["max_in_flight"], counts["in_flight"]
            )
        sleep(0.002)
        with lock:
            counts["in_flight"] -= 1
        return {"artifact_sha256": "d" * 64, "uncertain": True}

    coordinator = PageCoordinator(
        journal, authorize=lambda: None, cancelled=lambda: False
    )
    result = coordinator.run(scope, "capacity-concurrency", plan, work)
    assert result["completed"] == MAX_PDF_PAGES
    assert result["failed"] == 0
    assert counts["processed"] == MAX_PDF_PAGES
    assert 1 < counts["max_in_flight"] <= 4
    second = PageCoordinator(
        journal, authorize=lambda: None, cancelled=lambda: False
    )
    assert second.run(
        scope, "capacity-concurrency", plan,
        lambda page: pytest.fail("duplicate processor work after restart"),
    ) == result
