"""Reproducible loopback signed workbench: upload -> publish -> check.

Brings up the genuine development composition (create_litigation_development_app)
against the isolated disposable PostgreSQL backend with the in-repo
DisposableSignedSourceLibrary and DisposableSignedBriefPublisher ports wired,
then serves the signed workbench on 127.0.0.1 so the full browser journey
runs without any operator intervention outside the UI: select a registered
document/version, upload the immutable original, publish it as the next
working-brief version (the server resolves the brief; optimistic concurrency
is tracked by the client), run the check, review, upload a corrected
version, publish again.

Fail-closed: requires the disposable CI database opt-in
(CASEPROOF_DISPOSABLE_DB=YES, PGHOST 127.0.0.1); never touches a shared
Supabase project, never accepts credentials from requests, and uses the
synthetic fixture verifier only. All fixtures are generated synthetic
content; nothing here is a real matter.

Usage: uv run --locked python -m scripts.run_signed_workbench_disposable
"""

from __future__ import annotations

import os
import re
import sys
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PORT = 8377

CORPUS = {
    "Source A (synthétique)": (
        "SOURCE A SYNTHETIQUE - aucune affaire reelle.\nLe delai de resiliation est de six mois.\n"
    ),
    "Source B (synthétique)": (
        "SOURCE B SYNTHETIQUE - aucune affaire reelle.\nLe preavis court du premier jour du mois suivant.\n"
    ),
}

BRIEF_V1_TEXT = (
    "BRIEF SYNTHETIQUE v1 - demonstration sans affaire reelle.\n"
    "Le contrat prevoit «un delai de trois mois» (Source A (synthétique)).\n"
)
BRIEF_V2_TEXT = (
    "BRIEF SYNTHETIQUE v2 - demonstration sans affaire reelle.\n"
    "Le contrat prevoit «un delai de six mois» (Source A (synthétique)).\n"
)

QUOTE_RE = re.compile(r"«\s*(?P<quote>[^«»]{4,600}?)\s*»\s*\((?P<label>[^)]{4,120})\)")


def extract_references(text: str) -> list[tuple[str, str, str]]:
    refs = []
    for i, m in enumerate(QUOTE_RE.finditer(text), 1):
        label = m.group("label").strip()
        if label in CORPUS:
            refs.append((f"ref-{i:02d}", label, m.group("quote").strip()))
    return refs


def build_representation(*, case_id, version_id, text, references, original_sha256_hex):
    from application.litigation.brief_checks import DraftReference, VersionedBrief
    from application.litigation.unified_review import BriefRepresentation

    refs = tuple(DraftReference(rid, label, quote) for rid, label, quote in references)
    brief = VersionedBrief(str(case_id), str(version_id), original_sha256_hex, refs)
    return BriefRepresentation(brief, text, sha256(text.encode()).hexdigest(), "demo-utf8-v1", ())


def _docx_bytes(text: str) -> bytes:
    from docx import Document

    document = Document()
    for line in text.splitlines():
        document.add_paragraph(line)
    target = Path("/tmp/caseproof-workbench-fixture.docx")
    document.save(str(target))
    data = target.read_bytes()
    target.unlink()
    return data


def _guard() -> None:
    if os.environ.get("CASEPROOF_DISPOSABLE_DB") != "YES":
        raise SystemExit("CASEPROOF_DISPOSABLE_DB=YES requis (base disposable uniquement)")
    if os.environ.get("PGHOST") not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("PGHOST loopback requis (jamais de projet partage)")


