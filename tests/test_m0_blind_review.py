"""Blind packet protects independent human review; no fabricated judgments."""
import json

from scripts.audit_m0_trilingual import DEFAULT_CORPUS
from scripts.m0_blind_review import generate, make_packet


def test_blind_packet_has_all_cases_without_expected_labels_or_author_rationale(tmp_path):
    result = generate(tmp_path)
    assert result["cases"] == 37
    pack = json.loads((tmp_path / "blind_cases.json").read_text(encoding="utf-8"))
    assert pack["review_status"] == "AWAITING_INDEPENDENT_HUMAN_REVIEW"
    assert len(pack["cases"]) == 37
    for case in pack["cases"]:
        assert "expected" not in case
        assert "expected_dimensions" not in case
        assert "review_basis" not in case
        assert "human_review_labels" not in case
        assert all("text_or_unavailable" in source for source in case["sources"])
    assert next(c for c in pack["cases"] if c["id"] == "NL_CLEAN_01")["inventory"]["status"] == (
        "not_defined_in_legacy_v2"
    )


def test_review_submission_has_no_human_or_owner_approval(tmp_path):
    generate(tmp_path)
    template = json.loads((tmp_path / "empty_review_submission.json").read_text(encoding="utf-8"))
    assert template["reviewer"]["real_name"] == ""
    assert template["reviewer"]["independence_and_conflicts_attested"] is False
    assert template["reviewer"]["credential_and_signed_attestation_evidence"] == ""
    assert all(case["independent_rationale"] == "" for case in template["cases"])
    assert template["submission_status"] == "EMPTY_UNREVIEWED_TEMPLATE"


def test_blind_packet_uses_pinned_corpus_and_does_not_modify_inputs():
    raw = DEFAULT_CORPUS.read_bytes()
    data = json.loads(raw)
    original = json.dumps(data, sort_keys=True)
    packet = make_packet(data, "a" * 64)
    assert packet["corpus_sha256"] == "a" * 64
    assert len(packet["cases"]) == 37
    assert json.dumps(data, sort_keys=True) == original
