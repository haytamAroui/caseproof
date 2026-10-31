"""Audit M0 trilingual synthetic candidates; never certify product or legal accuracy.

The first 19 cases must be byte-semantically unchanged from v2. The new cases
test *declared* four-dimension fixture labels with an independent structural
oracle. This is not a production checker, OCR benchmark or human adjudication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.validate_litigation_corpus import literal_state

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "evals/litigation/m0_corpus_v3.json"
PRIOR_CORPUS = ROOT / "evals/litigation/m0_corpus_v2.json"
LANGUAGES = {"nl", "fr", "en", "mixed"}
IDENTITY = {"resolved", "ambiguous", "source_missing", "not_in_inventory", "not_assessed"}
PAGE = {"mapped", "unmapped", "conflicting"}
FIDELITY = {
    "exact_match", "mismatch", "ocr_unreliable", "translation_review_required",
    "not_applicable", "not_assessed",
}


def expected_dimensions(case: dict[str, Any]) -> dict[str, str]:
    """Mechanical contract oracle for new synthetic examples only."""
    citation = case["citation"]
    inventory = case["inventory"]
    label = citation["label"]
    listings = inventory["listed_labels"]
    status = inventory["status"]

    if status == "unconfirmed" or label not in listings and status == "incomplete_confirmed":
        identity = "not_assessed"
    elif label not in listings:
        identity = "not_in_inventory"
    else:
        matches = [
            source for source in case["sources"]
            if label in [source["label"], *source["aliases"]]
        ]
        if not matches:
            identity = "source_missing"
        elif len(matches) > 1:
            identity = "ambiguous"
        else:
            identity = "resolved"

    page = "unmapped"
    fidelity = "not_assessed"
    if identity == "resolved":
        source = matches[0]
        pdf_matches = source["pdf_page"] == citation["pdf_page"]
        printed_matches = citation.get("printed_page_ref", source["printed_page"]) == source["printed_page"]
        bundle_matches = citation.get("bundle_page_ref", source["bundle_page"]) == source["bundle_page"]
        page = "mapped" if pdf_matches and printed_matches and bundle_matches else "conflicting"
        if page == "mapped":
            if citation.get("translated_claim", False):
                fidelity = "translation_review_required"
            elif source["representation_status"] == "unprocessed_scan":
                fidelity = "ocr_unreliable"
            elif not citation.get("quote"):
                fidelity = "not_applicable"
            else:
                source_text = unicodedata.normalize("NFC", source["text"])
                quote = unicodedata.normalize("NFC", citation["quote"])
                fidelity = "exact_match" if quote in source_text else "mismatch"

    return {"identity": identity, "page": page, "fidelity": fidelity, "semantic": "not_assessed"}


def audit(data: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    if data.get("schema_version") != "caseproof-litigation-gold-v3":
        raise ValueError("expected v3 corpus")
    if previous.get("schema_version") != "caseproof-litigation-gold-v2":
        raise ValueError("expected frozen v2 predecessor")
    provenance = data["provenance"]
    if provenance.get("label_status") != "author_supplied_unadjudicated":
        raise ValueError("independent label adjudication cannot be claimed")
    if "CC0-1.0" not in provenance.get("rights", "") or "synthetic" not in provenance.get("rights", ""):
        raise ValueError("corpus provenance or rights missing")
    if data.get("allowed_languages") != ["nl", "fr", "en", "mixed"]:
        raise ValueError("declared language baseline changed")
    previous_cases = previous["cases"]
    all_cases = data["cases"]
    if data.get("legacy_case_count") != len(previous_cases) or all_cases[:len(previous_cases)] != previous_cases:
        raise ValueError("historical v2 cases changed or reordered")
    new_cases = all_cases[len(previous_cases):]
    ids = [item["id"] for item in all_cases]
    if len(set(ids)) != len(ids) or [case["id"] for case in new_cases] != data.get("new_case_ids"):
        raise ValueError("missing, repeated or reordered case IDs")
    if len(new_cases) < 16:
        raise ValueError("insufficient independent-language boundary scenarios")
    languages: Counter[str] = Counter()
    identity_counts: Counter[str] = Counter()
    page_counts: Counter[str] = Counter()
    fidelity_counts: Counter[str] = Counter()
    for case in new_cases:
        cid = case["id"]
        language = case["language"]
        if language not in LANGUAGES:
            raise ValueError(f"{cid}: invalid language")
        languages[language] += 1
        if not isinstance(case.get("brief_text"), str) or not case["brief_text"].strip():
            raise ValueError(f"{cid}: missing original brief text")
        if case["cohort"] not in {"clean", "review", "adversarial"}:
            raise ValueError(f"{cid}: invalid cohort")
        if case["rights"] != {
            "origin": "new fictional CaseProof M0 authored example",
            "license": "CC0-1.0",
            "customer_or_court_material": False,
        }:
            raise ValueError(f"{cid}: case-level synthetic rights declaration missing")
        review = case["review_basis"]
        if review.get("status") != "author_supplied_unadjudicated" or not review.get("rationale", "").strip():
            raise ValueError(f"{cid}: author-only decision rationale missing")
        inv = case["inventory"]
        if inv["status"] not in {"complete_confirmed", "incomplete_confirmed", "unconfirmed"}:
            raise ValueError(f"{cid}: invalid inventory status")
        listed = inv["listed_labels"]
        if not isinstance(listed, list) or len(listed) != len(set(listed)):
            raise ValueError(f"{cid}: inventory entries repeated")
        citation = case["citation"]
        if type(citation["pdf_page"]) is not int or citation["pdf_page"] < 1:
            raise ValueError(f"{cid}: invalid citation page")
        for key in ("printed_page_ref", "bundle_page_ref"):
            if key in citation and (type(citation[key]) is not int or citation[key] < 1):
                raise ValueError(f"{cid}: invalid {key}")
        if citation.get("translated_claim", False) not in (True, False):
            raise ValueError(f"{cid}: invalid translation marker")
        if citation["quote"] is not None and not isinstance(citation["quote"], str):
            raise ValueError(f"{cid}: quotation type invalid")
        seen = set()
        for source in case["sources"]:
            locator = (source["source_id"], source["version"], source["pdf_page"])
            if locator in seen:
                raise ValueError(f"{cid}: repeated source locator")
            seen.add(locator)
            if any(type(source[key]) is not int or source[key] < 1 for key in ("pdf_page", "bundle_page")):
                raise ValueError(f"{cid}: invalid source page")
            if source["printed_page"] is not None and (
                type(source["printed_page"]) is not int or source["printed_page"] < 1
            ):
                raise ValueError(f"{cid}: invalid printed page")
            if len(set([source["label"], *source["aliases"]])) != len([source["label"], *source["aliases"]]):
                raise ValueError(f"{cid}: duplicated source alias")
            if source["representation_status"] == "unprocessed_scan":
                if source["text"] is not None:
                    raise ValueError(f"{cid}: missing OCR cannot contain extracted text")
            elif source["representation_status"] == "indexed_text":
                if not isinstance(source["text"], str) or not source["text"]:
                    raise ValueError(f"{cid}: indexed text must be nonempty")
            else:
                raise ValueError(f"{cid}: invalid representation status")
        dims = case["expected_dimensions"]
        if set(dims) != {"identity", "page", "fidelity", "semantic"} or (
            dims["identity"] not in IDENTITY or dims["page"] not in PAGE
            or dims["fidelity"] not in FIDELITY or dims["semantic"] != "not_assessed"
        ):
            raise ValueError(f"{cid}: unknown or authoritative semantic state")
        calculated = expected_dimensions(case)
        if calculated != dims:
            raise ValueError(f"{cid}: expected {dims}, independent contract oracle gives {calculated}")
        if literal_state(case) != case["expected"]["literal_state"]:
            raise ValueError(f"{cid}: legacy literal oracle disagreement")
        if case["cohort"] == "clean" and (
            dims["identity"] != "resolved" or dims["page"] != "mapped"
            or dims["fidelity"] != "exact_match" or case["expected"]["human_review_labels"]
        ):
            raise ValueError(f"{cid}: contaminated clean control")
        identity_counts[dims["identity"]] += 1
        page_counts[dims["page"]] += 1
        fidelity_counts[dims["fidelity"]] += 1

    if any(languages[lang] < 2 for lang in LANGUAGES):
        raise ValueError("NL/FR/EN/mixed scenario distribution insufficient")
    if not {"resolved", "ambiguous", "source_missing", "not_in_inventory", "not_assessed"} <= set(identity_counts):
        raise ValueError("identity boundary controls missing")
    if not PAGE <= set(page_counts):
        raise ValueError("three-space page boundary controls missing")
    if not FIDELITY <= set(fidelity_counts):
        raise ValueError("fidelity/abstention controls missing")
    if sum(c["cohort"] == "clean" for c in new_cases) < 2:
        raise ValueError("zero-error controls absent")
    return {
        "status": "synthetic_fixture_integrity_only",
        "current_schema": data["schema_version"],
        "legacy_v2_cases_unchanged": len(previous_cases),
        "new_cases": len(new_cases),
        "total_cases": len(all_cases),
        "languages_new": dict(sorted(languages.items())),
        "identity_new": dict(sorted(identity_counts.items())),
        "page_new": dict(sorted(page_counts.items())),
        "fidelity_new": dict(sorted(fidelity_counts.items())),
        "label_status": "author_supplied_unadjudicated",
        "independent_human_review": False,
        "actual_pdf_docx_ocr_tested": False,
        "product_accuracy_measured": False,
        "m0_exit_signoff": "OPEN",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--previous", type=Path, default=PRIOR_CORPUS)
    args = parser.parse_args()
    content = args.corpus.read_bytes()
    original = args.previous.read_bytes()
    try:
        report = audit(json.loads(content), json.loads(original))
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.error(f"invalid M0 evaluation baseline: {exc}")
    report["corpus_sha256"] = hashlib.sha256(content).hexdigest()
    report["previous_sha256"] = hashlib.sha256(original).hexdigest()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
