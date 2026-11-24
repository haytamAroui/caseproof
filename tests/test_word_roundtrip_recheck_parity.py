"""BE-04: Word round-trip recheck parity (carried vs superseded decisions + 409 guard)."""

from __future__ import annotations

import io
from unittest.mock import Mock
from uuid import uuid4

from docx import Document
from fastapi import FastAPI
from fastapi.testclient import TestClient

from application.litigation.legal_review_decisions import (
    carry,
    make_decision,
    occurrence_fingerprints,
    validate_review,
)
from apps.api.dossier_journey import create_dossier_router
from infrastructure.parsers.docx_text_regions import extract_docx_text_regions

CASE_ID = str(uuid4())
OLD_BRIEF_ID = str(uuid4())
NEW_BRIEF_ID = str(uuid4())
PACK_SHA = "a" * 64
ART_SHA = {"cc:1732:fr:2024": "b" * 64, "cc:1728:fr:2024": "c" * 64}


def _docx_bytes(paragraphs: list[str]) -> bytes:
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_word_roundtrip_carries_unchanged_and_supersedes_modified_finding() -> None:
    p1 = "Selon l'art. 1732 Code civil, le preneur répond des dégradations."
    p2_v1 = "Selon l'art. 1728 Code civil, le délai de préavis est de trois mois."
    p2_v2 = "Selon l'art. 1728 Code civil, le délai de préavis est de six mois."

    v1_text = "\n".join(r.text for r in extract_docx_text_regions(_docx_bytes([p1, p2_v1])).regions)
    v2_text = "\n".join(r.text for r in extract_docx_text_regions(_docx_bytes([p1, p2_v2])).regions)

    def _refs(text: str) -> list[dict[str, object]]:
        i1 = text.index("art. 1732 Code civil")
        i2 = text.index("art. 1728 Code civil")
        return [
            {
                "raw_text": "art. 1732 Code civil",
                "status": "PASS",
                "quote": None,
                "corpus_key": "cc:1732:fr:2024",
                "start": i1,
                "end": i1 + len("art. 1732 Code civil"),
            },
            {
                "raw_text": "art. 1728 Code civil",
                "status": "FAIL",
                "quote": "trois mois" if "trois mois" in text else "six mois",
                "corpus_key": "cc:1728:fr:2024",
                "start": i2,
                "end": i2 + len("art. 1728 Code civil"),
            },
        ]

    fps_v1 = occurrence_fingerprints(_refs(v1_text), ART_SHA, PACK_SHA, v1_text)
    fps_v2 = occurrence_fingerprints(_refs(v2_text), ART_SHA, PACK_SHA, v2_text)

    prior_review = {
        "decisions": [
            make_decision(
                fingerprint=fps_v1[0],
                action="confirm",
                reason="article vérifié sur pièce",
                reviewer_label="Me Dupont",
                revision=1,
            ),
            make_decision(
                fingerprint=fps_v1[1],
                action="reject",
                reason="trois mois est erroné",
                reviewer_label="Me Dupont",
                revision=1,
            ),
        ],
        "superseded": [],
        "release_authorized": False,
    }
    validate_review(prior_review, fps_v1)

    rechecked = carry(prior_review, "checkpoint-v1", fps_v2)
    validate_review(rechecked, fps_v2)

    assert len(rechecked["decisions"]) == 1
    assert rechecked["decisions"][0]["fingerprint"] == fps_v2[0]
    assert rechecked["decisions"][0]["origin"] == "carried"
    assert rechecked["decisions"][0]["carried_from"] == "checkpoint-v1"

    assert len(rechecked["superseded"]) == 1
    assert rechecked["superseded"][0]["fingerprint"] == fps_v1[1]
    assert fps_v2[1] not in {d["fingerprint"] for d in rechecked["decisions"]}


def test_signed_recheck_route_rejects_superseded_draft_and_allows_active_draft() -> None:
    store = Mock()
    store.current_draft_version.return_value = NEW_BRIEF_ID
    store.load.return_value = ({"case_id": CASE_ID, "brief_id": NEW_BRIEF_ID, "snapshot_hash": "d" * 64}, {})

    app = FastAPI()
    app.include_router(create_dossier_router(store))
    client = TestClient(app)
    headers = {"Authorization": "Bearer signed-test-token"}

    stale = client.post(
        f"/v2/matters/{CASE_ID}/briefs/{OLD_BRIEF_ID}/dossier/recheck", headers=headers
    )
    assert stale.status_code == 409
    assert "superseded" in stale.json()["detail"].lower()

    active = client.post(
        f"/v2/matters/{CASE_ID}/briefs/{NEW_BRIEF_ID}/dossier/recheck", headers=headers
    )
    assert active.status_code == 200
    assert active.json()["brief_id"] == NEW_BRIEF_ID
