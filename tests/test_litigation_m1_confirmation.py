"""M1 atomic-confirmation contract: explicitly fixture-only, no real Auth/DB proof."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
from uuid import uuid4

import pytest

from application.litigation.exhibit_confirmation import (
    ExhibitCommit,
    ExhibitConfirmationError,
    ExhibitConfirmationUseCase,
    ExhibitPrincipal,
    KnownSourceVersion,
)
from domains.disputes.exhibits import ExhibitEntry, ExhibitPage
from infrastructure.persistence.m1_exhibit_memory import FixtureExhibitStore


def rig():
    org, case, actor = uuid4(), uuid4(), uuid4()
    principal = ExhibitPrincipal(actor, org, case, True)
    store = FixtureExhibitStore()
    store.allowed_reviewers.add((org, case, actor))
    store.sources[(org, case)] = (KnownSourceVersion("s1", "v1", sha256(b"original").hexdigest()),)
    entry = ExhibitEntry(
        "id-a", "Stuk 1", (ExhibitPage("s1", "v1", 1, 4, 9),),
        ("Pièce 1",), confirmed=True,
    )
    return store, ExhibitConfirmationUseCase(store), principal, entry


def test_confirmed_exhibit_has_stable_hash_and_audit_with_safe_replay():
    _, use, principal, entry = rig()
    command = ExhibitCommit(uuid4(), 0, (entry,))
    result = use.confirm(principal, command)
    assert result.register.revision == 1
    assert result.register.resolve("Pièce 1", pdf_page=1).page.printed_page == 4
    assert use.confirm(principal, command) == result
    assert use.current(principal) == result
    assert result.audit_id.int != 0


def test_source_version_not_client_defined_and_suspected_replacement_denied():
    store, use, principal, entry = rig()
    changed = replace(entry, pages=(ExhibitPage("s1", "v2", 1),))
    with pytest.raises(ExhibitConfirmationError, match="outside authorized"):
        use.confirm(principal, ExhibitCommit(uuid4(), 0, (changed,)))
    assert use.current(principal) is None
    store.sources[(principal.org_id, principal.case_id)] = ()
    with pytest.raises(ExhibitConfirmationError, match="no authorized"):
        use.confirm(principal, ExhibitCommit(uuid4(), 0, (entry,)))


def test_noninteractive_or_revoked_reviewer_cannot_confirm():
    store, use, principal, entry = rig()
    with pytest.raises(ExhibitConfirmationError, match="explicit interactive"):
        use.confirm(replace(principal, interactive_confirmation=False), ExhibitCommit(uuid4(), 0, (entry,)))
    store.allowed_reviewers.clear()
    with pytest.raises(ExhibitConfirmationError, match="revoked"):
        use.confirm(principal, ExhibitCommit(uuid4(), 0, (entry,)))


def test_second_writer_stale_revision_and_changed_payload_replay_denied():
    _, use, principal, entry = rig()
    old = ExhibitCommit(uuid4(), 0, (entry,))
    use.confirm(principal, old)
    with pytest.raises(ExhibitConfirmationError, match="stale"):
        use.confirm(principal, ExhibitCommit(uuid4(), 0, (entry,)))
    with pytest.raises(ExhibitConfirmationError, match="different payload"):
        use.confirm(principal, ExhibitCommit(old.request_id, 0, (replace(entry, display_label="Stuk 2"),)))


def test_concurrent_only_one_initial_revision_commits():
    _, use, principal, entry = rig()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(use.confirm, principal, ExhibitCommit(uuid4(), 0, (entry,)))
            for _ in range(2)
        ]
    outcomes = [f.exception() for f in futures]
    assert sum(x is None for x in outcomes) == 1
    assert sum(isinstance(x, ExhibitConfirmationError) for x in outcomes) == 1


def test_unconfirmed_mapping_never_becomes_confirmed_by_persisting():
    _, use, principal, entry = rig()
    with pytest.raises(ExhibitConfirmationError, match="explicitly confirmed"):
        use.confirm(principal, ExhibitCommit(uuid4(), 0, (replace(entry, confirmed=False),)))
