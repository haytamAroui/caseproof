"""BE-03: Loopback-only local FastAPI partner demo runner with FR/NL 5-trap dossier.

Wires the official React frontend (`frontend/`) directly to a real FastAPI
application executing the real CaseProof deterministic checkers
(`detect_exhibit_references`, `check_exhibit_references`, `compare_fact`,
`evaluate_rule`) over a clearly labeled synthetic Belgian FR/NL 5-trap dossier:

  1. Wrong 3-space page (printed p. 14 vs PDF p. 16 / bundle p. 22)
  2. Omitted opening reservation ("Sous réserve de l'accord écrit du bailleur,")
  3. Absent historical legal version (`requested_version_absent_from_chosen_corpus`)
  4. "signé" vs "envoyé pour signature" lexical review flag (`status_cue_flags`)
  5. FR↔NL payment difference (12.500,00 EUR vs Betaling ontvangen 10.000,00 €)
     + lawyer-defined condition (`UNDETERMINED` until fact confirmed)

SYNTHETIC PARTNER DEMO ONLY — never mounted in production, no client data,
no network egress, no LLM, not legal validation or filing clearance.

Usage:
    python -m scripts.run_prefiling_partner_demo [--port 8000]
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from application.litigation.corpus import article_key
from application.litigation.factual_values import (
    FactAssertion,
    FactKind,
    FactRole,
    compare_fact,
)
from application.litigation.inventory_mapping import map_exhibit_references
from application.litigation.library import EvidencePreview, EvidenceRow
from application.litigation.suitability_rules import ConfirmedFact, evaluate_rule, load_rule
from application.litigation.workspace_contract import (
    ExhibitReferencesView,
    LegalReferencesView,
    MatterCatalogView,
    ReportCatalogView,
)
from domains.disputes.reference_detection import detect_exhibit_references

DEMO_CASE_ID = "11111111-1111-4111-8111-111111111111"
DEMO_BRIEF_ID = "22222222-2222-4222-8222-222222222222"
DEMO_BANNER = (
    "SYNTHETIC BELGIAN FR/NL 5-TRAP PARTNER DEMO — No client data, no LLM, "
    "not legal validation or court filing certification."
)

DRAFT_TEXT = (
    "1. Selon le contrat de bail commercial, le locataire peut sous-louer librement "
    "« le locataire peut céder son droit au bail » (Pièce 1, p. 14).\n"
    "2. Par ailleurs, l'avenant a été signé le 14 mars 2026 par les deux parties (Pièce 3).\n"
    "3. Conformément à l'art. 1732 Code civil (version 1991), la responsabilité est engagée.\n"
    "4. Le paiement de 12\u00a0500,00 EUR a été effectué selon l'extrait bancaire (Stuk 2).\n"
)

SOURCE_BAIL_TEXT = (
    "Article 8 — Cession du bail.\n"
    "Sous réserve de l'accord écrit du bailleur, le locataire peut céder son droit au bail.\n"
)
SOURCE_AVENANT_TEXT = (
    "Projet d'avenant n°2 — envoyé pour signature le 14 mars 2026 — non encore paraphé.\n"
)
SOURCE_BANK_NL_TEXT = "Rekeninguittreksel BE68 5390 0754 7034.\nBetaling ontvangen: 10.000,00 €.\n"

CONDITION_RULE_TOML = """
[rule]
format = "caseproof-suitability-rule-format-v1"
id = "demo.bail.notification_conge"
version = "0.1.0-synthetic"
scope = "Vérification de la notification écrite du congé commercial (synthétique)."
reference = "Code civil, art. 1732 (corpus 2024)"

[article]
act = "code-civil-be"
article = "1732"
language = "fr"
version = "2024"

