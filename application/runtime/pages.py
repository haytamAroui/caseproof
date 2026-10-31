"""Bounded deterministic page work over the existing transactional checkpoint port.

The host supplies freshly authorized scope, a fenced journal, and a resource-limited
local parser. No credentials, document text, crops, or arbitrary entrypoints belong
in the manifest. External side-effecting provider calls need their own outcome-
unknown protocol and MUST NOT use this local retry policy.
"""
from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any

from application.extraction.contracts import (
    ExtractionError,
    Scope,
    StepJournal,
    StepState,
    canonical,
    decode,
    digest,
)


class PageRetry(ExtractionError):
    """Known transient failure of local, deterministic, side-effect-free work."""


@dataclass(frozen=True, slots=True)
class PageInput:
    version_id: str
    original_sha256: str
    pdf_page: int

    def __post_init__(self) -> None:
        import re
        if (type(self.version_id) is not str or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', self.version_id)
                or type(self.original_sha256) is not str
                or not re.fullmatch(r'[0-9a-f]{64}', self.original_sha256)
                or type(self.pdf_page) is not int or not 1 <= self.pdf_page <= 200):
            raise ExtractionError('invalid page identity')


@dataclass(frozen=True, slots=True)
class PagePlan:
    pages: tuple[PageInput, ...]
    engine_version: str
    concurrency: int = 2
    attempts: int = 3
    deadline_seconds: int = 600

    def __post_init__(self) -> None:
        if (type(self.pages) is not tuple or not 1 <= len(self.pages) <= 200
                or any(not isinstance(p, PageInput) for p in self.pages)
                or len(set(self.pages)) != len(self.pages)
                or type(self.engine_version) is not str or not 1 <= len(self.engine_version) <= 128
                or type(self.concurrency) is not int or not 1 <= self.concurrency <= 4
                or type(self.attempts) is not int or not 1 <= self.attempts <= 5
                or type(self.deadline_seconds) is not int or not 1 <= self.deadline_seconds <= 1800):
            raise ExtractionError('bounded page plan required')
        identities: dict[str, str] = {}
        for page in self.pages:
            if identities.setdefault(page.version_id, page.original_sha256) != page.original_sha256:
                raise ExtractionError('conflicting immutable source')

    @property
    def fingerprint(self) -> str:
        return digest({'schema': 'page-plan-v1', **asdict(self)})


class PageCoordinator:
    def __init__(self, journal: StepJournal, *, authorize: Callable[[], None],
                 cancelled: Callable[[], bool], clock: Callable[[], float] = monotonic):
        self.journal, self.authorize, self.cancelled, self.clock = journal, authorize, cancelled, clock

    def run(self, scope: Scope, run_id: str, plan: PagePlan,
            process: Callable[[PageInput], dict[str, Any]]) -> dict[str, Any]:
        started = self.clock()
        created_at = datetime.now(UTC)

        def guard() -> None:
            self.authorize()
            if self.cancelled():
                raise ExtractionError('page_job_cancelled')
            if (self.clock() - started >= plan.deadline_seconds
                    or (datetime.now(UTC) - created_at).total_seconds() >= plan.deadline_seconds):
                raise ExtractionError('page_job_deadline')

        guard()
        # Reserve before any execution; an existing run cannot silently change inputs.
        manifest = self.journal.reserve(scope, run_id, 'page-plan', plan.fingerprint)
        created_at = datetime.fromisoformat(manifest.created_at)
        if created_at.tzinfo is None or (datetime.now(UTC) - created_at).total_seconds() >= plan.deadline_seconds:
            raise ExtractionError('page_job_deadline')
        if manifest.state is StepState.PREPARED:
            self.journal.transition(scope, run_id, 'page-plan', StepState.PREPARED,
                                    StepState.COMPLETED, canonical({'manifest_hash': plan.fingerprint}))

        def page_work(page: PageInput) -> dict[str, Any]:
            identity = digest(asdict(page))
            for attempt in range(1, plan.attempts + 1):
                guard()
                step = f'page:{identity}:{attempt}'
                row = self.journal.reserve(scope, run_id, step, plan.fingerprint)
                if row.state is StepState.COMPLETED:
                    outcome = decode(row.payload or '')
                elif row.state is StepState.PREPARED:
                    try:
                        result = process(page)
                        # Persist references/digests only; never trust text-bearing worker output.
                        if (type(result) is not dict or set(result) != {'artifact_sha256', 'uncertain'}
                                or type(result['uncertain']) is not bool
                                or type(result['artifact_sha256']) is not str
                                or len(result['artifact_sha256']) != 64
                                or any(c not in '0123456789abcdef' for c in result['artifact_sha256'])):
                            raise ExtractionError('invalid page artifact reference')
                        outcome = {'state': 'completed', **result}
                    except PageRetry:
                        outcome = {'state': 'retry', 'reason': 'local_transient'}
                    # Lost grants, cancellation, timeout and persistence failure never acknowledge completion.
                    guard()
                    row = self.journal.transition(scope, run_id, step, StepState.PREPARED,
                                                  StepState.COMPLETED, canonical(outcome))
                else:
                    raise ExtractionError('unsupported page checkpoint state')
                if outcome['state'] == 'completed':
                    return {**asdict(page), **outcome, 'attempts': attempt}
            return {**asdict(page), 'state': 'failed', 'reason': 'attempts_exhausted', 'attempts': plan.attempts}

        with ThreadPoolExecutor(max_workers=plan.concurrency) as pool:
            results = list(pool.map(page_work, plan.pages))
        guard()
        return {'schema': 'page-processing-v1', 'manifest_hash': plan.fingerprint,
                'engine_version': plan.engine_version, 'pages': results,
                'completed': sum(r['state'] == 'completed' for r in results),
                'failed': sum(r['state'] == 'failed' for r in results),
                'coverage_complete': all(r['state'] == 'completed' for r in results),
                'semantic_support': 'not_assessed'}
