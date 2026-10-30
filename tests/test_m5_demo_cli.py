"""Offline M5 demo presentation contract: never imply global verification."""
from scripts.m5_demo_cli import dimensions, show


def test_dimensions_keep_semantics_unassessed(capsys):
    finding = {
        "literal": "Stuk 7, p. 12", "identity": "resolved",
        "page_mapping": "pdf_page_verified", "fidelity": "not_assessed",
        "support": "not_assessed", "ocr_uncertainty": "requires_human_confirmation",
        "ocr_crop": {"page_number": 1, "left": 10, "top": 20, "width": 50, "height": 30},
    }
    assert dimensions(finding) == (
        "RESOLVED", "PDF_PAGE_VERIFIED", "OCR_UNRELIABLE / NOT_ASSESSED", "NOT_ASSESSED"
    )
    show([finding], False)
    output = capsys.readouterr().out
    assert "Semantic Support: NOT_ASSESSED" in output
    assert "OCR candidate crop" in output
    assert "VERIFIED" not in output.replace("PDF_PAGE_VERIFIED", "")


def test_unknown_is_not_exact_match(capsys):
    show([{"literal": "Pièce 99", "identity": "not_in_inventory"}], False)
    output = capsys.readouterr().out
    assert "NOT_IN_INVENTORY" in output
    assert "EXACT_MATCH" not in output
