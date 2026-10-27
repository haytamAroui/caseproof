"""Authorization, snapshot and source-anchored search regressions."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent))
from test_litigation_m2_headless_api import ACTOR, CASE, DRAFT, ORG, rig  # noqa: E402

from application.litigation.matter_policy import (  # noqa: E402
    CurrentMatterGrant,
    CurrentOrganizationGrant,
    MatterPermission,
    OrganizationPermission,
)
from apps.api.access_control import AccessRejected  # noqa: E402
from apps.api.litigation_check_service import PrivateMatterAccess  # noqa: E402
from apps.api.litigation_evidence_search import AuthorizedEvidenceSearch  # noqa: E402
from apps.api.litigation_search_app import create_litigation_search_app  # noqa: E402


def search_rig():
    checker, _, store = rig()
    def access(subject_id, case_id):
        if subject_id != ACTOR or case_id != CASE:
            return None
        member = CurrentOrganizationGrant(ACTOR, ORG, True, frozenset({
            OrganizationPermission.CASE_READ, OrganizationPermission.EVIDENCE_READ,
            OrganizationPermission.FINDING_WRITE,
        }), 1)
        grant = CurrentMatterGrant(ACTOR, ORG, CASE, True, frozenset({
            MatterPermission.READ, MatterPermission.EVIDENCE_READ, MatterPermission.DRAFT_CHECK,
        }), 1)
        return PrivateMatterAccess(CASE, ORG, member, grant, 1)
    store.current_access = access
    return AuthorizedEvidenceSearch(checker), store


def test_exact_search_returns_source_offsets_and_no_false_coverage():
    search, _ = search_rig()
    result = search.search(bearer="signed-dev-fixture", case_id=CASE,
                           brief_version_id=DRAFT, query="betaling")
    assert result.coverage == "complete" and len(result.hits) == 1
    hit = result.hits[0]
    assert hit.source_id == "s1" and hit.source_version_id == "v1"
    assert hit.text == "De betaling is vastgesteld."
    assert (hit.start, hit.end, hit.page) == (0, len(hit.text), 1)
    assert hit.citation.label == "Stuk 1" and hit.citation.pdf_page == 1


def test_unavailable_snapshot_and_revoked_permission_never_return_text():
    search, store = search_rig()
    store.snapshot_current = False
    with pytest.raises(AccessRejected):
        search.search(bearer="signed-dev-fixture", case_id=CASE, brief_version_id=DRAFT, query="betaling")
    with pytest.raises(AccessRejected):
        search.search(bearer="bad", case_id=CASE, brief_version_id=DRAFT, query="betaling")


def test_http_requires_bearer_and_disables_extra_fields():
    search, _ = search_rig()
    client = TestClient(create_litigation_search_app(search))
    path = f"/v2/matters/{CASE}/briefs/{DRAFT}/evidence/search"
    assert client.post(path, json={"query": "betaling"}).status_code == 401
    headers = {"Authorization": "Bearer signed-dev-fixture"}
    invalid = client.post(path, json={"query": "confidential search", "actor_id": ACTOR}, headers=headers)
    assert invalid.status_code == 422 and "confidential search" not in invalid.text
    response = client.post(path, json={"query": "betaling"}, headers=headers)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert response.json()["hits"][0]["source_version_id"] == "v1"


def test_evidence_permission_is_independent_of_draft_check():
    search, store = search_rig()
    original = store.current_access
    def no_evidence(subject_id, case_id):
        access = original(subject_id, case_id)
        return PrivateMatterAccess(
            access.case_id, access.org_id, access.member,
            CurrentMatterGrant(ACTOR, ORG, CASE, True,
                               frozenset({MatterPermission.READ, MatterPermission.DRAFT_CHECK}), 1),
            1,
        )
    store.current_access = no_evidence
    with pytest.raises(AccessRejected) as exc:
        search.search(bearer="signed-dev-fixture", case_id=CASE, brief_version_id=DRAFT, query="betaling")
    assert exc.value.http_status == 403 and store.load_calls == 0


def test_incomplete_source_universe_is_visible():
    from dataclasses import replace

    from application.litigation.unified_review import SourceScope
    search, store = search_rig()
    original = store.load_bundle
    def partial(**kwargs):
        bundle = original(**kwargs)
        return replace(bundle, source_scope=SourceScope((("s1", "v1"), ("s2", "v2"))))
    store.load_bundle = partial
    result = search.search(bearer="signed-dev-fixture", case_id=CASE, brief_version_id=DRAFT, query="betaling")
    assert result.coverage == "partial" and result.omitted_sources == 1


def test_no_matches_is_a_valid_result():
    search, _ = search_rig()
    result = search.search(bearer="signed-dev-fixture", case_id=CASE, brief_version_id=DRAFT, query="unmatched")
    assert result.coverage == "complete" and result.hits == ()


def test_ambiguous_or_unmapped_citations_are_not_suggested():
    from apps.api.litigation_evidence_search import citation_candidate
    from domains.disputes.exhibits import ExhibitEntry, ExhibitPage, ExhibitRegister
    page = ExhibitPage("s1", "v1", 1)
    register = ExhibitRegister(1, (
        ExhibitEntry("e1", "Stuk 1", (page,), confirmed=True),
        ExhibitEntry("e2", "Stuk 2", (page,), confirmed=True),
    ))
    assert citation_candidate(register, "s1", "v1", 1) is None
    assert citation_candidate(register, "s1", "v1", None) is None
    assert citation_candidate(register, "s1", "v2", 1) is None
