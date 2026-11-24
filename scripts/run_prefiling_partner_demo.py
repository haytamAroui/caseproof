"""BE-03: Loopback-only local FastAPI partner demo runner with FR/NL 5-trap dossier.

Wires the official React frontend (`frontend/dist` under `/workspace/`) directly
to a real FastAPI application executing the real CaseProof deterministic checkers
(`detect_exhibit_references`, `map_exhibit_references`, `compare_fact`,
`evaluate_rule`) over a clearly labeled synthetic Belgian FR/NL 5-trap dossier
packaged in the canonical 4-source intake envelope (1 draft, 1 inventory, 2 PDF
exhibits):

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
import hmac
import io
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from docx import Document
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response
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
    ClearbriefReviewReceipt,
    ClearbriefReviewState,
    ConditionMatchesView,
    ConditionsStateView,
    DraftExcerptView,
    ExhibitReferencesView,
    LegalPassageView,
    LegalReferencesView,
    MatterCatalogView,
    ReportCatalogView,
    ReviewLedgerView,
)
from domains.disputes.reference_detection import detect_exhibit_references
from infrastructure.parsers.dossier_docx_export import annotated_docx

DEMO_ORG_ID = "00000000-0000-4000-8000-000000000001"
DEMO_CASE_ID = "11111111-1111-4111-8111-111111111111"
DEMO_BRIEF_ID = "22222222-2222-4222-8222-222222222222"
DEMO_ACTOR_ID = "55555555-5555-4555-8555-555555555555"
DEMO_ACTOR_EMAIL = "demo-lawyer@caseproof.local"
DEMO_HMAC_KEY = b"synthetic-partner-demo-loopback-hmac-key-not-production"

# Canonical 4-source intake envelope (capacity-policy.json source_count == 4):
# 1 draft + 1 inventory + 2 exhibit PDFs (piece-01 bundles bail p.16 + avenant p.17).
VER_PIECE_1 = "33333333-3333-4333-8333-333333333301"
VER_STUK_2 = "33333333-3333-4333-8333-333333333302"
VER_INVENTORY = "33333333-3333-4333-8333-333333333304"

DOC_DRAFT = "44444444-4444-4444-8444-444444444400"
DOC_PIECE_1 = "44444444-4444-4444-8444-444444444401"
DOC_STUK_2 = "44444444-4444-4444-8444-444444444402"
DOC_INVENTORY = "44444444-4444-4444-8444-444444444404"

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
SOURCE_PIECE_1_COMBINED_TEXT = SOURCE_BAIL_TEXT + "\n" + SOURCE_AVENANT_TEXT
SOURCE_BANK_NL_TEXT = "Rekeninguittreksel BE68 5390 0754 7034.\nBetaling ontvangen: 10.000,00 €.\n"
INVENTORY_TEXT = (
    "Inventaire des pièces (synthétique)\n"
    "Pièce 1 : Contrat de bail commercial (p. imprimée 14 = p. PDF 16 / liasse 22)\n"
    "Stuk 2 : Rekeninguittreksel BE68 5390 0754 7034\n"
    "Pièce 3 : Projet d'avenant n°2 (annexé en p. PDF 17 du classeur Pièce 1)\n"
)

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


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _minimal_pdf_bytes(pages: list[list[str]]) -> bytes:
    """Build a minimal valid multi-page PDF 1.4 document with Helvetica text for pdfjs-dist."""
    if not pages:
        pages = [["Empty page"]]
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(len(pages)))
    objects: list[bytes] = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        f"2 0 obj << /Type /Pages /Kids [{kids}] /Count {len(pages)} >> endobj\n".encode("ascii"),
        b"3 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]
    for i, lines in enumerate(pages):
        escaped = [
            line.encode("latin-1", "replace")
            .decode("latin-1")
            .replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
            for line in lines
        ]
        ops = ["BT", "/F1 12 Tf", "50 760 Td", "16 TL"]
        for line_idx, line in enumerate(escaped):
            ops.append(f"({line}) Tj" if line_idx == 0 else f"T* ({line}) Tj")
        ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        page_num = 4 + 2 * i
        stream_num = 5 + 2 * i
        objects.append(
            (
                f"{page_num} 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {stream_num} 0 R >> endobj\n"
            ).encode("ascii")
        )
        objects.append(
            f"{stream_num} 0 obj << /Length {len(stream)} >> stream\n".encode("ascii")
            + stream
            + b"\nendstream endobj\n"
        )

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


def _minimal_docx_bytes(text: str) -> bytes:
    """Build a valid OpenXML DOCX archive via python-docx so annotated_docx() appends cleanly."""
    doc = Document()
    for line in text.splitlines():
        if line:
            doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


_PIECE_1_PAGES: list[list[str]] = [
    [
        f"SYNTHETIC DEMO EXHIBIT - PIECE 1 (PDF page {idx} of 17)",
        "Contrat de bail commercial (page d'annexe synthétique).",
    ]
    for idx in range(1, 16)
] + [
    [
        "SYNTHETIC DEMO EXHIBIT - PIECE 1 (Printed p. 14 / PDF p. 16 / Bundle p. 22)",
        "Article 8 - Cession du bail commercial.",
        "Sous reserve de l'accord ecrit du bailleur, le locataire peut ceder son droit au bail.",
    ],
    [
        "SYNTHETIC DEMO EXHIBIT - PIECE 3 / ANNEXE AVENANT (PDF p. 17)",
        "Projet d'avenant n. 2 - envoye pour signature le 14 mars 2026 - non encore paraphe.",
    ],
]

DEMO_PDF_SOURCES: dict[str, tuple[str, bytes]] = {
    VER_PIECE_1: (
        "piece-01-bail-et-avenant.pdf",
        _minimal_pdf_bytes(_PIECE_1_PAGES),
    ),
    VER_STUK_2: (
        "stuk-02-rekeninguittreksel.pdf",
        _minimal_pdf_bytes(
            [
                [
                    "SYNTHETIC DEMO EXHIBIT - STUK 2 (NL Bank Statement, p. 1)",
                    "Rekeninguittreksel BE68 5390 0754 7034",
                    "Betaling ontvangen: 10.000,00 EUR",
                ],
                ["SYNTHETIC DEMO EXHIBIT - STUK 2 (p. 2 - continuation)"],
            ]
        ),
    ),
}

DEMO_DRAFT_DOCX_BYTES = _minimal_docx_bytes(DRAFT_TEXT)
DEMO_DRAFT_DOCX_SHA256 = _sha_bytes(DEMO_DRAFT_DOCX_BYTES)
DEMO_INVENTORY_BYTES = INVENTORY_TEXT.encode("utf-8")
DEMO_INVENTORY_SHA256 = _sha_bytes(DEMO_INVENTORY_BYTES)

DEMO_SOURCE_META: dict[str, dict[str, Any]] = {
    VER_PIECE_1: {
        "source_id": "src-bail-01",
        "document_id": DOC_PIECE_1,
        "version_id": VER_PIECE_1,
        "filename": DEMO_PDF_SOURCES[VER_PIECE_1][0],
        "sha256": _sha_bytes(DEMO_PDF_SOURCES[VER_PIECE_1][1]),
        "byte_length": len(DEMO_PDF_SOURCES[VER_PIECE_1][1]),
        "page_count": 17,
        "text": SOURCE_PIECE_1_COMBINED_TEXT,
        "spans": (
            (0, len(SOURCE_BAIL_TEXT), "pdf-page-16", 15),
            (
                len(SOURCE_BAIL_TEXT) + 1,
                len(SOURCE_PIECE_1_COMBINED_TEXT),
                "pdf-page-17",
                16,
            ),
        ),
    },
    VER_STUK_2: {
        "source_id": "src-bank-02",
        "document_id": DOC_STUK_2,
        "version_id": VER_STUK_2,
        "filename": DEMO_PDF_SOURCES[VER_STUK_2][0],
        "sha256": _sha_bytes(DEMO_PDF_SOURCES[VER_STUK_2][1]),
        "byte_length": len(DEMO_PDF_SOURCES[VER_STUK_2][1]),
        "page_count": 2,
        "text": SOURCE_BANK_NL_TEXT,
        "spans": ((0, len(SOURCE_BANK_NL_TEXT), "pdf-page-1", 0),),
    },
}


def _bundle_signature_for(draft_sha256: str) -> str:
    return _sha(
        "|".join(
            [
                draft_sha256,
                DEMO_INVENTORY_SHA256,
                DEMO_SOURCE_META[VER_PIECE_1]["sha256"],
                DEMO_SOURCE_META[VER_STUK_2]["sha256"],
            ]
        )
    )


DEMO_BUNDLE_SIGNATURE = _bundle_signature_for(DEMO_DRAFT_DOCX_SHA256)


def _default_inventory_entries() -> list[dict[str, Any]]:
    return [
        {
            "label": "piece",
            "number": "1",
            "source_version_id": VER_PIECE_1,
            "pages": [
                {
                    "space": "printed",
                    "label": "14",
                    "pdf_page": 16,
                    "rationale": "Bordereau printed page 14 corresponds to physical PDF page 16.",
                },
                {
                    "space": "bundle",
                    "label": "22",
                    "pdf_page": 16,
                    "rationale": "Bundle page 22 corresponds to physical PDF page 16.",
                },
            ],
        },
        {
            "label": "stuk",
            "number": "2",
            "source_version_id": VER_STUK_2,
            "pages": [],
        },
        {
            "label": "piece",
            "number": "3",
            "source_version_id": VER_PIECE_1,
            "pages": [
                {
                    "space": "printed",
                    "label": "1",
                    "pdf_page": 17,
                    "rationale": "Draft amendment (Pièce 3) appears on physical PDF page 17.",
                }
            ],
        },
    ]


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


def _preview(meta: dict[str, Any]) -> EvidencePreview:
    return EvidencePreview(
        EvidenceRow(
            source_id=meta["source_id"],
            document_id=meta["document_id"],
            version_id=meta["version_id"],
            original_sha256=meta["sha256"],
            media_type="application/pdf",
            status="ready",
            parser_id="synthetic-demo-v1",
            representation_id=f"repr-{meta['source_id']}",
            pages=(),
            warnings=(),
        ),
        meta["text"],
        meta["spans"],
    )


def _demo_previews() -> tuple[EvidencePreview, EvidencePreview]:
    return (
        _preview(DEMO_SOURCE_META[VER_PIECE_1]),
        _preview(DEMO_SOURCE_META[VER_STUK_2]),
    )


def _demo_intake_dict(
    *,
    brief_id: str = DEMO_BRIEF_ID,
    draft_sha256: str = DEMO_DRAFT_DOCX_SHA256,
    draft_byte_length: int = len(DEMO_DRAFT_DOCX_BYTES),
    confirmation_id: str | None,
    inventory_complete: bool,
    entries: list[dict[str, Any]] | None = None,
    exceptions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return canonical 4-source `caseproof-workspace-intake-v1` (1 draft, 1 inventory, 2 exhibits)."""
    return {
        "schema": "caseproof-workspace-intake-v1",
        "case_id": DEMO_CASE_ID,
        "brief_id": brief_id,
        "bundle_signature": _bundle_signature_for(draft_sha256),
        "confirmation_id": confirmation_id,
        "inventory_complete": inventory_complete,
        "readback_complete": True,
        "sources": [
            {
                "role": "draft",
                "filename": "conclusions-synthese-demo.docx",
                "document_id": DOC_DRAFT,
                "version_id": brief_id,
                "sha256": draft_sha256,
                "byte_length": draft_byte_length,
                "media_type": (
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                ),
                "processing": "text_extracted",
                "readback": "verified",
                "page_count": None,
            },
            {
                "role": "inventory",
                "filename": "bordereau-pieces-demo.txt",
                "document_id": DOC_INVENTORY,
                "version_id": VER_INVENTORY,
                "sha256": DEMO_INVENTORY_SHA256,
                "byte_length": len(DEMO_INVENTORY_BYTES),
                "media_type": "text/plain",
                "processing": "text_extracted",
                "readback": "verified",
                "page_count": None,
            },
            *[
                {
                    "role": "exhibit",
                    "filename": meta["filename"],
                    "document_id": meta["document_id"],
                    "version_id": meta["version_id"],
                    "sha256": meta["sha256"],
                    "byte_length": meta["byte_length"],
                    "media_type": "application/pdf",
                    "processing": "text_extracted",
                    "readback": "verified",
                    "page_count": meta["page_count"],
                }
                for meta in DEMO_SOURCE_META.values()
            ],
        ],
        "entries": entries if entries is not None else _default_inventory_entries(),
        "exceptions": exceptions if exceptions is not None else [],
    }


