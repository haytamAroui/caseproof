from uuid import uuid4

import pytest

from application.extraction.contracts import ExtractionError, Scope
from application.extraction.journal import MemoryJournal
from application.runtime.pages import PageCoordinator, PageInput, PagePlan, PageRetry


def setup(pages=3, **options):
    journal = MemoryJournal()
    scope = Scope(uuid4(), uuid4())
    plan = PagePlan(tuple(PageInput('version', 'a' * 64, p) for p in range(1, pages + 1)), 'synthetic-v1', **options)
    coordinator = PageCoordinator(journal, authorize=lambda: None, cancelled=lambda: False)
    return scope, plan, coordinator


def result(page):
    return {'artifact_sha256': 'b' * 64, 'uncertain': True}


def test_restart_reuses_completed_pages_and_retries_only_known_local_failures():
    scope, plan, c = setup()
    calls = []
    def process(page):
        calls.append(page.pdf_page)
        if page.pdf_page == 2 and calls.count(2) == 1:
            raise PageRetry('private source text must never persist')
        return result(page)
    first = c.run(scope, 'run', plan, process)
    restarted = PageCoordinator(c.journal, authorize=lambda: None, cancelled=lambda: False)
    second = restarted.run(scope, 'run', plan, lambda p: pytest.fail('completed page reprocessed'))
    assert first == second
    assert sorted(calls) == [1, 2, 2, 3]
    assert first['completed'] == 3 and first['pages'][1]['attempts'] == 2
    assert first['semantic_support'] == 'not_assessed'


def test_retry_exhaustion_remains_explicit_partial_coverage():
    scope, plan, c = setup(1, attempts=2)
    def fail(page):
        raise PageRetry('sensitive exception')
    output = c.run(scope, 'run', plan, fail)
    assert output['failed'] == 1 and not output['coverage_complete']
    assert output['pages'][0]['reason'] == 'attempts_exhausted'
    assert 'sensitive' not in str(output)


def test_changed_manifest_never_reuses_old_results():
    scope, plan, c = setup(1)
    c.run(scope, 'run', plan, result)
    from dataclasses import replace
    with pytest.raises(ExtractionError, match='input changed'):
        c.run(scope, 'run', replace(plan, engine_version='new-engine'), result)


@pytest.mark.parametrize('reason', ['cancel', 'revoke', 'deadline'])
def test_mid_page_cancellation_revocation_deadline_never_checkpoints_success(reason):
    scope, plan, c = setup(1)
    state = {'done': False}
    c.cancelled = lambda: reason == 'cancel' and state['done']
    def authorize():
        if reason == 'revoke' and state['done']:
            raise ExtractionError('access_revoked')
    c.authorize = authorize
    c.clock = lambda: 10000 if reason == 'deadline' and state['done'] else 0
    def process(page):
        state['done'] = True
        return result(page)
    with pytest.raises(ExtractionError):
        c.run(scope, 'run', plan, process)
    state['done'] = False
    retried = []
    c.run(scope, 'run', plan, lambda p: (retried.append(p), result(p))[1])
    assert len(retried) == 1


def test_concurrency_is_bounded_and_bad_worker_payload_is_rejected():
    scope, plan, c = setup(1)
    with pytest.raises(ExtractionError, match='artifact reference'):
        c.run(scope, 'run', plan, lambda p: {'text': 'private', 'uncertain': False})
    with pytest.raises(ExtractionError):
        PagePlan(plan.pages, 'v1', concurrency=100)


def test_deadline_survives_restart():
    from dataclasses import replace
    from datetime import UTC, datetime, timedelta
    scope, plan, c = setup(1)
    c.run(scope, 'run', plan, result)
    key = (scope.namespace, 'run', 'page-plan')
    c.journal._rows[key] = replace(c.journal._rows[key],
        created_at=(datetime.now(UTC) - timedelta(hours=1)).isoformat())
    with pytest.raises(ExtractionError, match='page_job_deadline'):
        c.run(scope, 'run', plan, lambda p: pytest.fail('expired run processed'))
