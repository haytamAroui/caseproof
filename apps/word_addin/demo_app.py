"""Synthetic-only Word demo; run on a trusted localhost HTTPS server.

This process contains no real identity, storage, customer data or production
configuration. It is never imported by the normal API.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from ipaddress import ip_address
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from application.litigation.brief_checks import DraftReference, VersionedBrief
from application.litigation.library import EvidencePreview, EvidenceRow
from application.litigation.matter_policy import (
    CurrentMatterGrant,
    CurrentOrganizationGrant,
    MatterPermission,
    OrganizationPermission,
)
from application.litigation.unified_review import BriefRepresentation, SourceScope
from apps.api.access_control import InvalidBearer, VerifiedSubject
from apps.api.litigation_check_service import AuthorizedLitigationChecker, CheckBundle, PrivateMatterAccess
from apps.api.litigation_evidence_search import AuthorizedEvidenceSearch
from apps.api.litigation_search_app import create_litigation_search_app
from domains.disputes.exhibits import ExhibitEntry, ExhibitPage, ExhibitRegister

ACTOR = "synthetic-user"
CASE = "synthetic-matter"
BRIEF = "synthetic-brief"
TOKEN = "synthetic-demo-only"


class SyntheticVerifier:
    def verify_bearer(self, token: str) -> VerifiedSubject:
        if token != TOKEN:
            raise InvalidBearer("invalid synthetic token")
        now = datetime.now(UTC)
        return VerifiedSubject(ACTOR, "synthetic-only", "authenticated", now, now + timedelta(minutes=5), False)


class SyntheticStore:
    def current_access(self, subject_id: str, case_id: str) -> PrivateMatterAccess | None:
        if subject_id != ACTOR or case_id != CASE:
            return None
        member = CurrentOrganizationGrant(ACTOR, "synthetic-org", True, frozenset({
            OrganizationPermission.CASE_READ, OrganizationPermission.EVIDENCE_READ,
            OrganizationPermission.FINDING_WRITE,
        }), 1)
        grant = CurrentMatterGrant(ACTOR, "synthetic-org", CASE, True, frozenset({
            MatterPermission.READ, MatterPermission.EVIDENCE_READ, MatterPermission.DRAFT_CHECK,
        }), 1)
        return PrivateMatterAccess(CASE, "synthetic-org", member, grant, 1)

    def load_bundle(self, *, case_id: str, brief_version_id: str, access: PrivateMatterAccess) -> CheckBundle:
        if case_id != CASE or brief_version_id != BRIEF or access.case_id != CASE:
            raise ValueError("synthetic scope mismatch")
        raw = b"De betaling van 250 euro is verschuldigd op 1 maart 2026."
        digest = sha256(raw).hexdigest()
        brief = VersionedBrief(CASE, BRIEF, digest, (DraftReference("reference", "Stuk 1", None, 1),))
        representation = BriefRepresentation(brief, raw.decode(), digest, "synthetic-demo", ())
        row = EvidenceRow("synthetic-source", "synthetic-document", "synthetic-v1", digest,
                          "application/pdf", "ready", "synthetic-demo", "synthetic-representation", (), ())
        preview = EvidencePreview(row, raw.decode(), ((0, len(raw.decode()), "page:0", 0),))
        register = ExhibitRegister(1, (ExhibitEntry(
            "synthetic-exhibit", "Stuk 1", (ExhibitPage("synthetic-source", "synthetic-v1", 1),),
            aliases=("Pièce 1",), confirmed=True,
        ),))
        return CheckBundle(representation, register, (preview,), SourceScope((("synthetic-source", "synthetic-v1"),)))

    def still_current(self, *, access: PrivateMatterAccess, bundle: CheckBundle) -> bool:
        return self.current_access(access.member.actor_id, access.case_id) == access


service = AuthorizedLitigationChecker(
    verifier=SyntheticVerifier(), store=SyntheticStore(), issuer="synthetic-only", audience="authenticated",
)
app = create_litigation_search_app(AuthorizedEvidenceSearch(service))
@app.middleware("http")
async def local_only(request: Request, call_next):  # type: ignore[no-untyped-def]
    try:
        if request.client is None or not ip_address(request.client.host).is_loopback:
            return JSONResponse({"error": "synthetic_demo_local_only"}, status_code=403)
    except ValueError:
        return JSONResponse({"error": "synthetic_demo_local_only"}, status_code=403)
    return await call_next(request)


app.mount("/", StaticFiles(directory=Path(__file__).parent, html=True), name="synthetic-static")