def build_five_trap_audit(
    *,
    confirmed_inventory: bool = False,
    fact_confirmed: bool = False,
    draft_text: str = DRAFT_TEXT,
    brief_id: str = DEMO_BRIEF_ID,
) -> dict[str, Any]:
    """Run real CaseProof deterministic checks over the synthetic 5-trap Belgian dossier."""
    previews = _demo_previews()
    intake = _demo_intake_dict(
        brief_id=brief_id,
        confirmation_id="conf-demo-001" if confirmed_inventory else None,
        inventory_complete=confirmed_inventory,
    )
    detected = detect_exhibit_references(draft_text, region="body")
    exhibit_report = map_exhibit_references(
        draft_text,
        brief_version_id=brief_id,
        intake=intake,
        previews=previews,
    )
    confirmed_exhibit_report = (
        exhibit_report
        if confirmed_inventory
        else map_exhibit_references(
            draft_text,
            brief_version_id=brief_id,
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
        else _omitted_reservation_cue(
            "le locataire peut céder son droit au bail", SOURCE_BAIL_TEXT
        )
    )

    claim_sentence = (
        "Le paiement de 12\u00a0500,00 EUR a été effectué selon l'extrait bancaire (Stuk 2)."
    )
    claim_start = draft_text.find(claim_sentence)
    if claim_start < 0:
        claim_start = 0
        claim_sentence = draft_text.splitlines()[-1] if draft_text.splitlines() else draft_text
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
        verified_brief_text=draft_text,
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
        "brief_id": brief_id,
        "snapshot_hash": _sha(f"{brief_id}:{draft_text}:{confirmed_inventory}:{fact_confirmed}"),
        "inventory_confirmed": confirmed_inventory,
        "identity_reason": None if confirmed_inventory else "INVENTORY_UNCONFIRMED",
        "detected_reference_count": len(detected),
        "exhibit_findings_count": len(exhibit_report["references"]),
        "traps": traps,
    }


