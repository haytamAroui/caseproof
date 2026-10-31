"""Real disposable PostgreSQL checkpoint restart proof; never production Auth."""
from __future__ import annotations

import json
import subprocess
import sys
from uuid import UUID

from application.extraction.contracts import ExtractionError, Scope, digest
from application.runtime.pages import PageCoordinator, PageInput, PagePlan
from apps.api.disposable_extraction_journal import DisposablePostgresJournal
from scripts.verify_vault_integration import connect, seed


def run(actor, org, case, *, replay=False):
    journal = DisposablePostgresJournal(connect, actor_id=actor)
    coordinator = PageCoordinator(journal, authorize=lambda: None, cancelled=lambda: False)
    plan = PagePlan(tuple(PageInput('synthetic-original', 'a' * 64, p) for p in range(1, 201)), 'checkpoint-proof-v1')
    def process(page):
        if replay:
            raise AssertionError('restart recomputed completed page')
        return {'artifact_sha256': 'b' * 64, 'uncertain': True}
    return coordinator.run(Scope(org, case), 'page-durable-restart', plan, process)


def main():
    if len(sys.argv) == 5 and sys.argv[1] == '--replay':
        result = run(*(UUID(v) for v in sys.argv[2:]), replay=True)
        print(digest(result))
        return
    fixture = seed()
    result = run(fixture.actor, fixture.scope.org_id, fixture.scope.case_id)
    child = subprocess.run([sys.executable, '-m', 'scripts.verify_page_checkpoints', '--replay',
                            str(fixture.actor), str(fixture.scope.org_id), str(fixture.scope.case_id)],
                           capture_output=True, text=True, timeout=60, check=True)
    assert child.stdout.strip() == digest(result)
    other = seed()
    try:
        run(other.actor, fixture.scope.org_id, fixture.scope.case_id, replay=True)
    except ExtractionError:
        pass
    else:
        raise AssertionError('foreign actor accessed checkpoint')
    with connect() as conn:
        conn.execute('update caseproof.organization_members set active=false where org_id=%s and user_id=%s',
                     (fixture.scope.org_id, fixture.actor))
    try:
        run(fixture.actor, fixture.scope.org_id, fixture.scope.case_id, replay=True)
    except ExtractionError:
        pass
    else:
        raise AssertionError('revoked actor accessed checkpoint')
    print(json.dumps({'pages': 200, 'separate_process_replay': True,
                      'foreign_actor_denied': True, 'revoked_actor_denied': True, 'signed_live': False}))


if __name__ == '__main__':
    main()
