"""Synthetic OFFLINE M1 evidence inventory + confirmed alias illustration.

No real bearer, no customer content, no production upload or authorization claim.
"""
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from application.documents.intake import CapturedDocument
from application.litigation.library import EvidenceIndexer
from domains.disputes.exhibits import ExhibitEntry, ExhibitPage, ExhibitRegister
from infrastructure.parsers.limited import LimitedDocumentParser
from packages.evidence_kernel.domain.source_versions import SourceVersion


def main() -> None:
    corpus = json.loads(
        (Path(__file__).resolve().parents[1] / "evals/litigation/m0_corpus_v1.json").read_text(
            encoding="utf-8"
        )
    )
    samples = [next(item for item in corpus["cases"] if item["id"] == i) for i in (
        "NL_CLEAN_01", "FR_CLEAN_02", "FR_SCAN_05"
    )]
    documents = []
    for sample in samples:
        src = sample["sources"][0]
        # Simulated page state is NOT OCR validation. Input is original authored fixture text.
        raw = (src["text"] or "").encode("utf-8")
        if not raw:
            raw = b"Representation unavailable in synthetic scenario."
        captured = SourceVersion(
            src["source_id"], src["version"], sha256(raw).hexdigest(), raw,
            datetime(2026, 10, 26, tzinfo=UTC), "text/plain",
        )
        documents.append(CapturedDocument(src["source_id"], captured))
    indexer = EvidenceIndexer(LimitedDocumentParser())
    inventory = indexer.inventory(tuple(documents))
    registry = ExhibitRegister(1, (
        ExhibitEntry(
            "exhibit-nl-1", "Stuk 1",
            (ExhibitPage("nl_delivery", "v1", pdf_page=1, printed_page=1),),
            aliases=("Pièce 1",), confirmed=True,
        ),
    ))
    result = {
        "schema": "caseproof-m1-synthetic-demo-v1",
        "mode": "offline_synthetic_only",
        "real_auth": False,
        "customer_storage": False,
        "ocr_evaluated": False,
        "inventory": [
            {"source_id": row.source_id, "status": row.status, "sha256": row.original_sha256,
             "warnings": row.warnings}
            for row in inventory.rows
        ],
        "alias_resolution": registry.resolve("Pièce 1", pdf_page=1).state.value,
        "release_authorized": False,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