def _build_demo_dossier(
    *,
    brief_id: str,
    draft_text: str,
    draft_sha256: str,
    draft_byte_length: int,
    snapshot_hash: str,
    confirmed_inventory: bool,
    literal_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a canonical `caseproof-dossier-v1` payload for the official React cockpit."""
    identity_state = "resolved" if confirmed_inventory else "not_assessed"
    identity_reason = None if confirmed_inventory else "INVENTORY_UNCONFIRMED"
    overrides = literal_overrides or {}
    m1 = DEMO_SOURCE_META[VER_PIECE_1]
    m2 = DEMO_SOURCE_META[VER_STUK_2]
    p1_literal = overrides.get("ref-piece-1", "Pièce 1, p. 14")
    p3_literal = overrides.get("ref-piece-3", "Pièce 3")
    s2_literal = overrides.get("ref-stuk-2", "Stuk 2")
    findings = [
        {
            "reference_id": "ref-piece-1",
            "literal": p1_literal,
            "identity": identity_state,
            "page_mapping": "mapped",
            "fidelity": "exact_match",
            "support": "not_assessed",
            "reason": identity_reason or "omitted_opening_reservation_appraisal_required",
            "quoted_text": "le locataire peut céder son droit au bail",
            "source_text_context": SOURCE_BAIL_TEXT.strip(),
            "source_text_context_partial": False,
            "version_id": m1["version_id"],
            "source_sha256": m1["sha256"],
            "pdf_page": 16,
            "page_spaces": {
                "pdf": {"state": "mapped", "value": 16},
                "printed": {"state": "mapped", "value": "14"},
                "bundle": {"state": "mapped", "value": "22"},
            },
            "visual_assessment": {"regions": []},
        },
        {
            "reference_id": "ref-piece-3",
            "literal": p3_literal,
            "identity": identity_state,
            "page_mapping": "mapped",
            "fidelity": "quote_not_found",
            "support": "not_assessed",
            "reason": identity_reason or "lexical_status_cue_appraisal_required",
            "quoted_text": "l'avenant a été signé le 14 mars 2026 par les deux parties",
            "source_text_context": SOURCE_AVENANT_TEXT.strip(),
            "source_text_context_partial": False,
            "version_id": m1["version_id"],
            "source_sha256": m1["sha256"],
            "pdf_page": 17,
            "page_spaces": {
                "pdf": {"state": "mapped", "value": 17},
                "printed": {"state": "mapped", "value": "1"},
                "bundle": {"state": "unmapped", "value": None},
            },
            "visual_assessment": {"regions": []},
        },
        {
            "reference_id": "ref-stuk-2",
            "literal": s2_literal,
            "identity": identity_state,
            "page_mapping": "mapped",
            "fidelity": "translation_review_required",
            "support": "not_assessed",
            "reason": identity_reason or "fr_nl_amount_difference_12500_vs_10000",
            "quoted_text": "Le paiement de 12\u00a0500,00 EUR a été effectué",
            "source_text_context": SOURCE_BANK_NL_TEXT.strip(),
            "source_text_context_partial": False,
            "version_id": m2["version_id"],
            "source_sha256": m2["sha256"],
            "pdf_page": 1,
            "page_spaces": {
                "pdf": {"state": "mapped", "value": 1},
                "printed": {"state": "unmapped", "value": None},
                "bundle": {"state": "unmapped", "value": None},
            },
            "visual_assessment": {"regions": []},
        },
    ]
    return {
        "schema": "caseproof-dossier-v1",
        "case_id": DEMO_CASE_ID,
        "brief_id": brief_id,
        "snapshot_hash": snapshot_hash,
        "findings": findings,
        "coverage": {
            "text_coverage_complete": True,
            "reference_recall_measured": False,
            "analysed_regions": ["body"],
            "unanalysed_regions": ["footnotes", "headers", "textboxes"],
            **_demo_coverage_counts(findings),
            "sources": [
                {
                    "role": "draft",
                    "version_id": brief_id,
                    "filename": "conclusions-synthese-demo.docx",
                    "sha256": draft_sha256,
                    "byte_length": draft_byte_length,
                },
                *[
                    {
                        "role": "exhibit",
                        "version_id": meta["version_id"],
                        "filename": meta["filename"],
                        "sha256": meta["sha256"],
                        "byte_length": meta["byte_length"],
                        "page_count": meta["page_count"],
                    }
                    for meta in DEMO_SOURCE_META.values()
                ],
            ],
        },
    }


def _demo_coverage_counts(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Numeric coverage denominators the official frontend reads (no invented values)."""
    ledger = [
        {
            "version_id": meta["version_id"],
            "original_sha256": meta["sha256"],
            "pdf_page": number,
            "method": "NOT_PROCESSED",
            "reason": "outside_assessed_reference_scope",
            "text_layer_present": True,
            "engine_versions": {},
        }
        for meta in DEMO_SOURCE_META.values()
        for number in range(1, int(meta["page_count"]) + 1)
    ]
    checked = sum(1 for f in findings if f.get("identity") == "resolved")
    return {
        "detected": len(findings),
        "checked": checked,
        "unresolved": len(findings) - checked,
        "unsupported_references": 0,
        "unprocessed_regions": 3,
        "inventory_exceptions_pending": 0,
        "visual_pages_completed": 0,
        "visual_findings_not_assessed": len(findings),
        "source_pages": ledger,
        "source_pages_known_total": len(ledger),
        "source_pages_total": len(ledger),
        "source_pages_ocr_processed": 0,
        "source_pages_failed_or_skipped": len(ledger),
    }


class DemoToggleBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    confirmed_inventory: bool | None = None
    fact_confirmed: bool | None = None


class OmissionBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    passage: str = Field(min_length=4, max_length=1000)
    rationale: str = Field(min_length=4, max_length=1000)


class VisualReviewBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    snapshot_hash: str
    reference_id: str
    decision: str
    rationale: str
    request_id: str
    reviewed_region_ids: list[str] = Field(default_factory=list)


class ClearbriefReviewCommandBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    snapshot_hash: str
    observation_id: str
    request_id: str
    expected_revision: int
    disposition: str
    rationale: str


class ConfirmationBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    request_id: str
    bundle_signature: str
    inventory_complete: bool
    entries: list[dict[str, Any]]
    exceptions: list[dict[str, Any]] = Field(default_factory=list)


class CheckCommandBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    require_confirmed_inventory: bool = True


class CorrectionPreviewBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    snapshot_hash: str
    original_sha256: str
    reference_id: str
    paragraph_index: int
    before: str
    after: str
    locator_identity: dict[str, Any] | None = None


class CorrectionCommitBody(CorrectionPreviewBody):
    request_id: str


class ReleaseCreateBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    release_id: str
    snapshot_hash: str
    release_type: str
    partial_acknowledged: bool = False
    release_acknowledged: bool = True
    acknowledgement_version: str = "caseproof-release-ack-v1"


def create_partner_demo_app(*, frontend_dist: Path | None = None) -> FastAPI:
    """Create the loopback-only FastAPI partner demo app."""
    app = FastAPI(title="CaseProof Belgian Partner Demo (Synthetic Loopback)")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "If-Match",
            "Idempotency-Key",
        ],
    )
    state: dict[str, Any] = {
        "current_brief_id": DEMO_BRIEF_ID,
        "briefs": {
            DEMO_BRIEF_ID: {
                "text": DRAFT_TEXT,
                "docx": DEMO_DRAFT_DOCX_BYTES,
                "sha256": DEMO_DRAFT_DOCX_SHA256,
                "literal_overrides": {},
            }
        },
        "confirmed_inventory": False,
        "inventory_complete": False,
        "confirmation_id": None,
        "entries": _default_inventory_entries(),
        "exceptions": [],
        "fact_confirmed": False,
        "omissions": [],
        "reviews_by_snapshot": {},
        "clearbrief_revision": 0,
        "clearbrief_decisions": [],
        "clearbrief_requests": set(),
        "snapshots": {},
        "latest_snapshot_by_brief": {},
        "reports_catalog": [],
        "correction_commits": {},
        "releases": {},
        "release_artifacts": {},
    }

    def _require_brief(case_id: str, brief_id: str) -> dict[str, Any]:
        if case_id != DEMO_CASE_ID or brief_id not in state["briefs"]:
            raise HTTPException(404, "unknown demo brief")
        return state["briefs"][brief_id]

    def _register_snapshot(brief_id: str, dossier: dict[str, Any]) -> None:
        snap = dossier["snapshot_hash"]
        state["snapshots"][snap] = dossier
        state["latest_snapshot_by_brief"][brief_id] = snap
        if not any(
            row["brief_id"] == brief_id and row["snapshot_hash"] == snap
            for row in state["reports_catalog"]
        ):
            state["reports_catalog"].insert(
                0,
                {
                    "brief_id": brief_id,
                    "snapshot_hash": snap,
                    "created_at": datetime.now(UTC).isoformat(),
                },
            )

    def _current_audit(brief_id: str | None = None) -> dict[str, Any]:
        target_brief = brief_id or state["current_brief_id"]
        brief = state["briefs"][target_brief]
        audit = build_five_trap_audit(
            confirmed_inventory=state["confirmed_inventory"],
            fact_confirmed=state["fact_confirmed"],
            draft_text=brief["text"],
            brief_id=target_brief,
        )
        audit["omissions"] = list(state["omissions"])
        snap = audit["snapshot_hash"]
        if snap not in state["snapshots"]:
            dossier = _build_demo_dossier(
                brief_id=target_brief,
                draft_text=brief["text"],
                draft_sha256=brief["sha256"],
                draft_byte_length=len(brief["docx"]),
                snapshot_hash=snap,
                confirmed_inventory=state["confirmed_inventory"],
                literal_overrides=brief["literal_overrides"],
            )
            _register_snapshot(target_brief, dossier)
        return audit

    def _dossier_for(brief_id: str, snapshot_hash: str | None) -> dict[str, Any]:
        audit = _current_audit(brief_id)
        target = snapshot_hash or audit["snapshot_hash"]
        if target in state["snapshots"]:
            return state["snapshots"][target]
        return state["snapshots"][audit["snapshot_hash"]]

    def _finding_for(brief_id: str, snapshot_hash: str, reference_id: str) -> dict[str, Any]:
        dossier = _dossier_for(brief_id, snapshot_hash)
        for row in dossier["findings"]:
            if row["reference_id"] == reference_id:
                return row
        raise HTTPException(404, "unknown demo reference")

    def _review_completeness(dossier: dict[str, Any]) -> dict[str, Any]:
        snap = dossier["snapshot_hash"]
        all_refs = [f["reference_id"] for f in dossier["findings"]]
        reviewed = {
            row["reference_id"] for row in state["reviews_by_snapshot"].get(snap, [])
        }
        unreviewed = [ref for ref in all_refs if ref not in reviewed]
        total = len(all_refs)
        reviewed_count = total - len(unreviewed)
        review_complete = total > 0 and len(unreviewed) == 0
        can_partial = reviewed_count > 0 and not review_complete
        return {
            "policy_version": "caseproof-release-completeness-v1",
            "total_findings": total,
            "required_reviews": total,
            "reviewed_findings": reviewed_count,
            "unreviewed_findings": len(unreviewed),
            "unreviewed_reference_ids": unreviewed,
            "review_complete": review_complete,
            "can_release_complete": review_complete,
            "can_release_partial": can_partial,
            "text_coverage_complete": True,
            "reference_recall_measured": False,
            "reason_codes": ["synthetic_demo_only"],
        }

    # Seed initial snapshot into reports catalog.
    _current_audit(DEMO_BRIEF_ID)

    @app.get("/v2/demo/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "synthetic_demo": True, "banner": DEMO_BANNER}

    @app.get("/v2/demo/five-trap-audit")
    def get_audit() -> dict[str, Any]:
        return _current_audit()

    @app.post("/v2/demo/five-trap-audit/state")
    def update_state(body: DemoToggleBody) -> dict[str, Any]:
        if body.confirmed_inventory is not None:
            state["confirmed_inventory"] = body.confirmed_inventory
            state["inventory_complete"] = body.confirmed_inventory
            state["confirmation_id"] = "conf-demo-001" if body.confirmed_inventory else None
        if body.fact_confirmed is not None:
            state["fact_confirmed"] = body.fact_confirmed
        return _current_audit()

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

    # --- Workspace Session (strictly matches frontend/src/shared/api/session.schema.json) ---

    @app.post("/v2/workspace/session")
    def demo_session() -> dict[str, Any]:
        return {
            "access_token": "synthetic-partner-demo-loopback-token",
            "expires_at": 4102444800,
        }

    @app.post("/v2/workspace/session/end", status_code=204)
    def demo_session_end() -> Response:
        return Response(status_code=204)

    # --- Matters, Organizations, Reports ---

    @app.get("/v2/workspace/intake/organizations")
    def demo_organizations() -> dict[str, Any]:
        return {
            "schema": "caseproof-workspace-create-orgs-v1",
            "organizations": [
                {
                    "org_id": DEMO_ORG_ID,
                    "name": "Cabinet Synthétique Démo (Bruxelles / Brussel)",
                }
            ],
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
    def demo_reports(
        case_id: str,
        after: str | None = Query(default=None),
    ) -> dict[str, Any]:
        if case_id != DEMO_CASE_ID:
            raise HTTPException(404, "unknown demo matter")
        _current_audit()
        # `frontend/src/shared/api/reports.ts` enforces strictly ascending
        # lexicographical order by `snapshot_hash` (unique hashes, cursor > after).
        unique_by_hash = {
            row["snapshot_hash"]: row for row in state["reports_catalog"]
        }
        ordered = [unique_by_hash[h] for h in sorted(unique_by_hash)]
        if after is not None:
            ordered = [row for row in ordered if row["snapshot_hash"] > after]
        page = ordered[:20]
        next_cursor = page[-1]["snapshot_hash"] if len(ordered) > 20 else None
        return ReportCatalogView.model_validate(
            {
                "schema": "caseproof-workspace-reports-v1",
                "case_id": DEMO_CASE_ID,
                "reports": page,
                "next_cursor": next_cursor,
            }
        ).model_dump(by_alias=True)

    # --- Intake, Inventory Confirmation & Explicit Check Execution ---

    @app.get("/v2/workspace/intake/matters/{case_id}")
    def demo_intake(case_id: str) -> dict[str, Any]:
        if case_id != DEMO_CASE_ID:
            raise HTTPException(404, "unknown demo matter")
        cur_id = state["current_brief_id"]
        brief = state["briefs"][cur_id]
        return _demo_intake_dict(
            brief_id=cur_id,
            draft_sha256=brief["sha256"],
            draft_byte_length=len(brief["docx"]),
            confirmation_id=state["confirmation_id"],
            inventory_complete=state["inventory_complete"],
            entries=state["entries"],
            exceptions=state["exceptions"],
        )

    @app.post("/v2/matters/{case_id}/briefs/{brief_id}/dossier/confirmation")
    def demo_confirm_inventory(
        case_id: str, brief_id: str, body: ConfirmationBody
    ) -> dict[str, Any]:
        brief = _require_brief(case_id, brief_id)
        expected_sig = _bundle_signature_for(brief["sha256"])
        if body.bundle_signature != expected_sig:
            raise HTTPException(409, "stale bundle signature")
        state["confirmation_id"] = body.request_id
        state["confirmed_inventory"] = True
        state["inventory_complete"] = body.inventory_complete
        state["entries"] = body.entries
        state["exceptions"] = body.exceptions
        _current_audit(brief_id)
        return {
            "confirmation_id": body.request_id,
            "inventory_complete": body.inventory_complete,
        }

    @app.post("/v2/matters/{case_id}/briefs/{brief_id}/dossier/checks")
    def demo_run_check(
        case_id: str,
        brief_id: str,
        body: CheckCommandBody | None = None,
    ) -> dict[str, Any]:
        _require_brief(case_id, brief_id)
        require_confirmed = True if body is None else body.require_confirmed_inventory
        if require_confirmed and not state["confirmed_inventory"]:
            raise HTTPException(409, "confirmed inventory required before explicit check")
        audit = _current_audit(brief_id)
        return state["snapshots"][audit["snapshot_hash"]]

    # --- Main Verification Cockpit (Dossier, History, Reviews, Viewer, Draft Context) ---

    @app.get("/v2/matters/{case_id}/briefs/{brief_id}/dossier")
    def demo_dossier(
        case_id: str,
        brief_id: str,
        snapshot_hash: str | None = Query(default=None),
    ) -> dict[str, Any]:
        _require_brief(case_id, brief_id)
        audit = _current_audit(brief_id)
        if snapshot_hash is not None and snapshot_hash != audit["snapshot_hash"]:
            raise HTTPException(409, "snapshot superseded; use historical read-only route")
        return state["snapshots"][audit["snapshot_hash"]]

    @app.get("/v2/matters/{case_id}/briefs/{brief_id}/dossier/history/{snapshot_hash}")
    def demo_dossier_history(
        case_id: str, brief_id: str, snapshot_hash: str
    ) -> dict[str, Any]:
        _require_brief(case_id, brief_id)
        dossier = state["snapshots"].get(snapshot_hash)
        if dossier is None:
            raise HTTPException(404, "unknown demo snapshot")
        return {
            "mode": "historical_read_only",
            "currentness": "not_asserted",
            "source_availability": "not_assessed",
            "report": dossier,
        }

    @app.get(
        "/v2/matters/{case_id}/briefs/{brief_id}/dossier/history/{snapshot_hash}/comparison"
    )
    def demo_history_comparison(
        case_id: str,
        brief_id: str,
        snapshot_hash: str,
        current_brief_id: str = Query(...),
        current_snapshot_hash: str = Query(...),
    ) -> dict[str, Any]:
        _require_brief(case_id, brief_id)
        old = state["snapshots"].get(snapshot_hash)
        current = state["snapshots"].get(current_snapshot_hash)
        if old is None or current is None:
            raise HTTPException(409, "comparison unavailable")
        old_by_id = {f["reference_id"]: f for f in old["findings"]}
        cur_by_id = {f["reference_id"]: f for f in current["findings"]}
        rows = []
        for ref_id, cur in cur_by_id.items():
            prev = old_by_id.get(ref_id)
            if prev is None:
                rows.append(
                    {
                        "previous_reference_id": None,
                        "current_reference_id": ref_id,
                        "status": "added",
                        "reasons": ["added_in_revised_draft"],
                        "review_transfer": "never",
                    }
                )
            elif prev["literal"] != cur["literal"]:
                rows.append(
                    {
                        "previous_reference_id": ref_id,
                        "current_reference_id": ref_id,
                        "status": "changed",
                        "reasons": ["literal_changed_recheck_required"],
                        "review_transfer": "never",
                    }
                )
            else:
                rows.append(
                    {
                        "previous_reference_id": ref_id,
                        "current_reference_id": ref_id,
                        "status": "unchanged",
                        "reasons": ["literal_unchanged_human_review_not_auto_transferred"],
                        "review_transfer": "never",
                    }
                )
        return {
            "schema": "caseproof-finding-drift-v1",
            "case_id": DEMO_CASE_ID,
            "previous_brief_id": brief_id,
            "previous_snapshot_hash": snapshot_hash,
            "current_brief_id": current_brief_id,
            "current_snapshot_hash": current_snapshot_hash,
            "correspondence_basis": "unique_region_and_start_offset_candidate_not_identity_proof",
            "review_transfer": "never",
            "rows": rows,
        }

    @app.get("/v2/matters/{case_id}/briefs/{brief_id}/dossier/reviews")
    def demo_reviews(
        case_id: str,
        brief_id: str,
        snapshot_hash: str | None = Query(default=None),
    ) -> dict[str, Any]:
        _require_brief(case_id, brief_id)
        audit = _current_audit(brief_id)
        snap = snapshot_hash or audit["snapshot_hash"]
        decisions = list(state["reviews_by_snapshot"].get(snap, []))
        return ReviewLedgerView.model_validate(
            {
                "schema": "caseproof-review-ledger-v1",
                "case_id": DEMO_CASE_ID,
                "brief_id": brief_id,
                "snapshot_hash": snap,
                "decisions": decisions,
            }
        ).model_dump(by_alias=True)

    @app.post("/v2/matters/{case_id}/briefs/{brief_id}/dossier/reviews")
    def demo_record_review(
        case_id: str, brief_id: str, body: VisualReviewBody
    ) -> dict[str, Any]:
        _require_brief(case_id, brief_id)
        rows = state["reviews_by_snapshot"].setdefault(body.snapshot_hash, [])
        if not any(r["request_id"] == body.request_id for r in rows):
            rows.append(
                {
                    "reference_id": body.reference_id,
                    "decision": body.decision,
                    "rationale": body.rationale,
                    "reviewer_id": DEMO_ACTOR_EMAIL,
                    "request_id": body.request_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "reviewed_region_ids": list(body.reviewed_region_ids),
                }
            )
        return {
            "request_id": body.request_id,
            "reference_id": body.reference_id,
            "decision": body.decision,
            "reviewer_id": DEMO_ACTOR_EMAIL,
        }

    def _viewer_payload(brief_id: str, snapshot_hash: str, reference_id: str) -> dict[str, Any]:
        finding = _finding_for(brief_id, snapshot_hash, reference_id)
        meta = DEMO_SOURCE_META[finding["version_id"]]
        return {
            "schema": "caseproof-viewer-v1",
            "case_id": DEMO_CASE_ID,
            "brief_id": brief_id,
            "snapshot_hash": snapshot_hash,
            "reference_id": reference_id,
            "version_id": meta["version_id"],
            "original_sha256": meta["sha256"],
            "byte_length": meta["byte_length"],
            "page_mapping": finding["page_mapping"],
            "pdf_page": finding["pdf_page"],
            "legacy_region_count": 0,
            "geometry_policy": "derived_pdf_text_only_legacy_raster_not_projected",
        }

    def _viewer_original_response(
        brief_id: str, snapshot_hash: str, reference_id: str
    ) -> Response:
        finding = _finding_for(brief_id, snapshot_hash, reference_id)
        version_id = finding["version_id"]
        filename, pdf_bytes = DEMO_PDF_SOURCES[version_id]
        digest = _sha_bytes(pdf_bytes)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "X-CaseProof-Snapshot": snapshot_hash,
                "X-CaseProof-Original-SHA256": digest,
                "X-Content-SHA256": digest,
                "Cache-Control": "no-store",
            },
        )

    def _viewer_regions_payload(
        brief_id: str, snapshot_hash: str, reference_id: str
    ) -> dict[str, Any]:
        finding = _finding_for(brief_id, snapshot_hash, reference_id)
        meta = DEMO_SOURCE_META[finding["version_id"]]
        return {
            "schema": "caseproof-raster-overlays-v1",
            "snapshot_hash": snapshot_hash,
            "original_sha256": meta["sha256"],
            "source_version_id": meta["version_id"],
            "interpretation": "navigation_only_never_a_verdict",
            "regions": [],
            "unassessed_region_count": 0,
        }

    @app.get(
        "/v2/matters/{case_id}/briefs/{brief_id}/dossier/snapshots/{snapshot_hash}"
        "/references/{reference_id}/viewer"
    )
    @app.get(
        "/v2/matters/{case_id}/briefs/{brief_id}/dossier/history/{snapshot_hash}"
        "/references/{reference_id}/viewer"
    )
    def demo_viewer(
        case_id: str, brief_id: str, snapshot_hash: str, reference_id: str
    ) -> dict[str, Any]:
        _require_brief(case_id, brief_id)
        return _viewer_payload(brief_id, snapshot_hash, reference_id)

    @app.get(
        "/v2/matters/{case_id}/briefs/{brief_id}/dossier/snapshots/{snapshot_hash}"
        "/references/{reference_id}/viewer/original"
    )
    @app.get(
        "/v2/matters/{case_id}/briefs/{brief_id}/dossier/history/{snapshot_hash}"
        "/references/{reference_id}/viewer/original"
    )
    def demo_viewer_original(
        case_id: str, brief_id: str, snapshot_hash: str, reference_id: str
    ) -> Response:
        _require_brief(case_id, brief_id)
        return _viewer_original_response(brief_id, snapshot_hash, reference_id)

    @app.get(
        "/v2/matters/{case_id}/briefs/{brief_id}/dossier/snapshots/{snapshot_hash}"
        "/references/{reference_id}/viewer/regions"
    )
    @app.get(
        "/v2/matters/{case_id}/briefs/{brief_id}/dossier/history/{snapshot_hash}"
        "/references/{reference_id}/viewer/regions"
    )
    def demo_viewer_regions(
        case_id: str, brief_id: str, snapshot_hash: str, reference_id: str
    ) -> dict[str, Any]:
        _require_brief(case_id, brief_id)
        return _viewer_regions_payload(brief_id, snapshot_hash, reference_id)

    @app.get(
        "/v2/matters/{case_id}/briefs/{brief_id}/dossier/snapshots/{snapshot_hash}"
        "/references/{reference_id}/draft-context"
    )
    def demo_draft_context(
        case_id: str, brief_id: str, snapshot_hash: str, reference_id: str
    ) -> dict[str, Any]:
        brief = _require_brief(case_id, brief_id)
        finding = _finding_for(brief_id, snapshot_hash, reference_id)
        literal = finding["literal"]
        text = brief["text"]
        idx = text.find(literal)
        if idx < 0:
            payload = {
                "schema": "caseproof-draft-excerpt-v1",
                "case_id": DEMO_CASE_ID,
                "brief_id": brief_id,
                "snapshot_hash": snapshot_hash,
                "reference_id": reference_id,
                "original_sha256": brief["sha256"],
                "available": False,
                "region": None,
                "excerpt": "",
                "selection_start": 0,
                "selection_end": 0,
                "reason": "unsupported_or_ambiguous_anchor",
            }
        else:
            payload = {
                "schema": "caseproof-draft-excerpt-v1",
                "case_id": DEMO_CASE_ID,
                "brief_id": brief_id,
                "snapshot_hash": snapshot_hash,
                "reference_id": reference_id,
                "original_sha256": brief["sha256"],
                "available": True,
                "region": "body",
                "excerpt": text,
                "selection_start": idx,
                "selection_end": idx + len(literal),
                "reason": None,
            }
        return DraftExcerptView.model_validate(payload).model_dump(by_alias=True)

    # --- Corrections (Anchor, Review Receipt, Preview, Commit, Recheck) ---

    @app.get(
        "/v2/matters/{case_id}/briefs/{brief_id}/dossier/snapshots/{snapshot_hash}"
        "/references/{reference_id}/correction-operations"
    )
    def demo_correction_operations(
        case_id: str, brief_id: str, snapshot_hash: str, reference_id: str
    ) -> dict[str, Any]:
        _require_brief(case_id, brief_id)
        _finding_for(brief_id, snapshot_hash, reference_id)
        return {
            "operations": [],
            "current_draft_version_id": state["current_brief_id"],
        }

    @app.get(
        "/v2/matters/{case_id}/briefs/{brief_id}/dossier/snapshots/{snapshot_hash}"
        "/references/{reference_id}/correction-anchor"
    )
    def demo_correction_anchor(
        case_id: str, brief_id: str, snapshot_hash: str, reference_id: str
    ) -> dict[str, Any]:
        brief = _require_brief(case_id, brief_id)
        finding = _finding_for(brief_id, snapshot_hash, reference_id)
        literal = finding["literal"]
        lines = [line for line in brief["text"].splitlines() if line]
        for p_idx, line in enumerate(lines):
            pos = line.find(literal)
            if pos >= 0:
                return {
                    "snapshot_hash": snapshot_hash,
                    "brief_version_id": brief_id,
                    "reference_id": reference_id,
                    "original_sha256": brief["sha256"],
                    "before": literal,
                    "paragraph_index": p_idx,
                    "locator_identity": {
                        "exact_text": literal,
                        "prefix": line[:pos],
                        "suffix": line[pos + len(literal) :],
                        "occurrence_index": 0,
                        "content_hash": _sha(line),
                        "source_version_id": brief_id,
                        "paragraph_id": None,
                    },
                }
        raise HTTPException(409, "correction anchor unavailable")

    @app.get("/v2/matters/{case_id}/briefs/{brief_id}/dossier/corrections/review-receipt")
    def demo_correction_review_receipt(
        case_id: str,
        brief_id: str,
        snapshot_hash: str = Query(...),
        reference_id: str = Query(...),
    ) -> dict[str, Any]:
        _require_brief(case_id, brief_id)
        matching = [
            row
            for row in state["reviews_by_snapshot"].get(snapshot_hash, [])
            if row["reference_id"] == reference_id
        ]
        if not matching:
            raise HTTPException(409, "persisted actor review required before correction")
        return {
            "schema": "caseproof-correction-review-receipt-v1",
            "brief_version_id": brief_id,
            "snapshot_hash": snapshot_hash,
            "reference_id": reference_id,
            "reviewer_id": DEMO_ACTOR_ID,
            "review_request_id": matching[-1]["request_id"],
        }

    @app.post("/v2/matters/{case_id}/briefs/{brief_id}/dossier/corrections/preview")
    def demo_correction_preview(
        case_id: str, brief_id: str, body: CorrectionPreviewBody
    ) -> dict[str, Any]:
        brief = _require_brief(case_id, brief_id)
        if body.original_sha256 != brief["sha256"] or body.before not in brief["text"]:
            raise HTTPException(409, "draft changed or anchor not found")
        new_text = brief["text"].replace(body.before, body.after, 1)
        deriv = _minimal_docx_bytes(new_text)
        return {
            "schema": "caseproof-docx-correction-preview-v1",
            "committed": False,
            "requires_recheck": True,
            "original_sha256": body.original_sha256,
            "derivative_sha256": _sha_bytes(deriv),
            "derivative_byte_length": len(deriv),
            "reference_id": body.reference_id,
            "paragraph_index": body.paragraph_index,
            "before": body.before,
            "after": body.after,
            "brief_version_id": brief_id,
            "snapshot_hash": body.snapshot_hash,
        }

    @app.post("/v2/matters/{case_id}/briefs/{brief_id}/dossier/corrections/commit")
    def demo_correction_commit(
        case_id: str, brief_id: str, body: CorrectionCommitBody
    ) -> dict[str, Any]:
        brief = _require_brief(case_id, brief_id)
        existing = state["correction_commits"].get(body.request_id)
        if existing is not None:
            return existing
        if body.original_sha256 != brief["sha256"] or body.before not in brief["text"]:
            raise HTTPException(409, "draft changed or anchor not found")
        new_text = brief["text"].replace(body.before, body.after, 1)
        new_docx = _minimal_docx_bytes(new_text)
        new_brief_id = str(uuid.uuid4())
        overrides = dict(brief["literal_overrides"])
        overrides[body.reference_id] = body.after
        state["briefs"][new_brief_id] = {
            "text": new_text,
            "docx": new_docx,
            "sha256": _sha_bytes(new_docx),
            "literal_overrides": overrides,
        }
        state["current_brief_id"] = new_brief_id
        receipt = {
            "state": "active",
            "version_id": new_brief_id,
            "committed": True,
            "requires_recheck": True,
        }
        state["correction_commits"][body.request_id] = receipt
        return receipt

    @app.post("/v2/matters/{case_id}/briefs/{brief_id}/dossier/recheck")
    def demo_recheck(case_id: str, brief_id: str) -> dict[str, Any]:
        _require_brief(case_id, brief_id)
        audit = _current_audit(brief_id)
        return state["snapshots"][audit["snapshot_hash"]]

    # --- Legal, Exhibits, Reservation Cues, Conditions & Clearbrief Review ---

    @app.get("/v2/matters/{case_id}/briefs/{brief_id}/exhibit-references")
    def demo_exhibit_references(case_id: str, brief_id: str) -> dict[str, Any]:
        brief = _require_brief(case_id, brief_id)
        previews = _demo_previews()
        intake = _demo_intake_dict(
            brief_id=brief_id,
            draft_sha256=brief["sha256"],
            draft_byte_length=len(brief["docx"]),
            confirmation_id=state["confirmation_id"],
            inventory_complete=state["inventory_complete"],
            entries=state["entries"],
            exceptions=state["exceptions"],
        )
        mapped = map_exhibit_references(
            brief["text"],
            brief_version_id=brief_id,
            intake=intake,
            previews=previews,
        )
        audit = _current_audit(brief_id)
        return ExhibitReferencesView.model_validate(
            {
                "schema": "caseproof-exhibit-references-v1",
                "brief_version_id": brief_id,
                "snapshot_hash": audit["snapshot_hash"],
                "note": "SYNTHETIC DEMO: located never means content verified.",
                **mapped,
            }
        ).model_dump(by_alias=True)

    @app.get("/v2/matters/{case_id}/briefs/{brief_id}/legal-references")
    def demo_legal_references(case_id: str, brief_id: str) -> dict[str, Any]:
        brief = _require_brief(case_id, brief_id)
        audit = _current_audit(brief_id)
        cite = "art. 1732 Code civil (version 1991)"
        start = max(0, brief["text"].find(cite))
        return LegalReferencesView.model_validate(
            {
                "schema": "caseproof-legal-references-v1",
                "brief_version_id": brief_id,
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

    @app.get("/v2/matters/{case_id}/briefs/{brief_id}/legal-references/{reference_id}/passage")
    def demo_legal_passage(
        case_id: str, brief_id: str, reference_id: str
    ) -> dict[str, Any]:
        _require_brief(case_id, brief_id)
        if reference_id != "legal-ref-01":
            raise HTTPException(404, "unknown demo legal reference")
        audit = _current_audit(brief_id)
        excerpt = (
            "3. Conformément à l'art. 1732 Code civil (version 1991), la responsabilité est engagée."
        )
        cite = "art. 1732 Code civil (version 1991)"
        start = excerpt.index(cite)
        return LegalPassageView.model_validate(
            {
                "schema": "caseproof-legal-passage-v1",
                "observation_id": f"legal:{reference_id}",
                "snapshot_hash": audit["snapshot_hash"],
                "brief_excerpt": excerpt,
                "citation_span": [start, start + len(cite)],
                "quote": None,
                "quote_span": None,
                "other_findings": [],
                "status": "UNVERIFIED",
                "reason": "requested_version_absent_from_chosen_corpus",
                "article_text": None,
                "corpus_key": None,
                "corpus_version": None,
                "corpus_text_sha256": None,
                "corpus_source_uri": None,
                "note": (
                    "Version 1991 is absent from the pinned 2024 synthetic corpus. "
                    "CaseProof fails closed (UNVERIFIED) rather than substituting a newer version."
                ),
            }
        ).model_dump(by_alias=True)

    @app.get("/v2/matters/{case_id}/briefs/{brief_id}/reservation-cues")
    def demo_reservation_cues(case_id: str, brief_id: str) -> dict[str, Any]:
        _require_brief(case_id, brief_id)
        audit = _current_audit(brief_id)
        return {
            "schema": "caseproof-reservation-cues-v1",
            "rules": "belgian-reservation-cues-v1",
            "advisory": True,
            "note": "Advisory literal cues only; never alters a legal reference status.",
            "snapshot_hash": audit["snapshot_hash"],
            "brief_version_id": brief_id,
            "rows": [],
        }

    @app.get("/v2/matters/{case_id}/conditions")
    def demo_conditions_state(case_id: str) -> dict[str, Any]:
        if case_id != DEMO_CASE_ID:
            raise HTTPException(404, "unknown demo matter")
        spec_sha = _sha(CONDITION_RULE_TOML)
        return ConditionsStateView.model_validate(
            {
                "schema": "caseproof-conditions-state-v1",
                "revision": 1,
                "spec_sha256": spec_sha,
                "conditions": [
                    {
                        "id": "demo-bail-notification-conge",
                        "label": "Notification écrite du congé commercial",
                        "question": (
                            "Le congé commercial a-t-il été notifié par pli recommandé "
                            "conformément à la clause de bail ?"
                        ),
                        "trigger": ["bail commercial", "céder son droit au bail"],
                        "evidence": ["accord écrit du bailleur", "recommandé"],
                        "pieces": ["Pièce 1"],
                    }
                ],
                "note": "SYNTHETIC DEMO: lawyer-defined routing conditions, never legal advice.",
            }
        ).model_dump(by_alias=True)

    @app.get("/v2/matters/{case_id}/briefs/{brief_id}/conditions")
    def demo_condition_matches(case_id: str, brief_id: str) -> dict[str, Any]:
        brief = _require_brief(case_id, brief_id)
        first_line = brief["text"].splitlines()[0]
        start = brief["text"].find(first_line)
        m1 = DEMO_SOURCE_META[VER_PIECE_1]
        excerpt = (
            "Sous réserve de l'accord écrit du bailleur, "
            "le locataire peut céder son droit au bail."
        )
        return ConditionMatchesView.model_validate(
            {
                "schema": "caseproof-condition-matches-v1",
                "brief_version_id": brief_id,
                "revision": 1,
                "spec_sha256": _sha(CONDITION_RULE_TOML),
                "scope": "SYNTHETIC DEMO: literal keyword routing only — lawyer decides.",
                "anchors": [
                    {
                        "anchor_id": "condition-anchor-01",
                        "condition_id": "demo-bail-notification-conge",
                        "label": "Notification écrite du congé commercial",
                        "question": (
                            "Le congé commercial a-t-il été notifié par pli recommandé "
                            "conformément à la clause de bail ?"
                        ),
                        "start": start,
                        "end": start + len(first_line),
                        "sentence": first_line,
                        "status": "UNDETERMINED",
                        "reason": "condition_passages_found_appraisal_required",
                        "found": [
                            {
                                "piece": "Pièce 1",
                                "source_id": m1["source_id"],
                                "version_id": m1["version_id"],
                                "original_sha256": m1["sha256"],
                                "term": "accord écrit du bailleur",
                                "excerpt": excerpt,
                                "excerpt_sha256": _sha(excerpt),
                                "pdf_page": 16,
                            }
                        ],
                        "pieces_read": ["Pièce 1"],
                        "pieces_not_read": [],
                    }
                ],
                "coverage": {
                    "conditions": 1,
                    "anchors": 1,
                    "sources_read": 2,
                    "sources_not_read": 0,
                    "by_status": {"UNDETERMINED": 1, "UNVERIFIED": 0},
                },
            }
        ).model_dump(by_alias=True)

    @app.get("/v2/matters/{case_id}/briefs/{brief_id}/review")
    def demo_clearbrief_review_state(case_id: str, brief_id: str) -> dict[str, Any]:
        _require_brief(case_id, brief_id)
        audit = _current_audit(brief_id)
        return ClearbriefReviewState.model_validate(
            {
                "schema": "caseproof-clearbrief-review-v1",
                "case_id": DEMO_CASE_ID,
                "brief_version_id": brief_id,
                "snapshot_hash": audit["snapshot_hash"],
                "revision": state["clearbrief_revision"],
                "decisions": list(state["clearbrief_decisions"]),
                "blocker_inventory": {
                    "schema": "caseproof-blocker-inventory-v1",
                    "snapshot_hash": audit["snapshot_hash"],
                    "items": [
                        {
                            "observation_id": "legal:legal-ref-01",
                            "reason": "requested_version_absent_from_chosen_corpus",
                            "review_disposition": "unreviewed",
                        }
                    ],
                    "verdict": "not_computed",
                    "release_authorized": False,
                    "waiver_policy": "not_decided",
                    "note": "Open items only; never readiness or permission to file.",
                },
                "release_authorized": False,
            }
        ).model_dump(by_alias=True)

    @app.post("/v2/matters/{case_id}/briefs/{brief_id}/review")
    def demo_clearbrief_review_record(
        case_id: str, brief_id: str, body: ClearbriefReviewCommandBody
    ) -> dict[str, Any]:
        _require_brief(case_id, brief_id)
        audit = _current_audit(brief_id)
        if body.snapshot_hash != audit["snapshot_hash"]:
            raise HTTPException(409, "stale snapshot_hash")
        replayed = body.request_id in state["clearbrief_requests"]
        if not replayed:
            if body.expected_revision != state["clearbrief_revision"]:
                raise HTTPException(409, "stale review revision")
            state["clearbrief_requests"].add(body.request_id)
            state["clearbrief_revision"] += 1
            state["clearbrief_decisions"].append(
                {
                    "observation_id": body.observation_id,
                    "actor_id": DEMO_ACTOR_EMAIL,
                    "disposition": body.disposition,
                    "rationale": body.rationale.strip(),
                }
            )
        return ClearbriefReviewReceipt.model_validate(
            {
                "schema": "caseproof-clearbrief-review-receipt-v1",
                "snapshot_hash": audit["snapshot_hash"],
                "revision": state["clearbrief_revision"],
                "replayed": replayed,
                "release_authorized": False,
            }
        ).model_dump(by_alias=True)

    # --- Exports Preview, Release Commit, Status & Artifact Download ---

    @app.get("/v2/matters/{case_id}/briefs/{brief_id}/dossier/releases")
    def demo_releases(case_id: str, brief_id: str) -> dict[str, Any]:
        _require_brief(case_id, brief_id)
        items = [r for r in state["releases"].values() if r["brief_id"] == brief_id]
        return {"releases": items}

    @app.get("/v2/matters/{case_id}/briefs/{brief_id}/dossier/releases/preview")
    def demo_releases_preview(
        case_id: str,
        brief_id: str,
        snapshot_hash: str | None = Query(default=None),
    ) -> dict[str, Any]:
        _require_brief(case_id, brief_id)
        dossier = _dossier_for(brief_id, snapshot_hash)
        comp = _review_completeness(dossier)
        return {
            "schema": "caseproof-release-preview-v1",
            "case_id": DEMO_CASE_ID,
            "brief_id": brief_id,
            "snapshot_hash": dossier["snapshot_hash"],
            "finding_count": comp["total_findings"],
            "review_count": comp["reviewed_findings"],
            "release_ready": comp["can_release_complete"],
            "can_release": comp["can_release_complete"] or comp["can_release_partial"],
            "review_completeness": comp,
            "formats": ["json", "markdown", "docx"],
            "release_actor": {
                "actor_id": DEMO_ACTOR_ID,
                "actor_label": DEMO_ACTOR_EMAIL,
                "actor_label_type": "confirmed_email",
            },
            "acknowledgement_version": "caseproof-release-ack-v1",
            "acknowledgement_notice": (
                "Synthetic demo preview: authorizes an immutable CaseProof review record only; "
                "not legal validation, not a qualified signature, not a constat d'huissier."
            ),
            "coverage": dossier["coverage"],
            "limitations": [
                "Synthetic partner demo only — no client data, not legal validation or filing clearance."
            ],
        }

    @app.post("/v2/matters/{case_id}/briefs/{brief_id}/dossier/releases")
    def demo_create_release(
        case_id: str, brief_id: str, body: ReleaseCreateBody
    ) -> dict[str, Any]:
        brief = _require_brief(case_id, brief_id)
        existing = state["releases"].get(body.release_id)
        if existing is not None:
            return existing
        dossier = _dossier_for(brief_id, body.snapshot_hash)
        snap = dossier["snapshot_hash"]
        comp = _review_completeness(dossier)
        if comp["reviewed_findings"] < 1:
            raise HTTPException(409, "at least one human review decision required before release")
        if body.release_type == "complete_review" and not comp["can_release_complete"]:
            raise HTTPException(409, "complete review required")
        if body.release_type == "partial_review" and not (
            comp["can_release_partial"] and body.partial_acknowledged
        ):
            raise HTTPException(409, "partial acknowledgement required")

        now_iso = datetime.now(UTC).isoformat()
        reviews = list(state["reviews_by_snapshot"].get(snap, []))
        release_scope = {
            **comp,
            "release_type": body.release_type,
            "partial_acknowledged": (
                body.release_type == "partial_review" and body.partial_acknowledged
            ),
        }
        release_ack = {
            "schema": "caseproof-release-ack-v1",
            "intent": "AUTHORIZE_REVIEW_RECORD_RELEASE",
            "release_id": body.release_id,
            "snapshot_hash": snap,
            "release_type": body.release_type,
            "actor_id": DEMO_ACTOR_ID,
            "actor_label": DEMO_ACTOR_EMAIL,
            "actor_label_type": "confirmed_email",
            "acknowledged_at": now_iso,
            "notice": (
                "Synthetic demo release: immutable CaseProof review record only; "
                "not a qualified signature or constat d'huissier."
            ),
        }
        frozen_report = {
            "case_id": DEMO_CASE_ID,
            "brief_id": brief_id,
            "snapshot_hash": snap,
            "bundle_signature": _bundle_signature_for(brief["sha256"]),
            "confirmation_id": state["confirmation_id"],
            "coverage": dossier["coverage"],
            "verification_contract": {
                "scope": "synthetic_belgian_partner_demo",
                "llm_in_verdict_path": False,
                "legal_certification": False,
            },
            "abstentions": [
                {
                    "reason": "automated_legal_support_never_assessed",
                    "note": "Human lawyer inspection is required for semantic support.",
                }
            ],
            "findings": dossier["findings"],
            "human_decisions": reviews,
            "review_completeness": release_scope,
            "release_acknowledgement": release_ack,
        }
        json_bytes = json.dumps(
            {
                "schema": "caseproof-demo-export-v1",
                "release_id": body.release_id,
                **frozen_report,
                "notice": "Synthetic demo export — not a qualified signature or constat d'huissier.",
            },
            sort_keys=True,
            indent=2,
        ).encode("utf-8")
        md_bytes = (
            f"# CaseProof Synthetic Review Record\n\n"
            f"- Matter: `{DEMO_CASE_ID}`\n"
            f"- Brief: `{brief_id}`\n"
            f"- Snapshot: `{snap}`\n"
            f"- Reviewed findings: {comp['reviewed_findings']}/{comp['total_findings']}\n\n"
            f"## Draft Excerpt\n\n{brief['text']}\n\n"
            f"> Not legal validation, not a qualified signature, not a constat d'huissier.\n"
        ).encode()
        # Use the real CaseProof `annotated_docx()` derivative builder so the
        # exported DOCX preserves the full draft text and appends scoped findings,
        # human review decisions, coverage, and release provenance annotations.
        docx_bytes = annotated_docx(brief["docx"], frozen_report)
        artifacts_raw = {"json": json_bytes, "markdown": md_bytes, "docx": docx_bytes}
        state["release_artifacts"][body.release_id] = artifacts_raw

        sources = [
            {"role": "draft", "version_id": brief_id, "sha256": brief["sha256"]},
            *[
                {
                    "role": "exhibit",
                    "version_id": meta["version_id"],
                    "sha256": meta["sha256"],
                }
                for meta in DEMO_SOURCE_META.values()
            ],
        ]
        source_links = [
            {
                "role": s["role"],
                "version_id": s["version_id"],
                "sha256": s["sha256"],
                "original_path": (
                    f"/v2/matters/{DEMO_CASE_ID}/briefs/{brief_id}"
                    f"/dossier/history/{snap}/sources/{s['version_id']}/original"
                ),
            }
            for s in sources
        ]
        reference_links = [
            {
                "reference_id": f["reference_id"],
                "source_version_id": f["version_id"],
                "original_sha256": f["source_sha256"],
                "pdf_page": f["pdf_page"],
                "viewer_path": (
                    f"/matters/{DEMO_CASE_ID}/briefs/{brief_id}"
                    f"?snapshot={snap}&finding={f['reference_id']}"
                ),
                "page_space": "unmapped" if f["pdf_page"] is None else "physical_pdf_page",
            }
            for f in dossier["findings"]
        ]
        manifest_core: dict[str, Any] = {
            "schema": "caseproof-reviewed-release-v1",
            "release_id": body.release_id,
            "case_id": DEMO_CASE_ID,
            "brief_id": brief_id,
            "snapshot_hash": snap,
            "review_count": comp["reviewed_findings"],
            "finding_count": comp["total_findings"],
            "release_acknowledgement": release_ack,
            "reviewer_ids": [DEMO_ACTOR_EMAIL],
            "review_completeness": release_scope,
            "coverage": dossier["coverage"],
            "sources": sources,
            "source_links": source_links,
            "reference_links": reference_links,
            "limitations": [
                "Synthetic partner demo only — not legal validation or a qualified signature."
            ],
            "artifacts": {
                "json": {
                    "sha256": _sha_bytes(json_bytes),
                    "byte_length": len(json_bytes),
                    "media_type": "application/json",
                },
                "markdown": {
                    "sha256": _sha_bytes(md_bytes),
                    "byte_length": len(md_bytes),
                    "media_type": "text/markdown; charset=utf-8",
                },
                "docx": {
                    "sha256": _sha_bytes(docx_bytes),
                    "byte_length": len(docx_bytes),
                    "media_type": (
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    ),
                },
            },
        }
        canonical_manifest = json.dumps(manifest_core, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        manifest_sha = _sha_bytes(canonical_manifest)
        server_receipt = hmac.new(DEMO_HMAC_KEY, canonical_manifest, hashlib.sha256).hexdigest()
        manifest = {
            **manifest_core,
            "manifest_sha256": manifest_sha,
            "server_receipt": server_receipt,
        }
        record = {
            "state": "released",
            "release_id": body.release_id,
            "brief_id": brief_id,
            "snapshot_hash": snap,
            "manifest": manifest,
            "created_at": now_iso,
        }
        state["releases"][body.release_id] = record
        return record

    @app.get("/v2/matters/{case_id}/briefs/{brief_id}/dossier/releases/{release_id}")
    def demo_release_status(case_id: str, brief_id: str, release_id: str) -> dict[str, Any]:
        _require_brief(case_id, brief_id)
        record = state["releases"].get(release_id)
        if record is None:
            return {"state": "absent"}
        return record

    @app.get(
        "/v2/matters/{case_id}/briefs/{brief_id}/dossier/releases/{release_id}/artifacts/{fmt}"
    )
    def demo_release_artifact(
        case_id: str, brief_id: str, release_id: str, fmt: str
    ) -> Response:
        _require_brief(case_id, brief_id)
        record = state["releases"].get(release_id)
        raw_map = state["release_artifacts"].get(release_id)
        if record is None or raw_map is None or fmt not in raw_map:
            raise HTTPException(404, "unknown release artifact")
        data = raw_map[fmt]
        media = {
            "json": "application/json",
            "markdown": "text/markdown; charset=utf-8",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }[fmt]
        digest = _sha_bytes(data)
        return Response(
            content=data,
            media_type=media,
            headers={
                "Content-Disposition": f'attachment; filename="caseproof-demo-release.{fmt}"',
                "X-CaseProof-Snapshot": record["snapshot_hash"],
                "X-CaseProof-Export-SHA256": digest,
                "X-CaseProof-Export-Size": str(len(data)),
                "Cache-Control": "no-store",
            },
        )

    # --- Scoped DOCX Editor read endpoints ---

    @app.get("/v2/matters/{case_id}/briefs/{brief_id}/dossier/editor/blocks")
    def demo_editor_blocks(
        case_id: str,
        brief_id: str,
        snapshot_hash: str | None = Query(default=None),
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=20, ge=1, le=20),
    ) -> dict[str, Any]:
        brief = _require_brief(case_id, brief_id)
        dossier = _dossier_for(brief_id, snapshot_hash)
        lines = [line for line in brief["text"].splitlines() if line]
        slice_lines = lines[offset : offset + limit]
        blocks = [
            {
                "part": "word/document.xml",
                "paragraph_index": offset + idx,
                "kind": "body",
                "text": line,
                "text_sha256": _sha(line),
                "editable": True,
            }
            for idx, line in enumerate(slice_lines)
        ]
        return {
            "schema": "caseproof-docx-editor-blocks-v1",
            "brief_version_id": brief_id,
            "snapshot_hash": dossier["snapshot_hash"],
            "original_sha256": brief["sha256"],
            "original_byte_length": len(brief["docx"]),
            "total": len(lines),
            "editable_count": len(lines),
            "blocks": blocks,
            "has_more": offset + limit < len(lines),
        }

    @app.get("/v2/matters/{case_id}/briefs/{brief_id}/dossier/editor/revisions")
    def demo_editor_revisions(
        case_id: str,
        brief_id: str,
        snapshot_hash: str | None = Query(default=None),
    ) -> dict[str, Any]:
        brief = _require_brief(case_id, brief_id)
        dossier = _dossier_for(brief_id, snapshot_hash)
        return {
            "schema": "caseproof-docx-editor-revisions-v1",
            "brief_version_id": brief_id,
            "snapshot_hash": dossier["snapshot_hash"],
            "original_sha256": brief["sha256"],
            "revisions": [],
        }

    # --- Preserved Original Sources (PDF exhibits + Draft DOCX) ---

    def _source_original_response(
        brief_id: str, version_id: str, snapshot_hash: str | None
    ) -> Response:
        snap = snapshot_hash or _current_audit(brief_id)["snapshot_hash"]
        if version_id in state["briefs"]:
            brief = state["briefs"][version_id]
            return Response(
                content=brief["docx"],
                media_type=(
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                ),
                headers={
                    "Content-Disposition": 'attachment; filename="conclusions-synthese-demo.docx"',
                    "X-CaseProof-Snapshot": snap,
                    "X-CaseProof-Original-SHA256": brief["sha256"],
                    "X-Content-SHA256": brief["sha256"],
                    "Cache-Control": "no-store",
                },
            )
        if version_id not in DEMO_PDF_SOURCES:
            raise HTTPException(404, "unknown demo source")
        filename, pdf_bytes = DEMO_PDF_SOURCES[version_id]
        digest = _sha_bytes(pdf_bytes)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "X-CaseProof-Snapshot": snap,
                "X-CaseProof-Original-SHA256": digest,
                "X-Content-SHA256": digest,
                "Cache-Control": "no-store",
            },
        )

    @app.get("/v2/matters/{case_id}/briefs/{brief_id}/dossier/sources/{version_id}/original")
    def demo_original_source(
        case_id: str,
        brief_id: str,
        version_id: str,
        snapshot_hash: str | None = Query(default=None),
    ) -> Response:
        _require_brief(case_id, brief_id)
        return _source_original_response(brief_id, version_id, snapshot_hash)

    @app.get(
        "/v2/matters/{case_id}/briefs/{brief_id}/dossier/history/{snapshot_hash}"
        "/sources/{version_id}/original"
    )
    def demo_history_original_source(
        case_id: str, brief_id: str, snapshot_hash: str, version_id: str
    ) -> Response:
        _require_brief(case_id, brief_id)
        return _source_original_response(brief_id, version_id, snapshot_hash)

    @app.get(
        "/v2/matters/{case_id}/briefs/{brief_id}/sources/{source_id}/versions/{version_id}/original"
    )
    def demo_condition_original_source(
        case_id: str, brief_id: str, source_id: str, version_id: str
    ) -> Response:
        _require_brief(case_id, brief_id)
        meta = DEMO_SOURCE_META.get(version_id)
        if meta is None or meta["source_id"] != source_id:
            raise HTTPException(404, "unknown demo source")
        return _source_original_response(brief_id, version_id, None)

    # --- Built Frontend SPA Mount (`/workspace/` matches `vite.config.ts` base & BrowserRouter) ---

    dist = (frontend_dist or (Path(__file__).resolve().parents[1] / "frontend" / "dist")).resolve()
    if dist.is_dir() and (dist / "index.html").is_file():
        assets = dist / "assets"
        if assets.is_dir():
            app.mount(
                "/workspace/assets",
                StaticFiles(directory=str(assets)),
                name="demo-workspace-assets",
            )

        @app.get("/")
        def root_redirect() -> RedirectResponse:
            return RedirectResponse(url="/workspace/", status_code=307)

        @app.get("/workspace")
        def workspace_redirect() -> RedirectResponse:
            return RedirectResponse(url="/workspace/", status_code=307)

        @app.get("/workspace/{full_path:path}")
        def workspace_spa(full_path: str) -> FileResponse:
            if full_path:
                candidate = (dist / full_path).resolve()
                try:
                    candidate.relative_to(dist)
                except ValueError as exc:
                    raise HTTPException(404, "not found") from exc
                if candidate.is_file():
                    return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run CaseProof local synthetic 5-trap FastAPI partner demo."
    )
    parser.add_argument("--port", type=int, default=8000, help="Loopback port (127.0.0.1 only)")
    args = parser.parse_args(argv)
    import uvicorn

    print(DEMO_BANNER)
    print(f"Serving loopback FastAPI partner demo on http://127.0.0.1:{args.port}/workspace/")
    print(f"5-trap audit JSON: http://127.0.0.1:{args.port}/v2/demo/five-trap-audit")
    uvicorn.run(create_partner_demo_app(), host="127.0.0.1", port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
