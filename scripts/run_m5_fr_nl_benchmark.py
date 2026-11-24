"""M5-02 / P5-03 synthetic 5-dossier Belgian FR/NL benchmark harness.

Measures deterministic catch rate, fail-closed abstentions, false-alarm count
on clean controls, and wall-clock execution time across 5 representative
Belgian civil/commercial litigation scenarios:

  1. Bail commercial (FR): omitted opening reservation + 'signé' vs 'envoyé pour signature'
  2. Aanneming (NL): 'ondertekend' vs 'ter ondertekening' + NBSP/Belgian currency difference
  3. Référé bilingue (FR↔NL): cross-language payment match + ambiguous date abstention (AMBIGUOUS_DATE_FORMAT)
  4. Droit transitoire (FR): missing inventory piece under confirmed complete inventory
  5. Dossier témoin sans erreur (FR/NL clean control): 0 false alarms expected

SYNTHETIC ENGINEERING BENCHMARK ONLY — never practitioner M5 commercial
validation, never population recall proof, never client-data authorization.

Usage:
    python -m scripts.run_m5_fr_nl_benchmark [--json-out benchmark.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from application.litigation.factual_values import (
    FactAssertion,
    FactKind,
    FactRole,
    FactState,
    compare_fact,
)
from application.litigation.inventory_mapping import map_exhibit_references
from application.litigation.library import EvidencePreview, EvidenceRow


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _preview(source_id: str, version_id: str, text: str) -> EvidencePreview:
    return EvidencePreview(
        EvidenceRow(
            source_id=source_id,
            document_id=f"doc-{source_id}",
            version_id=version_id,
            original_sha256=_sha(text),
            media_type="application/pdf",
            status="ready",
            parser_id="synthetic-m5-bench-v1",
            representation_id=f"repr-{source_id}",
            pages=(),
            warnings=(),
        ),
        text,
        ((0, len(text), "pdf-page-1", 0),),
    )


def _intake(
    brief_id: str,
    sources: list[tuple[str, str, str]],
    entries: list[tuple[str, str, str]],
    *,
    complete: bool = True,
) -> dict[str, Any]:
    return {
        "brief_id": brief_id,
        "confirmation_id": "conf-bench-1",
        "inventory_complete": complete,
        "sources": [
            {
                "version_id": ver,
                "filename": fname,
                "sha256": _sha(text),
                "readback": "verified",
                "page_count": 1,
            }
            for ver, fname, text in sources
        ],
        "entries": [
            {"label": label, "number": number, "source_version_id": ver, "pages": []}
            for label, number, ver in entries
        ],
    }


def run_benchmark() -> dict[str, Any]:
    """Execute all 5 synthetic FR/NL dossiers and return exact denominator metrics."""
    started = time.perf_counter()
    dossiers: list[dict[str, Any]] = []

    # Dossier 1: FR commercial lease — 2 seeded traps (reservation + status cue)
    t0 = time.perf_counter()
    d1_src1 = (
        "Article 8. Sous réserve de l'accord écrit du bailleur, "
        "le locataire peut céder son droit au bail."
    )
    d1_src2 = "Avenant n°2 envoyé pour signature le 14 mars 2026."
    d1_brief = (
        "Le bail stipule que « le locataire peut céder son droit au bail » (Pièce 1). "
        "L'avenant a été signé le 14 mars 2026 (Pièce 2)."
    )
    d1_map = map_exhibit_references(
        d1_brief,
        brief_version_id="b-1",
        intake=_intake(
            "b-1",
            [("v1", "piece1.pdf", d1_src1), ("v2", "piece2.pdf", d1_src2)],
            [("piece", "1", "v1"), ("piece", "2", "v2")],
        ),
        previews=[_preview("s1", "v1", d1_src1), _preview("s2", "v2", d1_src2)],
    )
    d1_res_caught = any(r.get("reservation_cue_flag") is not None for r in d1_map["references"])
    d1_status_caught = any(r.get("status_cue_flag") is not None for r in d1_map["references"])
    dossiers.append(
        {
            "id": "fr-bail-commercial",
            "language": "fr",
            "is_clean_control": False,
            "seeded_traps": 2,
            "caught_traps": int(d1_res_caught) + int(d1_status_caught),
            "abstentions": 0,
            "false_alarms": 0,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 3),
        }
    )

    # Dossier 2: NL construction — 2 seeded traps (NL status cue + NBSP currency difference)
    t0 = time.perf_counter()
    d2_src1 = "Ontwerpovereenkomst verzonden ter ondertekening op 12 maart 2026."
    d2_src2 = "Betaling ontvangen: 10.000,00 €."
    d2_brief = (
        "De overeenkomst werd ondertekend op 12 maart 2026 (Stuk 1). "
        "De betaling van 12\u00a0500,00 EUR werd verricht."
    )
    d2_map = map_exhibit_references(
        d2_brief,
        brief_version_id="b-2",
        intake=_intake(
            "b-2",
            [("v1", "stuk1.pdf", d2_src1)],
            [("stuk", "1", "v1")],
        ),
        previews=[_preview("s1", "v1", d2_src1)],
    )
    d2_claim = "De betaling van 12\u00a0500,00 EUR werd verricht."
    d2_fact = compare_fact(
        FactAssertion(
            "f-nl-1",
            "ref-2",
            d2_claim,
            d2_brief.index(d2_claim),
            d2_brief.index(d2_claim) + len(d2_claim),
            FactKind.MONEY,
            FactRole.PAYMENT,
            "nl",
            "nl",
        ),
        verified_brief_text=d2_brief,
        preview=_preview("s2", "v2", d2_src2),
        pdf_page=1,
    )
    d2_caught = int(any(r.get("status_cue_flag") is not None for r in d2_map["references"])) + int(
        d2_fact.state is FactState.DIFFERENCE
    )
    dossiers.append(
        {
            "id": "nl-aanneming",
            "language": "nl",
            "is_clean_control": False,
            "seeded_traps": 2,
            "caught_traps": d2_caught,
            "abstentions": 0,
            "false_alarms": 0,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 3),
        }
    )

    # Dossier 3: FR↔NL bilingual summary — 1 clean cross-lang match + 1 ambiguous date abstention
    t0 = time.perf_counter()
    d3_src_money = "Betaling ontvangen: 1.250,00 €."
    d3_claim_money = "Le paiement de 1\u00a0250,00 EUR a été versé."
    d3_obs_money = compare_fact(
        FactAssertion(
            "f-bi-1",
            "ref-1",
            d3_claim_money,
            0,
            len(d3_claim_money),
            FactKind.MONEY,
            FactRole.PAYMENT,
            "fr",
            "nl",
        ),
        verified_brief_text=d3_claim_money,
        preview=_preview("s3a", "v3a", d3_src_money),
        pdf_page=1,
    )
    d3_claim_date = "Le paiement a eu lieu le 04/05/2026."
    d3_src_date = "Betaling ontvangen op 22 mei 2026."
    d3_obs_date = compare_fact(
        FactAssertion(
            "f-bi-2",
            "ref-2",
            d3_claim_date,
            0,
            len(d3_claim_date),
            FactKind.DATE,
            FactRole.PAYMENT,
            "fr",
            "nl",
        ),
        verified_brief_text=d3_claim_date,
        preview=_preview("s3b", "v3b", d3_src_date),
        pdf_page=1,
    )
    d3_abstained = d3_obs_date.state is FactState.NEEDS_CONTEXT and (
        d3_obs_date.explanation == "AMBIGUOUS_DATE_FORMAT"
    )
    d3_false_alarm = 0 if d3_obs_money.state is FactState.MATCH else 1
    dossiers.append(
        {
            "id": "fr-nl-bilingual-refere",
            "language": "fr/nl",
            "is_clean_control": False,
            "seeded_traps": 1,
            "caught_traps": int(d3_abstained),
            "abstentions": int(d3_abstained),
            "false_alarms": d3_false_alarm,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 3),
        }
    )

    # Dossier 4: Missing piece in confirmed complete inventory (1 seeded trap)
    t0 = time.perf_counter()
    d4_brief = "Voir également la mise en demeure (Pièce 9)."
    d4_map = map_exhibit_references(
        d4_brief,
        brief_version_id="b-4",
        intake=_intake("b-4", [("v1", "p1.pdf", "Pièce 1")], [("piece", "1", "v1")], complete=True),
        previews=[_preview("s4", "v1", "Pièce 1")],
    )
    d4_absent = any(
        r["status"] == "UNVERIFIED"
        and r["reason"] == "piece_number_absent_from_confirmed_complete_inventory"
        for r in d4_map["references"]
    )
    dossiers.append(
        {
            "id": "fr-missing-inventory-piece",
            "language": "fr",
            "is_clean_control": False,
            "seeded_traps": 1,
            "caught_traps": int(d4_absent),
            "abstentions": 0,
            "false_alarms": 0,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 3),
        }
    )

    # Dossier 5: Clean zero-error control (must produce 0 false alarms)
    t0 = time.perf_counter()
    d5_src = (
        "Article 8. Sous réserve de l'accord écrit du bailleur, "
        "le locataire peut céder son droit au bail. "
        "Le contrat a été signé le 14 mars 2026."
    )
    d5_brief = (
        "Selon l'article 8, « Sous réserve de l'accord écrit du bailleur, "
        "le locataire peut céder son droit au bail » et le contrat a été signé le 14 mars 2026 (Pièce 1)."
    )
    d5_map = map_exhibit_references(
        d5_brief,
        brief_version_id="b-5",
        intake=_intake("b-5", [("v1", "clean.pdf", d5_src)], [("piece", "1", "v1")], complete=True),
        previews=[_preview("s5", "v1", d5_src)],
    )
    d5_false = sum(
        1
        for r in d5_map["references"]
        if r.get("status_cue_flag") is not None
        or r.get("reservation_cue_flag") is not None
        or r["status"] == "UNVERIFIED"
    )
    dossiers.append(
        {
            "id": "fr-clean-zero-error-control",
            "language": "fr",
            "is_clean_control": True,
            "seeded_traps": 0,
            "caught_traps": 0,
            "abstentions": 0,
            "false_alarms": d5_false,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 3),
        }
    )

    total_seeded = sum(d["seeded_traps"] for d in dossiers)
    total_caught = sum(d["caught_traps"] for d in dossiers)
    total_false_alarms = sum(d["false_alarms"] for d in dossiers)
    return {
        "schema": "caseproof-m5-synthetic-benchmark-v1",
        "synthetic_benchmark": True,
        "not_practitioner_m5_signoff": True,
        "dossier_count": len(dossiers),
        "seeded_traps_total": total_seeded,
        "caught_traps_total": total_caught,
        "false_alarms_total": total_false_alarms,
        "total_elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "dossiers": dossiers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run CaseProof synthetic 5-dossier FR/NL M5 benchmark.")
    parser.add_argument("--json-out", type=Path, default=None, help="Optional JSON output path")
    args = parser.parse_args(argv)
    report = run_benchmark()
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.json_out is not None:
        args.json_out.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