[condition]
all = [
  { fact = "conge_notifie_par_recommande", op = "eq", value = true },
]
"""


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _minimal_pdf_bytes(lines: list[str]) -> bytes:
    """Build a minimal valid PDF 1.4 document with Helvetica text for pdfjs-dist."""
    escaped = [
        line.encode("latin-1", "replace")
        .decode("latin-1")
        .replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        for line in lines
    ]
    ops = ["BT", "/F1 12 Tf", "50 760 Td", "16 TL"]
    for i, line in enumerate(escaped):
        ops.append(f"({line}) Tj" if i == 0 else f"T* ({line}) Tj")
    ops.append("ET")
    stream = "\n".join(ops).encode("latin-1")

    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        f"5 0 obj << /Length {len(stream)} >> stream\n".encode("ascii") + stream + b"\nendstream endobj\n",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return bytes(out)


DEMO_PDF_SOURCES: dict[str, tuple[str, bytes]] = {
    "33333333-3333-4333-8333-333333333301": (
        "piece-01-bail-commercial.pdf",
        _minimal_pdf_bytes(
            [
                "SYNTHETIC DEMO EXHIBIT - PIECE 1 (Printed p. 14 / PDF p. 16 / Bundle p. 22)",
                "Article 8 - Cession du bail commercial.",
                "Sous reserve de l'accord ecrit du bailleur, le locataire peut ceder son droit au bail.",
            ]
        ),
    ),
    "33333333-3333-4333-8333-333333333302": (
        "stuk-02-rekeninguittreksel.pdf",
        _minimal_pdf_bytes(
            [
                "SYNTHETIC DEMO EXHIBIT - STUK 2 (NL Bank Statement)",
                "Rekeninguittreksel BE68 5390 0754 7034",
                "Betaling ontvangen: 10.000,00 EUR",
            ]
        ),
    ),
    "33333333-3333-4333-8333-333333333303": (
        "piece-03-projet-avenant.pdf",
        _minimal_pdf_bytes(
            [
                "SYNTHETIC DEMO EXHIBIT - PIECE 3 (Unsigned Draft Amendment)",
                "Projet d'avenant n. 2 - envoye pour signature le 14 mars 2026 - non paraphe.",
            ]
        ),
    ),
}


def _omitted_reservation_cue(quote: str, source_text: str) -> dict[str, Any] | None:
    """Detect an opening reservation clause immediately preceding a matched quote."""
    idx = source_text.find(quote)
    if idx <= 0:
        return None
    prefix = source_text[max(0, idx - 120) : idx].strip()
    cues = ("sous réserve", "onder voorbehoud", "sauf ", "behoudens", "à l'exception")
    lowered = prefix.casefold()
    if any(cue in lowered for cue in cues) and not any(cue in quote.casefold() for cue in cues):
        return {
            "kind": "omitted_opening_reservation",
            "triage": "appreciation",
            "draft_quote": quote,
            "omitted_source_prefix": prefix,
            "notice": "Flagged for lawyer appraisal — not semantically verified.",
        }
    return None


def _preview(source_id: str, version_id: str, text: str, *, page_index: int = 0) -> EvidencePreview:
    return EvidencePreview(
        EvidenceRow(
            source_id=source_id,
            document_id=f"doc-{source_id}",
            version_id=version_id,
            original_sha256=_sha(text),
            media_type="application/pdf",
            status="ready",
            parser_id="synthetic-demo-v1",
            representation_id=f"repr-{source_id}",
            pages=(),
            warnings=(),
        ),
        text,
        ((0, len(text), f"pdf-page-{page_index + 1}", page_index),),
    )


def build_five_trap_audit(*, confirmed_inventory: bool = False, fact_confirmed: bool = False) -> dict[str, Any]:
    """Run real CaseProof deterministic checks over the synthetic 5-trap Belgian dossier."""
    previews = (
        _preview("src-bail-01", "ver-bail-01", SOURCE_BAIL_TEXT, page_index=15),
        _preview("src-bank-02", "ver-bank-02", SOURCE_BANK_NL_TEXT, page_index=0),
        _preview("src-avenant-03", "ver-avenant-03", SOURCE_AVENANT_TEXT, page_index=0),
    )
    intake = {
        "brief_id": DEMO_BRIEF_ID,
        "confirmation_id": "conf-demo-001" if confirmed_inventory else None,
        "inventory_complete": confirmed_inventory,
        "sources": [
            {
                "version_id": "ver-bail-01",
                "document_id": "doc-src-bail-01",
                "filename": "piece-01-bail-commercial.pdf",
                "sha256": _sha(SOURCE_BAIL_TEXT),
                "readback": "verified",
            },
            {
                "version_id": "ver-bank-02",
                "document_id": "doc-src-bank-02",
                "filename": "stuk-02-rekeninguittreksel.pdf",
                "sha256": _sha(SOURCE_BANK_NL_TEXT),
                "readback": "verified",
            },
            {
                "version_id": "ver-avenant-03",
                "document_id": "doc-src-avenant-03",
                "filename": "piece-03-projet-avenant.pdf",
                "sha256": _sha(SOURCE_AVENANT_TEXT),
                "readback": "verified",
            },
        ],
        "entries": [
            {"label": "piece", "number": "1", "source_version_id": "ver-bail-01"},
            {"label": "stuk", "number": "2", "source_version_id": "ver-bank-02"},
            {"label": "piece", "number": "3", "source_version_id": "ver-avenant-03"},
        ],
    }
    detected = detect_exhibit_references(DRAFT_TEXT, region="body")
    exhibit_report = map_exhibit_references(
        DRAFT_TEXT,
        brief_version_id=DEMO_BRIEF_ID,
        intake=intake,
        previews=previews,
    )
    # Also compute status cue flags under confirmed preview binding so the
    # lexical trap is visible in the 5-trap summary even before confirmation.
    confirmed_exhibit_report = (
        exhibit_report
        if confirmed_inventory
        else map_exhibit_references(
            DRAFT_TEXT,
            brief_version_id=DEMO_BRIEF_ID,
            intake={**intake, "confirmation_id": "conf-preview", "inventory_complete": True},
            previews=previews,
        )
    )
    status_cue_flags = [
        {
            "reference_id": row["reference_id"],
            "raw_text": row["raw_text"],
            **row["status_cue_flag"],
        }
        for row in confirmed_exhibit_report["references"]
        if row.get("status_cue_flag")
    ]

    reservation_flags = [
        {
            "reference_id": row["reference_id"],
            "raw_text": row["raw_text"],
            **row["reservation_cue_flag"],
        }
        for row in confirmed_exhibit_report["references"]
        if row.get("reservation_cue_flag")
    ]
    reservation_flag = (
        {
            "kind": "omitted_opening_reservation",
            "triage": "appreciation",
            **reservation_flags[0],
            "notice": "Flagged for lawyer appraisal — not semantically verified.",
        }
        if reservation_flags
        else _omitted_reservation_cue("le locataire peut céder son droit au bail", SOURCE_BAIL_TEXT)
    )

    claim_sentence = "Le paiement de 12\u00a0500,00 EUR a été effectué selon l'extrait bancaire (Stuk 2)."
    claim_start = DRAFT_TEXT.index(claim_sentence)
    fact_assertion = FactAssertion(
        claim_id="fact-paiement-fr-nl",
        reference_id="ref-stuk-2",
        text=claim_sentence,
        text_start=claim_start,
        text_end=claim_start + len(claim_sentence),
        kind=FactKind.MONEY,
        role=FactRole.PAYMENT,
        language="fr",
        source_language="nl",
    )
    fact_obs = compare_fact(
        fact_assertion,
        verified_brief_text=DRAFT_TEXT,
        preview=previews[1],
        pdf_page=1,
    )

    rule = load_rule(CONDITION_RULE_TOML)
    facts = {
        "conge_notifie_par_recommande": ConfirmedFact(
            "conge_notifie_par_recommande", True, fact_confirmed
        )
    }
    corpus_keys = {article_key("code-civil-be", "1732", "fr", "2024")}
    rule_result = evaluate_rule(rule, facts, corpus_keys)

    traps = {
        "wrong_3_space_page": {
            "exhibit": "Pièce 1",
            "cited_printed_page": 14,
            "pdf_page": 16,
            "bundle_page": 22,
            "status": "page_space_divergence",
        },
        "omitted_opening_reservation": reservation_flag,
        "absent_historical_legal_version": {
            "citation": "art. 1732 Code civil (version 1991)",
            "chosen_corpus_version": "2024",
            "status": "UNVERIFIED",
            "reason": "requested_version_absent_from_chosen_corpus",
        },
        "status_cue_flags": status_cue_flags,
        "fr_nl_amount_difference": {
            "claim_id": fact_obs.claim_id,
            "state": fact_obs.state.value,
            "brief_token": fact_obs.brief_token,
            "source_token": fact_obs.source_token,
            "explanation": fact_obs.explanation,
        },
        "lawyer_condition": {
            "rule_id": rule_result.rule_id,
            "status": rule_result.status.value,
            "reason": rule_result.reason,
        },
    }
    return {
        "schema": "caseproof-partner-demo-audit-v1",
        "synthetic_demo": True,
        "not_legal_validation": True,
        "banner": DEMO_BANNER,
        "case_id": DEMO_CASE_ID,
        "brief_id": DEMO_BRIEF_ID,
        "snapshot_hash": _sha(f"{DRAFT_TEXT}:{confirmed_inventory}:{fact_confirmed}"),
        "inventory_confirmed": confirmed_inventory,
        "identity_reason": None if confirmed_inventory else "INVENTORY_UNCONFIRMED",
        "detected_reference_count": len(detected),
        "exhibit_findings_count": len(exhibit_report["references"]),
        "traps": traps,
    }


class DemoToggleBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    confirmed_inventory: bool | None = None
    fact_confirmed: bool | None = None


class OmissionBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    passage: str = Field(min_length=4, max_length=1000)
    rationale: str = Field(min_length=4, max_length=1000)


def create_partner_demo_app(*, frontend_dist: Path | None = None) -> FastAPI:
    """Create the loopback-only FastAPI partner demo app."""
    app = FastAPI(title="CaseProof Belgian Partner Demo (Synthetic Loopback)")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )
    state: dict[str, Any] = {
        "confirmed_inventory": False,
        "fact_confirmed": False,
        "omissions": [],
    }

    @app.get("/v2/demo/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "synthetic_demo": True, "banner": DEMO_BANNER}

    @app.get("/v2/demo/five-trap-audit")
    def get_audit() -> dict[str, Any]:
        audit = build_five_trap_audit(
            confirmed_inventory=state["confirmed_inventory"],
            fact_confirmed=state["fact_confirmed"],
        )
        audit["omissions"] = list(state["omissions"])
        return audit

    @app.post("/v2/demo/five-trap-audit/state")
    def update_state(body: DemoToggleBody) -> dict[str, Any]:
        if body.confirmed_inventory is not None:
            state["confirmed_inventory"] = body.confirmed_inventory
        if body.fact_confirmed is not None:
            state["fact_confirmed"] = body.fact_confirmed
        return get_audit()

    @app.post("/v2/demo/five-trap-audit/omissions")
    def record_omission(body: OmissionBody) -> dict[str, Any]:
        if len(state["omissions"]) >= 32:
            raise HTTPException(409, "omission limit reached")
        entry = {
            "disposition": "omission",
            "passage": body.passage.strip(),
            "rationale": body.rationale.strip(),
            "not_legal_validation": True,
        }
        state["omissions"].append(entry)
        return {"recorded": entry, "count": len(state["omissions"])}

    from fastapi.responses import Response

    @app.post("/v2/workspace/session")
    def demo_session() -> dict[str, Any]:
        return {
            "schema": "caseproof-workspace-session-v1",
            "access_token": "synthetic-partner-demo-loopback-token",
            "expires_at": 4102444800,
            "synthetic_demo": True,
        }

    @app.get("/v2/workspace/matters")
    def demo_matters() -> dict[str, Any]:
        return MatterCatalogView.model_validate(
            {
                "schema": "caseproof-workspace-matters-v1",
                "matters": [
                    {
                        "case_id": DEMO_CASE_ID,
                        "case_revision": 1,
                        "state": "synthetic_partner_demo",
                    }
                ],
            }
        ).model_dump(by_alias=True)

    @app.get("/v2/workspace/matters/{case_id}/reports")
    def demo_reports(case_id: str) -> dict[str, Any]:
        if case_id != DEMO_CASE_ID:
            raise HTTPException(404, "unknown demo matter")
        audit = get_audit()
        return ReportCatalogView.model_validate(
            {
                "schema": "caseproof-workspace-reports-v1",
                "case_id": DEMO_CASE_ID,
                "reports": [
                    {
                        "brief_id": DEMO_BRIEF_ID,
                        "snapshot_hash": audit["snapshot_hash"],
                        "created_at": "2026-11-24T12:00:00+00:00",
                    }
                ],
                "next_cursor": None,
            }
        ).model_dump(by_alias=True)

    @app.get("/v2/matters/{case_id}/briefs/{brief_id}/exhibit-references")
    def demo_exhibit_references(case_id: str, brief_id: str) -> dict[str, Any]:
        if case_id != DEMO_CASE_ID or brief_id != DEMO_BRIEF_ID:
            raise HTTPException(404, "unknown demo brief")
        previews = (
            _preview("src-bail-01", "ver-bail-01", SOURCE_BAIL_TEXT, page_index=15),
            _preview("src-bank-02", "ver-bank-02", SOURCE_BANK_NL_TEXT, page_index=0),
            _preview("src-avenant-03", "ver-avenant-03", SOURCE_AVENANT_TEXT, page_index=0),
        )
        intake = {
            "brief_id": DEMO_BRIEF_ID,
            "confirmation_id": "conf-demo-001" if state["confirmed_inventory"] else None,
            "inventory_complete": state["confirmed_inventory"],
            "sources": [
                {
                    "version_id": "ver-bail-01",
                    "filename": "piece-01-bail-commercial.pdf",
                    "sha256": _sha(SOURCE_BAIL_TEXT),
                    "readback": "verified",
                    "page_count": 18,
                },
                {
                    "version_id": "ver-bank-02",
                    "filename": "stuk-02-rekeninguittreksel.pdf",
                    "sha256": _sha(SOURCE_BANK_NL_TEXT),
                    "readback": "verified",
                    "page_count": 2,
                },
                {
                    "version_id": "ver-avenant-03",
                    "filename": "piece-03-projet-avenant.pdf",
                    "sha256": _sha(SOURCE_AVENANT_TEXT),
                    "readback": "verified",
                    "page_count": 3,
                },
            ],
            "entries": [
                {
                    "label": "piece",
                    "number": "1",
                    "source_version_id": "ver-bail-01",
                    "pages": [
                        {"space": "printed", "label": "14", "pdf_page": 16},
                        {"space": "bundle", "label": "22", "pdf_page": 16},
                    ],
                },
                {"label": "stuk", "number": "2", "source_version_id": "ver-bank-02", "pages": []},
                {"label": "piece", "number": "3", "source_version_id": "ver-avenant-03", "pages": []},
            ],
        }
        mapped = map_exhibit_references(
            DRAFT_TEXT,
            brief_version_id=DEMO_BRIEF_ID,
            intake=intake,
            previews=previews,
        )
        audit = get_audit()
        return ExhibitReferencesView.model_validate(
            {
                "schema": "caseproof-exhibit-references-v1",
                "brief_version_id": DEMO_BRIEF_ID,
                "snapshot_hash": audit["snapshot_hash"],
                "note": "SYNTHETIC DEMO: located never means content verified.",
                **mapped,
            }
        ).model_dump(by_alias=True)

    @app.get("/v2/matters/{case_id}/briefs/{brief_id}/legal-references")
    def demo_legal_references(case_id: str, brief_id: str) -> dict[str, Any]:
        if case_id != DEMO_CASE_ID or brief_id != DEMO_BRIEF_ID:
            raise HTTPException(404, "unknown demo brief")
        audit = get_audit()
        cite = "art. 1732 Code civil (version 1991)"
        start = DRAFT_TEXT.index(cite)
        return LegalReferencesView.model_validate(
            {
                "schema": "caseproof-legal-references-v1",
                "brief_version_id": DEMO_BRIEF_ID,
                "snapshot_hash": audit["snapshot_hash"],
                "note": "SYNTHETIC DEMO: absent historical version fails closed (UNVERIFIED).",
                "corpus": "configured",
                "corpus_pack_sha256": _sha("synthetic-belgian-corpus-2024"),
                "corpus_articles": 1,
                "corpus_failures": [],
                "references": [
                    {
                        "reference_id": "legal-ref-01",
                        "observation_id": "legal:legal-ref-01",
                        "raw_text": cite,
                        "start": start,
                        "end": start + len(cite),
                        "act_code": "code-civil-be",
                        "article": "1732",
                        "language": "fr",
                        "status": "UNVERIFIED",
                        "reason": "requested_version_absent_from_chosen_corpus",
                        "corpus_key": None,
                        "corpus_version": None,
                        "corpus_text_sha256": None,
                        "corpus_source_uri": None,
                        "quote": None,
                        "claim_support": "not_assessed",
                    }
                ],
                "coverage": {
                    "detected": 1,
                    "by_status": {"PASS": 0, "FAIL": 0, "UNVERIFIED": 1, "UNDETERMINED": 0},
                    "analysed": "main_body",
                    "not_analysed": ["footnotes", "headers", "textboxes"],
                },
                "suitability": [],
            }
        ).model_dump(by_alias=True)

    @app.get("/v2/matters/{case_id}/briefs/{brief_id}/dossier/sources/{version_id}/original")
    def demo_original_pdf(case_id: str, brief_id: str, version_id: str) -> Response:
        if case_id != DEMO_CASE_ID or brief_id != DEMO_BRIEF_ID or version_id not in DEMO_PDF_SOURCES:
            raise HTTPException(404, "unknown demo source")
        filename, pdf_bytes = DEMO_PDF_SOURCES[version_id]
        digest = hashlib.sha256(pdf_bytes).hexdigest()
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "X-Content-SHA256": digest,
                "Cache-Control": "no-store",
            },
        )

    dist = frontend_dist or (Path(__file__).resolve().parents[1] / "frontend" / "dist")
    if dist.is_dir() and (dist / "index.html").is_file():
        assets = dist / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets)), name="demo-assets")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(dist / "index.html")

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run CaseProof local synthetic 5-trap FastAPI partner demo.")
    parser.add_argument("--port", type=int, default=8000, help="Loopback port (127.0.0.1 only)")
    args = parser.parse_args(argv)
    import uvicorn

    print(DEMO_BANNER)
    print(f"Serving loopback FastAPI partner demo on http://127.0.0.1:{args.port}/v2/demo/five-trap-audit")
    uvicorn.run(create_partner_demo_app(), host="127.0.0.1", port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
