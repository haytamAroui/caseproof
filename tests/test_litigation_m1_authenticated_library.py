"""M1 internal auth/custody composition tests; fixtures are not cloud identity proof."""
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

import pytest

from application.litigation.library import EvidenceIndexer
from apps.api.access_control import (
    AccessRejected,
    CaseAccessService,
    CaseAction,
    InvalidBearer,
    StoredCase,
    StoredMembership,
    VerifiedSubject,
)
from apps.api.authenticated_document_intelligence import StoredDocument
from apps.api.authenticated_evidence_library import AuthenticatedEvidenceLibrary
from infrastructure.parsers.limited import LimitedDocumentParser
from packages.evidence_kernel.domain.source_versions import SourceVersion

NOW = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)
ORG, CASE, ACTOR = (str(UUID(int=i)) for i in (4001, 4002, 4003))
READ = frozenset({CaseAction.READ_CASE, CaseAction.READ_EVIDENCE})


class Verifier:
    calls = 0

    def verify_bearer(self, token):
        self.calls += 1
        if token != "m1-synthetic-fixture":
            raise InvalidBearer("invalid")
        return VerifiedSubject(ACTOR, "m1-fixture-issuer", "authenticated", NOW, NOW + timedelta(hours=1), False)


class Memberships:
    actions = READ
    active = True
    revision = 1
    lookups = 0

    def lookup_case_membership(self, subject_id, case_id):
        self.lookups += 1
        if case_id != CASE:
            return None
        return StoredCase(CASE, ORG, self.revision, ACTOR), StoredMembership(
            subject_id, ORG, self.active, self.actions
        )


class Catalog:
    reads = 0

    def __init__(self):
        raw = b"De levering gebeurde op 12 april 2026."
        self.original = SourceVersion(
            "first", "v1", sha256(raw).hexdigest(), raw, NOW, "text/plain"
        )
        self.records = (StoredDocument("first", self.original, UUID(int=4020)),)

    def list_sources(self, authorized):
        self.reads += 1
        assert authorized.org_id == ORG and authorized.case_id == CASE
        return self.records


class Vault:
    reads = 0
    tamper = False
    on_read = None

    def __init__(self, catalog):
        self.catalog = catalog

    def read(self, *, scope, intent_id):
        self.reads += 1
        assert str(scope.org_id) == ORG and str(scope.case_id) == CASE
        record = self.catalog.records[0]
        assert intent_id == record.intent_id
        if self.on_read is not None:
            self.on_read(self.reads)
        return b"tampered" if self.tamper else record.original.content


def fixture():
    memberships, verifier, catalog = Memberships(), Verifier(), Catalog()
    access = CaseAccessService(verifier, memberships, "m1-fixture-issuer", "authenticated", lambda: NOW)
    vault = Vault(catalog)
    service = AuthenticatedEvidenceLibrary(
        access, catalog, lambda _context: vault, EvidenceIndexer(LimitedDocumentParser())
    )
    return service, memberships, verifier, catalog, vault


def get_inventory(service, *, token="m1-synthetic-fixture", case=CASE):
    return service.inventory(bearer=token, case_id=case)


def test_authorized_inventory_has_lineage_not_raw_text():
    service, _, verifier, catalog, vault = fixture()
    inventory = get_inventory(service)
    assert inventory.complete and inventory.failed_count == 0
    row = inventory.rows[0]
    assert row.status == "ready"
    assert row.original_sha256 == catalog.original.sha256_hex
    assert row.representation_id and row.parser_id
    assert not hasattr(row, "text")
    assert vault.reads == 2 and verifier.calls == 4


def test_opt_in_preview_has_bounded_exact_representation():
    service, _, _, _, _ = fixture()
    value = service.preview(bearer="m1-synthetic-fixture", case_id=CASE, source_id="first")
    assert "De levering" in value.text
    assert value.spans[0][0] == 0 and value.row.status == "ready"


@pytest.mark.parametrize("token,case", [
    ("", CASE), ("bad", CASE), ("m1-synthetic-fixture", str(UUID(int=88888))),
])
def test_auth_failure_never_reads_catalog_or_vault(token, case):
    service, _, _, catalog, vault = fixture()
    with pytest.raises(AccessRejected):
        get_inventory(service, token=token, case=case)
    assert catalog.reads == vault.reads == 0


def test_lack_of_evidence_action_and_revoked_membership_are_denied():
    service, memberships, _, _, vault = fixture()
    memberships.actions = frozenset({CaseAction.READ_CASE})
    with pytest.raises(AccessRejected):
        get_inventory(service)
    memberships.actions = READ
    memberships.active = False
    with pytest.raises(AccessRejected):
        get_inventory(service)
    assert vault.reads == 0


def test_tampered_source_bytes_never_reach_parser():
    service, _, _, _, vault = fixture()
    vault.tamper = True
    from application.extraction.contracts import ExtractionError

    with pytest.raises(ExtractionError, match="immutable"):
        get_inventory(service)


def test_revocation_after_first_vault_read_blocks_result():
    service, memberships, _, _, vault = fixture()
    vault.on_read = lambda _: setattr(memberships, "active", False)
    with pytest.raises(AccessRejected):
        get_inventory(service)


def test_catalog_mutation_during_parse_causes_stale_abort():
    service, _, _, catalog, vault = fixture()

    def mutate(_):
        catalog.records = ()

    vault.on_read = mutate
    from application.extraction.contracts import ExtractionError

    with pytest.raises(ExtractionError, match="source inventory changed"):
        get_inventory(service)


def test_matter_revision_change_blocks_stale_preview():
    service, memberships, _, _, vault = fixture()
    vault.on_read = lambda _: setattr(memberships, "revision", 2)
    with pytest.raises(AccessRejected):
        service.preview(bearer="m1-synthetic-fixture", case_id=CASE, source_id="first")


def test_unknown_document_is_sanitized_and_does_not_return_text():
    service, _, _, _, _ = fixture()
    with pytest.raises(AccessRejected) as exc:
        service.preview(bearer="m1-synthetic-fixture", case_id=CASE, source_id="unknown")
    assert exc.value.http_status == 404