def main() -> None:
    _guard()
    from application.litigation.exhibit_confirmation import serialized_entries
    from apps.api.disposable_litigation_brief_graph import DisposableBriefGraphStore
    from apps.api.disposable_litigation_review_ledger import DisposableM2ReviewLedger
    from apps.api.disposable_review_record import DisposableSignedReviewRecord
    from apps.api.disposable_signed_brief_publisher import DisposableSignedBriefPublisher
    from apps.api.disposable_signed_source_library import DisposableSignedSourceLibrary
    from apps.api.evidence_vault_protocol import VaultScope
    from apps.api.litigation_check_service import AuthorizedLitigationChecker
    from apps.api.litigation_development_app import create_litigation_development_app
    from apps.api.litigation_review_workspace import SignedReviewWorkspace
    from apps.api.postgres_litigation_check_store import PostgresPrivateMatterCheckStore
    from domains.disputes.exhibits import ExhibitEntry, ExhibitPage
    from scripts.extraction_fixtures import NOW
    from scripts.verify_document_intake_integration import SyntheticVerifier
    from scripts.verify_m2_brief_graph import add_verified_version, new_binding
    from scripts.verify_vault_integration import begin, connect, coordinator, seed

    temp = TemporaryDirectory(prefix="caseproof-workbench-")
    root = Path(temp.name)
    f = seed(data=b"placeholder non utilise comme source du brief")
    vault = coordinator(root, f)
    begin(vault, f)
    vault.upload(scope=f.scope, intent_id=f.intent, data=f.data)

    corpus_fixtures = {}
    for label, text in CORPUS.items():
        corpus_fixtures[label] = add_verified_version(root, f, text.encode())
    entries = []
    for idx, (label, cf) in enumerate(corpus_fixtures.items(), 1):
        entries.append(
            ExhibitEntry(
                f"piece-{idx}",
                label,
                (ExhibitPage(str(new_binding(cf).document_id), str(cf.version), printed_page=1),),
                confirmed=True,
            )
        )
    encoded = serialized_entries(tuple(entries))
    with connect() as conn:
        conn.execute(
            "update caseproof.organization_members "
            "set actions=array['case:read','finding:write','review:request','evidence:read']::text[] "
            "where org_id=%s and user_id=%s",
            (f.scope.org_id, f.actor),
        )
        conn.execute(
            "insert into caseproof._m1_matter_grants(org_id,case_id,user_id,role,permissions) "
            "values(%s,%s,%s,'reviewer',array['case:read','draft:check','review:request',"
            "'exhibit:confirm','evidence:read','evidence:upload']::text[])",
            (f.scope.org_id, f.scope.case_id, f.actor),
        )
        conn.execute(
            "select * from caseproof._m1_disposable_confirm_exhibits(%s,%s,%s,0,%s::jsonb,%s)",
            (f.actor, f.scope.case_id, uuid4(), encoded.decode("utf-8"), sha256(encoded).hexdigest()),
        ).fetchone()

    reader = lambda org, case, intent: coordinator(root, f).read(  # noqa: E731
        scope=VaultScope(org, case), intent_id=intent
    )
    graph = DisposableBriefGraphStore(connect, reader)
    store = PostgresPrivateMatterCheckStore(connect, graph, reader)
    ledger = DisposableM2ReviewLedger(connect)
    verifier = SyntheticVerifier(f.actor)
    service = AuthorizedLitigationChecker(
        verifier=verifier,
        store=store,
        publisher=ledger,
        issuer="synthetic-issuer",
        audience="authenticated",
        clock=lambda: NOW + timedelta(minutes=1),
    )
    workspace = SignedReviewWorkspace(service, ledger)
    library = DisposableSignedSourceLibrary(
        connect=connect,
        byte_store_root=root,
        verify_bearer=verifier.verify_bearer,
        access_lookup=store.current_access,
    )
    publisher = DisposableSignedBriefPublisher(
        connect=connect,
        library=library,
        graph=graph,
        verify_bearer=verifier.verify_bearer,
        access_lookup=store.current_access,
        extract_references=extract_references,
        build_representation=build_representation,
    )
    record_port = DisposableSignedReviewRecord(
        connect=connect,
        verify_bearer=verifier.verify_bearer,
        access_lookup=store.current_access,
    )

    fixtures = root / "fixtures"
    fixtures.mkdir()
    paths = {}
    for name, text in (("brief-v1.docx", BRIEF_V1_TEXT), ("brief-v2.docx", BRIEF_V2_TEXT)):
        data = _docx_bytes(text)
        path = fixtures / name
        path.write_bytes(data)
        paths[name] = (path, data)
    registered = {}
    for name, (_path, data) in paths.items():
        document, version = uuid4(), uuid4()
        with connect() as conn:
            conn.execute(
                "insert into caseproof.documents(id,org_id,case_id,source_label) values(%s,%s,%s,%s)",
                (document, f.scope.org_id, f.scope.case_id, name),
            )
            conn.execute(
                "insert into caseproof.document_versions(id,org_id,document_id,version_number,"
                "original_sha256_hex,byte_length,media_type) values(%s,%s,%s,1,%s,%s,%s)",
                (version, f.scope.org_id, document, sha256(data).hexdigest(), len(data), DOCX_MIME),
            )
        registered[name] = (document, version)

    app = create_litigation_development_app(
        checker=service,
        reviews=workspace,
        signed_originals=library,
        signed_brief_publisher=publisher,
        signed_review_record=record_port,
        workspace_directory=REPO / "apps/web/clearbrief",
    )
    import uvicorn

    print(f"CASE_ID={f.scope.case_id}")
    print(f"BRIEF_PLACEHOLDER={uuid4()} (le workbench bascule sur la version publiee)")
    print(f"FIXTURES={fixtures}")
    print(f"WORKBENCH=http://127.0.0.1:{PORT}/workspace")
    print("Token fixture: synthetic-fixture-only (verifieur synthetique, dev uniquement)")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
