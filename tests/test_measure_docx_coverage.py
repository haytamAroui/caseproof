"""Task 6 measurement harness: synthetic control corpus validates the counts.

Synthetic files only: harness validation, never Belgian acceptance evidence.
"""
from __future__ import annotations

from pathlib import Path

from scripts.measure_docx_coverage import HARNESS_VERSION, FileRow, Report, build_report, render_markdown
from scripts.synthetic_docx_corpus import control_files


def _report(tmp_path: Path) -> Report:
    for name, payload in control_files().items():
        (tmp_path / name).write_bytes(payload)
    return build_report(tmp_path, "synthetic")


def _by_name(report: Report, name: str) -> FileRow:
    for entry in report["files"]:
        if entry["file"] == name:
            return entry
    raise AssertionError(f"missing {name}")


def test_every_control_file_is_measured(tmp_path: Path) -> None:
    report = _report(tmp_path)
    assert report["corpus_kind"] == "synthetic"
    assert report["harness_version"] == HARNESS_VERSION
    assert report["file_count"] == len(control_files())


def test_comments_declared_excluded(tmp_path: Path) -> None:
    entry = _by_name(_report(tmp_path), "with-comments.docx")
    assert entry["has_comments"] is True
    kinds = {r["kind"] for r in entry["regions"]}
    assert "COMMENT_EXCLUDED" in kinds


def test_tracked_revisions_declared_unresolved(tmp_path: Path) -> None:
    entry = _by_name(_report(tmp_path), "with-tracked-revisions.docx")
    assert entry["has_tracked_revisions"] is True
    statuses = {r["status"] for r in entry["regions"]}
    assert "REVISION_STATE_UNRESOLVED" in statuses


def test_hidden_text_and_structured_content_declared(tmp_path: Path) -> None:
    report = _report(tmp_path)
    assert _by_name(report, "with-hidden-text.docx")["has_hidden_text"] is True
    assert _by_name(report, "with-textbox.docx")["has_structured_content"] is True


def test_unknown_part_and_unreadable_package_fail_closed(tmp_path: Path) -> None:
    report = _report(tmp_path)
    unknown = _by_name(report, "with-unknown-part.docx")
    assert "UNKNOWN_WORD_PART" in {r["kind"] for r in unknown["regions"]}
    unreadable = _by_name(report, "unreadable.docx")
    assert unreadable["coverage_unknown"] is True
    assert unreadable["fail_closed_reason"] is not None


def test_plain_file_has_no_declared_omission(tmp_path: Path) -> None:
    entry = _by_name(_report(tmp_path), "plain.docx")
    assert entry["coverage_unknown"] is False
    assert {r["kind"] for r in entry["regions"]} == {"MAIN_BODY"}


def test_aggregate_counts_match_files(tmp_path: Path) -> None:
    report = _report(tmp_path)
    aggregate = report["aggregate"]
    assert aggregate["files_with_comments"] == 1
    assert aggregate["files_with_tracked_revisions"] == 1
    assert aggregate["files_coverage_unknown"] >= 1


def test_markdown_states_corpus_kind(tmp_path: Path) -> None:
    markdown = render_markdown(_report(tmp_path))
    assert "synthetic corpus" in markdown
    assert "NOT Belgian acceptance" in markdown
    assert "with-comments.docx" in markdown
