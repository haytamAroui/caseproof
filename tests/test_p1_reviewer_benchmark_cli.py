"""Real locally-generated PDF bytes for the P1 benchmark preparation boundary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pypdf import PdfWriter

from application.litigation.reviewer_benchmark import BenchmarkInvalid
from scripts.p1_reviewer_benchmark import prepare, score, verify_source_bytes


def write_pdf(path: Path, pages: int = 3) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    with path.open("wb") as stream:
        writer.write(stream)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def case_manifest(source_sha: str, *, source_pdf: str = "nl/exhibit.pdf") -> list[dict[str, object]]:
    return [
        {
            "case_id": "nl-synthetic-claim",
            "language": "nl",
            "source_version_id": "source-version-original-nl",
            "source_sha256": source_sha,
            "physical_pdf_page": 2,
            "source_pdf": source_pdf,
            "draft_claim": "Stuk 4 toont aan dat EUR 900 betaald is.",
            "anchored_passage": "Stuk 4 toont EUR 500.",
            "context_before": "De factuur heeft betrekking op een oud contract.",
            "context_after": "De bedragen zijn onder voorbehoud genoteerd.",
            "warnings": [{"kind": "amount", "term": "EUR 900"}],
            "synthetic_seed_truth": "must_never_be_in_participant_packet",
        }
    ]


def test_prepare_checks_original_pdf_sha_and_page_and_separates_private_mapping(
    tmp_path: Path,
) -> None:
    original_root = tmp_path / "source-bytes"
    digest = write_pdf(original_root / "nl" / "exhibit.pdf")
    case_file = tmp_path / "case-manifest.json"
    case_file.write_text(json.dumps({"cases": case_manifest(digest)}))
    reviewer_file = tmp_path / "reviewers.json"
    reviewers = {
        "reviewer-alpha": ["nl"],
        "reviewer-bravo": ["nl"],
        "reviewer-charlie": ["nl"],
        "reviewer-delta": ["nl"],
    }
    reviewer_file.write_text(json.dumps({"reviewer_languages": reviewers}))
    out = tmp_path / "blinded"
    status = prepare(
        cases_path=case_file,
        reviewers_path=reviewer_file,
        source_root=original_root,
        seed="synthetic-reproducible-assignment",
        destination=out,
    )
    assert status["human_results_collected"] is False
    assert status["source_pdf_digest_and_page_verified"] is True
    assert status["balanced_for_descriptive_arm_comparison"] is True
    assert status["assignments"] == 4
    packet_paths = sorted((out / "participant_packets").glob("*.json"))
    assert len(packet_paths) == 4
    text = "".join(path.read_text() for path in packet_paths)
    assert "synthetic_seed_truth" not in text
    assert "must_never_be_in_participant_packet" not in text
    assert "source-version-original-nl" in text
    assert digest in text
    assert "case_id" not in text
    assert "nl-synthetic-claim" not in text
    assert (out / "private_assignments.json").exists()
    assert (out / "private_assignments.json").stat().st_mode & 0o077 == 0
    templates = sorted((out / "empty_submissions").glob("*.json"))
    assert len(templates) == 4
    for path in templates:
        row = json.loads(path.read_text())
        assert row["status"] == "EMPTY_TEMPLATE_NOT_A_HUMAN_RESULT"
        assert row["decisions"][0]["decision"] is None
    with pytest.raises(FileExistsError):
        prepare(
            cases_path=case_file,
            reviewers_path=reviewer_file,
            source_root=original_root,
            seed="same-seed",
            destination=out,
        )


@pytest.mark.parametrize("mutation", ["wrong_hash", "wrong_page", "escape_root", "not_pdf"])
def test_missing_or_mismatched_original_fails_closed(tmp_path: Path, mutation: str) -> None:
    source = tmp_path / "sources"
    digest = write_pdf(source / "nl" / "exhibit.pdf")
    cases = case_manifest(digest)
    if mutation == "wrong_hash":
        cases[0]["source_sha256"] = "e" * 64
    elif mutation == "wrong_page":
        cases[0]["physical_pdf_page"] = 4
    elif mutation == "escape_root":
        cases[0]["source_pdf"] = "../../not-permitted.pdf"
    else:
        (source / "nl" / "exhibit.pdf").write_bytes(b"Not a PDF.")
    with pytest.raises(BenchmarkInvalid):
        verify_source_bytes(cases, source)


def test_empty_template_cannot_be_scored_as_a_real_trial(tmp_path: Path) -> None:
    original_root = tmp_path / "source-bytes"
    digest = write_pdf(original_root / "nl" / "exhibit.pdf")
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "cases.json").write_text(json.dumps({"cases": case_manifest(digest)}))
    (inputs / "reviewers.json").write_text(
        json.dumps(
            {
                "reviewer_languages": {
                    rid: ["nl"] for rid in ("researcher-a", "researcher-b", "researcher-c", "researcher-d")
                }
            }
        ),
    )
    out = tmp_path / "out"
    prepare(
        cases_path=inputs / "cases.json",
        reviewers_path=inputs / "reviewers.json",
        source_root=original_root,
        seed="synthetic-assignment",
        destination=out,
    )
    gold = inputs / "gold.json"
    gold.write_text(json.dumps({"schema": "caseproof-p1-independent-labels-v1", "cases": []}))
    blank = out / "empty_submissions" / "reviewer-01.json"
    with pytest.raises(BenchmarkInvalid):
        score(
            assignments_path=out / "private_assignments.json",
            gold_path=gold,
            submissions_path=blank,
            destination=tmp_path / "fake-human-results.json",
        )
    assert not (tmp_path / "fake-human-results.json").exists()
