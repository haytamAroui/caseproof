"""Prepare a blinded NL/FR/EN M0 human-review pack, never fill human decisions.

This is a handoff aid. The generator and assistant cannot be an independent
Belgian legal reviewer, authenticate a reviewer or sign the owner's acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.audit_m0_trilingual import DEFAULT_CORPUS


def make_packet(corpus: dict[str, Any], sha256: str) -> dict[str, Any]:
    cases = []
    for case in corpus["cases"]:
        # Opaque IDs keep authored cohort labels like MISMATCH/CLEAN/SCAN
        # out of first-pass human review. Mapping remains reproducible
        # from the pinned corpus but is not shipped in reviewer packets.
        reviewer_id = "CASE-" + hashlib.sha256((sha256 + ":" + case["id"]).encode()).hexdigest()[:12]
        sources = [
            {
                "source_id": "SRC-" + hashlib.sha256((sha256 + ":" + s["source_id"]).encode()).hexdigest()[:10],
                "version": s["version"],
                "label": s["label"],
                "aliases": s["aliases"],
                "pdf_page": s["pdf_page"],
                "printed_page": s["printed_page"],
                "bundle_page": s.get("bundle_page"),
                "representation_status": s["representation_status"],
                "text_or_unavailable": s["text"],
            }
            for s in case["sources"]
        ]
        cases.append({
            "id": reviewer_id,
            "language": case["language"],
            "brief_text": case["brief_text"],
            "citation": case["citation"],
            "inventory": case.get("inventory", {"status": "not_defined_in_legacy_v2", "listed_labels": []}),
            "sources": sources,
            "note": "Source and inventory information supplied to reviewer; DO NOT infer absent inventory is complete.",
        })
    return {
        "schema": "caseproof-m0-blind-review-v1",
        "corpus_sha256": sha256,
        "review_status": "AWAITING_INDEPENDENT_HUMAN_REVIEW",
        "instructions": "Review independently before looking at source corpus expected labels. Record what cannot be assessed.",
        "cases": cases,
        "case_ids_are_opaque": True,
        "original_author_labels_excluded": True,
    }


def generate(out: Path, corpus_path: Path = DEFAULT_CORPUS) -> dict[str, Any]:
    content = corpus_path.read_bytes()
    corpus = json.loads(content)
    out.mkdir(parents=True, exist_ok=True)
    packet = make_packet(corpus, hashlib.sha256(content).hexdigest())
    (out / "blind_cases.json").write_text(
        json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    template = {
        "schema": "caseproof-m0-review-submission-v1",
        "corpus_sha256": packet["corpus_sha256"],
        "reviewer": {
            "real_name": "",
            "organization": "",
            "languages_competent": [],
            "belgian_legal_qualification": "",
            "independence_and_conflicts_attested": False,
            "credential_and_signed_attestation_evidence": "",
            "review_date": "",
        },
        "cases": [
            {
                "id": c["id"],
                "source_observations": "",
                "identity": "",
                "page": "",
                "fidelity": "",
                "semantic_support": "NOT_ASSESSED",
                "confidence_and_limitations": "",
                "independent_rationale": "",
            }
            for c in packet["cases"]
        ],
        "submission_status": "EMPTY_UNREVIEWED_TEMPLATE",
    }
    (out / "empty_review_submission.json").write_text(
        json.dumps(template, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    guidance = """# Independent M0 NL/FR/EN review instructions

- This is a **first-pass blind case pack**. It contains opaque case IDs, no
  original author cohort tags, no proposed labels or author rationales.
- Keep the unblinded document generator archive and corpus JSON out of
  first-pass review. Inspect and adjudicate actual real-format bytes **after**
  independent first judgments have been recorded, with no answer key provided.
- Review each case in your competent language before opening the original gold.
  Do not inspect code or files with original case names (CLEAN/MISMATCH/SCAN).
  Case/source IDs in the blind packet are deliberately pseudonymized.
- Every case requires **two distinct independent human assessments**.
- For the 19 historical v2 cases the separate complete inventory was **not defined**.
  Mark identity based on inventory as unassessed unless independent original material
  proves that a confirmed complete inventory exists; never infer absence.
- A reviewer qualified in applicable Belgian procedure must evaluate the procedural
  interpretation and all flagged legal claims; disagreement needs a third adjudicator.
- Actual generated PDF/DOCX/image sources are synthetic and **not a filing**.
- Enter observed physical PDF page, printed label and bundle page separately.
- Do not make semantic support CONFIRMED from matching words alone.
- Add verified reviewer credentials, signed records and exact source hashes.
  This tool cannot confirm professional status or authenticate signatures.
- Only an actual named owner can approve M0 after those records are independently checked.
"""
    (out / "REVIEWER_INSTRUCTIONS.md").write_text(guidance, encoding="utf-8")
    return {"cases": len(packet["cases"]), "corpus_sha256": packet["corpus_sha256"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(generate(args.out), sort_keys=True))


if __name__ == "__main__":
    main()
