"""Validate original synthetic M0 NL/FR litigation gold candidate fixtures.

This tests corpus integrity only, not litigation product inference accuracy.
No network, provider, customer data or production side effects.
"""

import argparse
import hashlib
import json
import unicodedata
from collections import Counter
from pathlib import Path

DEFAULT_CORPUS = Path(__file__).resolve().parents[1] / "evals/litigation/m0_corpus_v1.json"
STATES = {"match", "mismatch", "ambiguous", "unavailable", "unresolved", "not_applicable"}


def literal_state(case: dict) -> str:
    """Small reference oracle: not the production citation-checking engine."""
    citation = case["citation"]
    selected = [
        item
        for item in case["sources"]
        if citation["label"] in [item["label"], *item["aliases"]]
        and item["pdf_page"] == citation["pdf_page"]
    ]
    if not selected:
        return "unresolved"
    if len(selected) != 1:
        return "ambiguous"
    source = selected[0]
    if source["representation_status"] != "indexed_text":
        return "unavailable"
    if not citation["quote"]:
        return "not_applicable"
    quote = unicodedata.normalize("NFC", citation["quote"])
    passage = unicodedata.normalize("NFC", source["text"])
    return "match" if quote in passage else "mismatch"


def validate(data: dict) -> dict:
    if data.get("schema_version") != "caseproof-litigation-gold-v1":
        raise ValueError("unknown corpus schema")
    provenance = data["provenance"]
    if provenance["label_status"] != "author_supplied_unadjudicated" or "synthetic" not in provenance["rights"]:
        raise ValueError("rights/label qualifications absent")
    if data.get("allowed_languages") != ["nl", "fr", "en", "mixed"]:
        raise ValueError("NL/FR/EN/mixed language declaration required")
    cases = data["cases"]
    if not isinstance(cases, list) or len(cases) < 10:
        raise ValueError("expected at least 10 distinct scenarios")
    languages = Counter()
    observed = Counter()
    ids = set()
    clean = 0
    for case in cases:
        case_id = case["id"]
        if not isinstance(case_id, str) or not case_id or case_id in ids:
            raise ValueError("case id missing/duplicate")
        ids.add(case_id)
        if case["language"] not in {"nl", "fr", "mixed"}:
            raise ValueError(f"{case_id}: unsupported language")
        languages[case["language"]] += 1
        if case["cohort"] not in {"clean", "review", "adversarial"}:
            raise ValueError(f"{case_id}: unknown cohort")
        if not case["brief_text"]:
            raise ValueError(f"{case_id}: missing brief")
        if type(case["citation"]["pdf_page"]) is not int or case["citation"]["pdf_page"] <= 0:
            raise ValueError(f"{case_id}: invalid citation pdf page")
        seen_versions = set()
        source_ids = set()
        for source in case["sources"]:
            identity = (source["source_id"], source["version"], source["pdf_page"])
            if identity in seen_versions:
                raise ValueError(f"{case_id}: duplicate source/version/page")
            seen_versions.add(identity)
            source_ids.add(source["source_id"])
            if type(source["pdf_page"]) is not int or source["pdf_page"] <= 0:
                raise ValueError(f"{case_id}: invalid source pdf page")
            if source["printed_page"] is not None and (
                type(source["printed_page"]) is not int or source["printed_page"] <= 0
            ):
                raise ValueError(f"{case_id}: invalid printed page")
            if len([source["label"], *source["aliases"]]) != len(set([source["label"], *source["aliases"]])):
                raise ValueError(f"{case_id}: repeated alias")
            if source["representation_status"] == "indexed_text":
                if not isinstance(source["text"], str) or not source["text"]:
                    raise ValueError(f"{case_id}: indexed source missing representation")
            elif source["representation_status"] == "unprocessed_scan":
                if source["text"] is not None:
                    raise ValueError(f"{case_id}: unprocessed scan cannot claim text")
            else:
                raise ValueError(f"{case_id}: unsupported representation status")
        for query in case["retrieval_queries"]:
            if not query["query"] or not query["relevant_source_ids"]:
                raise ValueError(f"{case_id}: empty query relevance labels")
            if not set(query["relevant_source_ids"]) <= source_ids:
                raise ValueError(f"{case_id}: retrieval qrel references unknown source")
        expected = case["expected"]
        if expected["literal_state"] not in STATES:
            raise ValueError(f"{case_id}: unknown expected literal state")
        if len(expected["human_review_labels"]) != len(set(expected["human_review_labels"])):
            raise ValueError(f"{case_id}: duplicate review label")
        if not set(expected["human_review_labels"]) <= set(data["allowed_gold_labels"]):
            raise ValueError(f"{case_id}: unknown human label")
        actual = literal_state(case)
        if actual != expected["literal_state"]:
            raise ValueError(f"{case_id}: expected {expected['literal_state']}, oracle observed {actual}")
        if case["cohort"] == "clean":
            clean += 1
            if actual != "match" or expected["human_review_labels"]:
                raise ValueError(f"{case_id}: clean control is not clean")
        observed[actual] += 1
    if not {"nl", "fr", "mixed"} <= set(languages) or clean < 2:
        raise ValueError("missing language cohort or clean controls")
    for state in ("match", "mismatch", "ambiguous", "unavailable", "unresolved"):
        if not observed[state]:
            raise ValueError(f"missing negative/positive control: {state}")
    return {
        "schema_version": data["schema_version"],
        "status": "fixture_integrity_only",
        "label_status": provenance["label_status"],
        "case_count": len(cases),
        "clean_controls": clean,
        "languages": dict(sorted(languages.items())),
        "literal_states": dict(sorted(observed.items())),
        "human_accuracy_measured": False,
        "production_workflow_measured": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    args = parser.parse_args()
    content = args.corpus.read_bytes()
    try:
        report = validate(json.loads(content))
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.error(f"invalid synthetic litigation corpus: {exc}")
    report["corpus_sha256"] = hashlib.sha256(content).hexdigest()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
