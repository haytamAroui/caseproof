"""Authorization composition tests; verifier/catalog/Vault doubles are not live Auth proof."""

from datetime import timedelta
from uuid import UUID

import pytest

from application.documents.intake import DocumentIntelligence
from application.extraction.contracts import ExtractionConfig, ExtractionError
from application.extraction.journal import MemoryJournal
from apps.api.access_control import (
    AccessRejected,
    CaseAccessService,
    CaseAction,
    InvalidBearer,
    StoredCase,
    StoredMembership,
    VerifiedSubject,
)
from apps.api.authenticated_document_intelligence import AuthenticatedDocumentIntelligence, StoredDocument
from domains.finance.extraction_rules import FinanceEvidencePolicy
from evals.document_corpus import CASES
from infrastructure.parsers.limited import LimitedDocumentParser
from scripts.extraction_fixtures import NOW, ScriptedProvider, envelope

ORG, CASE, ACTOR = str(UUID(int=1001)), str(UUID(int=1002)), str(UUID(int=1003))
ACTIONS = frozenset({CaseAction.READ_CASE, CaseAction.READ_EVIDENCE, CaseAction.PROPOSE_FINDING})


class Verifier:
    def verify_bearer(self, token):
        if token != "synthetic-valid":
            raise InvalidBearer("invalid")
        return VerifiedSubject(ACTOR, "fixture-issuer", "authenticated", NOW, NOW + timedelta(hours=1), False)


class Repository:
    actions = ACTIONS
    active = True
    revision = 1

    def lookup_case_membership(self, subject, case):
        if case != CASE:
            return None
        return StoredCase(CASE, ORG, self.revision, ACTOR), StoredMembership(
            subject, ORG, self.active, self.actions
        )


class Catalog:
    calls = 0

    def list_sources(self, authorized):
        self.calls += 1
        assert authorized.org_id == ORG and authorized.case_id == CASE
        return (StoredDocument("invoice", CASES[0].captured().source, UUID(int=1004)),)


class Vault:
    calls = 0
    raw = CASES[0].captured().source.content

    def read(self, *, scope, intent_id):
        self.calls += 1
        assert str(scope.org_id) == ORG and str(scope.case_id) == CASE
        return self.raw


def composition():
    repo, catalog, vault = Repository(), Catalog(), Vault()
    access = CaseAccessService(Verifier(), repo, "fixture-issuer", "authenticated", lambda: NOW)
    provider = ScriptedProvider(envelope([]))
    service = DocumentIntelligence(
        LimitedDocumentParser(), provider, MemoryJournal(), FinanceEvidencePolicy()
    )
    adapter = AuthenticatedDocumentIntelligence(
        access, catalog, lambda context: vault, lambda context: service
    )
    return adapter, repo, catalog, vault, provider


def run(adapter, **kwargs):
    return adapter.run(
        bearer=kwargs.get("bearer", "synthetic-valid"),
        case_id=kwargs.get("case_id", CASE),
        run_id="synthetic-auth",
        assignments=(CASES[0].assignment,),
        slots=(CASES[0].slot,),
        config=ExtractionConfig(repair_passes=0),
    )


@pytest.mark.parametrize("token", ["", "invalid"])
def test_unauthenticated_never_reads_catalog_or_vault(token):
    adapter, _, catalog, vault, provider = composition()
    with pytest.raises(AccessRejected):
        run(adapter, bearer=token)
    assert catalog.calls == vault.calls == 0 and not provider.calls


@pytest.mark.parametrize("missing", list(ACTIONS))
def test_each_permission_is_required(missing):
    adapter, repo, catalog, vault, provider = composition()
    repo.actions = ACTIONS - {missing}
    with pytest.raises(AccessRejected):
        run(adapter)
    assert catalog.calls == vault.calls == 0 and not provider.calls


def test_foreign_case_and_revoked_membership_never_expose_sources():
    adapter, repo, catalog, _, _ = composition()
    with pytest.raises(AccessRejected):
        run(adapter, case_id=str(UUID(int=2002)))
    repo.active = False
    with pytest.raises(AccessRejected):
        run(adapter)
    assert catalog.calls == 0


def test_catalog_different_bytes_fail_before_paid_call():
    adapter, _, _, vault, provider = composition()
    vault.raw = b"tampered"
    with pytest.raises(ExtractionError, match="preserved"):
        run(adapter)
    assert not provider.calls


def test_revocation_during_processing_denies_return():
    adapter, repo, _, _, provider = composition()
    original = provider.complete

    def revoke(*args, **kwargs):
        repo.active = False
        return original(*args, **kwargs)

    provider.complete = revoke
    with pytest.raises(AccessRejected):
        run(adapter)


def test_case_revision_change_during_processing_denies_stale_output():
    adapter, repo, _, _, provider = composition()
    original = provider.complete

    def change(*args, **kwargs):
        repo.revision += 1
        return original(*args, **kwargs)

    provider.complete = change
    with pytest.raises(ExtractionError, match="case changed"):
        run(adapter)


def test_catalog_change_during_processing_denies_stale_output():
    adapter, _, catalog, _, provider = composition()
    original = provider.complete

    def change(*args, **kwargs):
        catalog.list_sources = lambda _: ()
        return original(*args, **kwargs)

    provider.complete = change
    with pytest.raises(ExtractionError, match="inventory changed"):
        run(adapter)
