"""Controlled reviewer benchmark: blinded allocation and descriptive scoring only.

No labels, identities, signatures or elapsed time are independently authenticated
by this module. Real lawyer accuracy requires separately adjudicated original
evidence, actual human submissions, approved rights and trial governance.
"""

from __future__ import annotations

import hashlib
import itertools
import re
import statistics
from collections import defaultdict
from typing import Any

PACKET_SCHEMA = "caseproof-p1-blinded-reviewer-packet-v1"
ASSIGNMENTS_SCHEMA = "caseproof-p1-private-assignments-v1"
GOLD_SCHEMA = "caseproof-p1-independent-labels-v1"
SUBMISSIONS_SCHEMA = "caseproof-p1-reviewer-submissions-v1"
RESULTS_SCHEMA = "caseproof-p1-reviewer-descriptive-results-v1"
CONDITIONS = ("standard_interface", "guarded_term_warnings")
DECISIONS = {"SUPPORTED", "QUALIFIED", "CONTRADICTED", "UNASSESSED"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")


class BenchmarkInvalid(ValueError):
    """Reject invalid, incomplete or potentially misleading benchmark inputs."""


def _require(value: object, message: str) -> None:
    if not value:
        raise BenchmarkInvalid(message)


def _bounded(value: object, label: str, max_length: int = 4000) -> str:
    _require(isinstance(value, str) and 0 < len(value.strip()) <= max_length, label)
    assert isinstance(value, str)
    return value


def _digest(seed: str, *parts: str) -> str:
    return hashlib.sha256(("caseproof:p1:" + seed + ":" + ":".join(parts)).encode()).hexdigest()


def validate_cases(cases: list[dict[str, Any]]) -> None:
    """Only bounded synthetic / rights-cleared input; no gold or author labels."""
    _require(1 <= len(cases) <= 120, "1–120 cases required")
    seen: set[str] = set()
    for item in cases:
        cid = _bounded(item.get("case_id"), "case_id", 80)
        _require(bool(SAFE_ID.fullmatch(cid)) and cid not in seen, "duplicate or unsafe case id")
        seen.add(cid)
        _require(item.get("language") in {"nl", "fr"}, "only NL/FR cases supported")
        _bounded(item.get("source_version_id"), "source_version_id", 200)
        _require(
            isinstance(item.get("source_sha256"), str) and bool(SHA256.fullmatch(item["source_sha256"])),
            "original source sha256 required",
        )
        _require(
            type(item.get("physical_pdf_page")) is int and 1 <= item["physical_pdf_page"] <= 500,
            "physical PDF page required",
        )
        _bounded(item.get("source_pdf"), "source_pdf", 256)
        _bounded(item.get("draft_claim"), "draft_claim")
        _bounded(item.get("anchored_passage"), "anchored_passage")
        _bounded(item.get("context_before"), "context_before")
        _bounded(item.get("context_after"), "context_after")
        _require(isinstance(item.get("warnings"), list) and len(item["warnings"]) <= 24, "warnings invalid")
        for warning in item["warnings"]:
            _require(isinstance(warning, dict), "warning must be a record")
            _bounded(warning.get("kind"), "warning kind", 40)
            _bounded(warning.get("term"), "warning term", 96)


def make_blinded_packets(
    cases: list[dict[str, Any]],
    reviewer_languages: dict[str, list[str]],
    *,
    seed: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Balance arms by language competence, then generate per-reviewer blind packs.

    A reviewer stays in one condition; the same claim/source is displayed in
    both arms, with the only intended difference being advisory warnings.
    Assignment keys are opaque and the private mapping is held separately.
    """
    validate_cases(cases)
    _bounded(seed, "randomization seed", 256)
    _require(4 <= len(reviewer_languages) <= 24, "4–24 reviewer pseudonyms required")
    by_stratum: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for rid, languages in reviewer_languages.items():
        _require(bool(SAFE_ID.fullmatch(rid)), "reviewer id must be a pseudonym")
        _require(isinstance(languages, list) and languages, "language competence required")
        _require(set(languages) <= {"nl", "fr"}, "unsupported language")
        by_stratum[tuple(sorted(set(languages)))].append(rid)
    assignments: list[dict[str, Any]] = []
    packets: list[dict[str, Any]] = []
    cases_by_id = {item["case_id"]: item for item in cases}
    for stratum, reviewers in sorted(by_stratum.items()):
        ordered = sorted(reviewers, key=lambda rid: _digest(seed, "reviewer", rid))
        for position, rid in enumerate(ordered):
            condition = CONDITIONS[position % 2]
            eligible = [c for c in cases if c["language"] in stratum]
            _require(eligible, "reviewer has no eligible cases")
            order = sorted(eligible, key=lambda c: _digest(seed, "order", rid, c["case_id"]))
            shown: list[dict[str, Any]] = []
            for case in order:
                alias = "CASE-" + _digest(seed, "case", case["case_id"])[:14]
                assignment_id = "ASN-" + _digest(seed, "assignment", rid, case["case_id"])[:18]
                assignments.append(
                    {
                        "assignment_id": assignment_id,
                        "case_id": case["case_id"],
                        "case_ref": alias,
                        "reviewer_id": rid,
                        "condition": condition,
                        "source_version_id": case["source_version_id"],
                        "source_sha256": case["source_sha256"],
                        "physical_pdf_page": case["physical_pdf_page"],
                    }
                )
                shown.append(
                    {
                        "assignment_id": assignment_id,
                        "case_ref": alias,
                        "language": case["language"],
                        "source_version_id": case["source_version_id"],
                        "source_sha256": case["source_sha256"],
                        "physical_pdf_page": case["physical_pdf_page"],
                        "source_pdf": case["source_pdf"],
                        "draft_claim": case["draft_claim"],
                        "anchored_passage": case["anchored_passage"],
                        "context_before": case["context_before"],
                        "context_after": case["context_after"],
                        "guarded_term_warnings": (
                            [{"kind": w["kind"], "term": w["term"]} for w in case["warnings"]]
                            if condition == "guarded_term_warnings"
                            else []
                        ),
                        "guard_notice": (
                            "Lexical warnings only: no automatic support or contradiction determination"
                            if condition == "guarded_term_warnings"
                            else None
                        ),
                    }
                )
            packets.append(
                {
                    "schema": PACKET_SCHEMA,
                    "reviewer_id": rid,
                    "condition": condition,
                    "status": "AWAITING_REAL_HUMAN_DECISIONS",
                    "source_inspection_required": True,
                    "cases": shown,
                }
            )
    # If a language only has one allocated arm, disallow a causal comparison.
    coverage: dict[str, dict[str, int]] = {}
    for lang in {"nl", "fr"}:
        if lang in {c["language"] for c in cases}:
            coverage[lang] = {
                arm: len(
                    {
                        a["reviewer_id"]
                        for a in assignments
                        if a["condition"] == arm and cases_by_id[a["case_id"]]["language"] == lang
                    }
                )
                for arm in CONDITIONS
            }
    ready = bool(coverage) and all(all(n >= 2 for n in arms.values()) for arms in coverage.values())
    manifest = {
        "schema": ASSIGNMENTS_SCHEMA,
        "assignment_seed_sha256": hashlib.sha256(seed.encode()).hexdigest(),
        "assignment_count": len(assignments),
        "reviewer_count": len(reviewer_languages),
        "cases": [
            {
                "case_id": c["case_id"],
                "language": c["language"],
                "source_version_id": c["source_version_id"],
                "source_sha256": c["source_sha256"],
                "physical_pdf_page": c["physical_pdf_page"],
            }
            for c in cases
        ],
        "assignments": assignments,
        "per_language_reviewers_per_arm": coverage,
        "balanced_for_descriptive_arm_comparison": ready,
        "independently_adjudicated": False,
        "actual_human_results": False,
        "note": "Pseudonyms and trial timestamps are not identities or signed attestations.",
    }
    return packets, manifest


def _gold_labels(gold: dict[str, Any], manifest: dict[str, Any]) -> dict[str, str]:
    _require(gold.get("schema") == GOLD_SCHEMA, "independent labels schema required")
    entries = gold.get("cases")
    if not isinstance(entries, list):
        raise BenchmarkInvalid("gold case records required")
    gold_by_case: dict[str, str] = {}
    known = {c["case_id"]: c for c in manifest["cases"]}
    for record in entries:
        _require(isinstance(record, dict), "gold case must be record")
        cid = record.get("case_id")
        _require(cid in known and cid not in gold_by_case, "unknown/duplicate gold case")
        source = known[cid]
        for key in ("source_version_id", "source_sha256", "physical_pdf_page"):
            _require(record.get(key) == source[key], "gold source identity or page mismatch")
        labels = record.get("independent_labels")
        if not isinstance(labels, list) or len(labels) < 2:
            raise BenchmarkInvalid("two independent labels required")
        persons: set[str] = set()
        decisions: list[str] = []
        for row in labels:
            _require(isinstance(row, dict), "invalid label")
            reviewer = _bounded(row.get("adjudicator_pseudonym"), "adjudicator")
            _require(reviewer not in persons, "duplicate adjudicator")
            persons.add(reviewer)
            value = row.get("decision")
            _require(value in DECISIONS, "unrecognized gold decision")
            _bounded(row.get("source_rationale"), "independent source rationale")
            decisions.append(value)
        if len(set(decisions)) == 1:
            resolved = decisions[0]
        else:
            adjudication = record.get("resolution")
            _require(isinstance(adjudication, dict), "disagreement requires separate adjudication")
            resolved = adjudication.get("decision")
            _require(resolved in DECISIONS, "invalid adjudicated decision")
            _require(
                adjudication.get("adjudicator_pseudonym") not in persons,
                "resolver cannot be original assessor",
            )
            _bounded(adjudication.get("source_rationale"), "adjudication rationale")
        gold_by_case[cid] = resolved
    _require(set(gold_by_case) == set(known), "all case gold judgments required")
    return gold_by_case


def score_completed_trial(
    manifest: dict[str, Any], gold: dict[str, Any], submissions: dict[str, Any]
) -> dict[str, Any]:
    """Refuse incomplete/cherry-picked samples and mismatched immutable source IDs."""
    _require(manifest.get("schema") == ASSIGNMENTS_SCHEMA, "assignment manifest required")
    _require(manifest.get("balanced_for_descriptive_arm_comparison") is True, "arms not balanced")
    _require(submissions.get("schema") == SUBMISSIONS_SCHEMA, "submission schema required")
    labels = _gold_labels(gold, manifest)
    expected = {a["assignment_id"]: a for a in manifest["assignments"]}
    rows = submissions.get("decisions")
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise BenchmarkInvalid("full assignment census required")
    seen: set[str] = set()
    grouped: dict[str, list[tuple[dict[str, Any], str]]] = defaultdict(list)
    for row in rows:
        _require(isinstance(row, dict), "decision must be a record")
        aid = row.get("assignment_id")
        _require(aid in expected and aid not in seen, "duplicate or unassigned decision")
        seen.add(aid)
        assignment = expected[aid]
        for key in (
            "reviewer_id",
            "case_ref",
            "condition",
            "source_version_id",
            "source_sha256",
            "physical_pdf_page",
        ):
            _require(row.get(key) == assignment[key], f"decision {key} mismatch")
        _require(row.get("decision") in DECISIONS, "no human decision")
        _require(
            type(row.get("elapsed_ms")) is int and 100 <= row["elapsed_ms"] <= 3_600_000, "invalid timing"
        )
        _require(row.get("inspected_original") is True, "original source inspection not attested")
        _bounded(row.get("rationale"), "reviewer justification", 2000)
        confidence = row.get("confidence")
        _require(type(confidence) is int and 1 <= confidence <= 5, "confidence 1–5 required")
        helpful = row.get("warning_helpful")
        _require(
            (helpful is None or type(helpful) is bool)
            and (assignment["condition"] == "guarded_term_warnings" or helpful is None),
            "warning helpfulness unsupported",
        )
        grouped[assignment["condition"]].append((row, labels[assignment["case_id"]]))
    _require(set(seen) == set(expected), "missing decisions")
    result: dict[str, Any] = {}
    for arm in CONDITIONS:
        sample = grouped[arm]
        _require(sample, f"arm empty: {arm}")
        unsupported = [(d, gold_state) for d, gold_state in sample if gold_state != "SUPPORTED"]
        contradictions = [(d, state) for d, state in sample if state == "CONTRADICTED"]
        false = [(d, g) for d, g in unsupported if d["decision"] == "SUPPORTED"]
        missed = [(d, g) for d, g in contradictions if d["decision"] != "CONTRADICTED"]
        by_case: dict[str, list[str]] = defaultdict(list)
        for row, _gold_state in sample:
            by_case[expected[row["assignment_id"]]["case_id"]].append(row["decision"])
        agreement_pairs = [
            left == right
            for decisions in by_case.values()
            for left, right in itertools.combinations(decisions, 2)
        ]
        helpful = [d["warning_helpful"] for d, _ in sample if d["warning_helpful"] is not None]
        result[arm] = {
            "decisions": len(sample),
            "unique_reviewers": len({d["reviewer_id"] for d, _ in sample}),
            "false_confirmations": len(false),
            "unsupported_cases_reviewed": len(unsupported),
            "false_confirmation_rate": len(false) / len(unsupported) if unsupported else None,
            "missed_contradictions": len(missed),
            "contradictions_reviewed": len(contradictions),
            "missed_contradiction_rate": (len(missed) / len(contradictions) if contradictions else None),
            "median_seconds_per_decision": statistics.median(d["elapsed_ms"] / 1000 for d, _ in sample),
            "exact_decision_agreement_pairs": sum(agreement_pairs),
            "total_decision_agreement_pairs": len(agreement_pairs),
            "exact_reviewer_agreement": (
                sum(agreement_pairs) / len(agreement_pairs) if agreement_pairs else None
            ),
            "warning_helpful_responses": len(helpful),
            "warning_helpful_share": (sum(helpful) / len(helpful) if helpful else None),
            "false_supported_mean_confidence": (
                statistics.mean(d["confidence"] for d, _ in false) if false else None
            ),
        }
    improvement = result["standard_interface"]["false_confirmation_rate"]
    guarded = result["guarded_term_warnings"]["false_confirmation_rate"]
    return {
        "schema": RESULTS_SCHEMA,
        "experiment_type": "two_arm_descriptive_nonrandomized_outcome_analysis",
        "human_data_submitted": True,
        "identity_and_time_independently_authenticated": False,
        "gold_adjudicators_independently_authenticated": False,
        "source_rights_independently_verified": False,
        "causal_effect_established": False,
        "nli_tested": False,
        "conditions": result,
        "false_confirmation_rate_difference_standard_minus_guarded": (
            improvement - guarded if improvement is not None and guarded is not None else None
        ),
        "interpretation": (
            "Descriptive, self-reported results only. No causal or practitioner-accuracy "
            "claim without independently verified labels, identities, source bytes, "
            "counterbalanced study execution and statistical review."
        ),
    }
