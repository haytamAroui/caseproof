from dataclasses import replace

import pytest

from application.litigation.representation_fidelity import (
    RepresentationComparison,
    RepresentationState,
)


def comparison(**changes):
    base = RepresentationComparison("a" * 64, "rep-1", 1, "b" * 64,
                                    "EUR 1000 1200", "EUR 1000 1200", True, False)
    return replace(base, **changes)


def test_edit_is_conflict_even_when_ocr_text_is_identical():
    result = comparison(meaning_bearing_edit=True)
    assert result.state is RepresentationState.REPRESENTATION_CONFLICT
    contract = result.review_contract()
    assert contract["human_confirmation_required"] is True
    assert contract["crop_sha256"] == "b" * 64
    assert contract["semantic_support"] == "not_assessed"


def test_disagreement_never_selects_a_winner():
    assert comparison(visual_text="EUR 1200").state is RepresentationState.REPRESENTATION_CONFLICT
    assert comparison(visual_reliable=False).state is RepresentationState.OCR_UNRELIABLE
    assert comparison(visual_text="").state is RepresentationState.OCR_UNRELIABLE
    assert comparison().state is RepresentationState.NOT_ASSESSED


@pytest.mark.parametrize("changes", [
    {"pdf_page": True}, {"pdf_page": 0}, {"crop_sha256": ""},
    {"visual_reliable": "true"}, {"extracted_text": "a" * 4001},
])
def test_invalid_provenance_rejected(changes):
    with pytest.raises(ValueError):
        comparison(**changes)


def test_real_fixture_formats_preserve_trap():
    import io
    import zipfile

    from pypdf import PdfReader

    from tests.fixtures.factory import generate_fidelity_bundle

    files = {source.filename: source.content for source in generate_fidelity_bundle()}
    clean = PdfReader(io.BytesIO(files["clean.pdf"])).pages[0].extract_text()
    redline = PdfReader(io.BytesIO(files["redline.pdf"])).pages[0].extract_text()
    assert "1000" not in clean
    assert "1000 1200" in redline
    assert not PdfReader(io.BytesIO(files["redline-scan.pdf"])).pages[0].extract_text().strip()
    with zipfile.ZipFile(io.BytesIO(files["redline.docx"])) as archive:
        assert b"w:strike" in archive.read("word/document.xml")


def test_pixel_detector_flags_midline_but_not_clean_or_underline():
    from PIL import Image, ImageDraw, ImageFont

    from infrastructure.parsers.visual_edit_candidates import has_midline_candidate

    font = ImageFont.truetype("DejaVuSans.ttf", 44)
    clean = Image.new("RGB", (200, 100), "white")
    draw = ImageDraw.Draw(clean)
    draw.text((20, 20), "1000", fill="black", font=font)
    box = draw.textbbox((20, 20), "1000", font=font)
    assert not has_midline_candidate(clean, box)
    struck = clean.copy()
    ImageDraw.Draw(struck).line((box[0], (box[1] + box[3]) // 2,
                                box[2], (box[1] + box[3]) // 2), fill="black", width=3)
    assert has_midline_candidate(struck, box)
    underlined = clean.copy()
    ImageDraw.Draw(underlined).line((box[0], box[3] - 1, box[2], box[3] - 1), fill="black")
    assert not has_midline_candidate(underlined, box)


@pytest.mark.parametrize("reliable,edit,expected", [
    (True, True, "representation_conflict"), (False, False, "ocr_unreliable"),
])
def test_resolver_blocks_exact_match_and_retains_crop(reliable, edit, expected):
    from tests.test_litigation_m2_brief_checks import check, rig

    brief, register, previews = rig()
    preview = previews[0]
    item = comparison(original_sha256=preview.row.original_sha256,
                      visual_reliable=reliable, meaning_bearing_edit=edit,
                      extracted_text=preview.text, visual_text=preview.text,
                      text_start=0, text_end=len(preview.text), bbox=(0,0,100,30))
    report = check(brief, register, (replace(preview, representation_comparisons=(item,)),))
    assert report.observations[0].state.value == expected
    assert report.exact_count == 0 and report.unresolved_count == 1
    assert report.observations[0].representation_comparisons[0].crop_sha256 == "b" * 64


def test_stale_comparison_abstains_for_affected_reference():
    from tests.test_litigation_m2_brief_checks import check, rig

    brief, register, previews = rig()
    preview = previews[0]
    stale = comparison(extracted_text=preview.text, visual_text=preview.text,
                       text_start=0, text_end=len(preview.text))
    report = check(brief, register, (replace(preview, representation_comparisons=(stale,)),))
    assert report.observations[0].state.value == "incomplete_extraction"
    assert report.exact_count == 0


def test_unrelated_region_does_not_block_literal_quote():
    from tests.test_litigation_m2_brief_checks import check, rig

    brief, register, previews = rig()
    preview = previews[0]
    start = preview.text.index("Ensuite")
    unrelated = comparison(original_sha256=preview.row.original_sha256,
                           extracted_text=preview.text[start:], visual_text="changed footer",
                           text_start=start, text_end=len(preview.text))
    report = check(brief, register, (replace(preview, representation_comparisons=(unrelated,)),))
    assert report.observations[0].state.value == "exact_match"


def test_whitespace_and_canonical_unicode_do_not_hide_values_or_edits():
    assert comparison(extracted_text="é 1000", visual_text="e\u0301   1000 ").state.value == "not_assessed"
    assert comparison(extracted_text="1000", visual_text="1200").state.value == "representation_conflict"
    assert comparison(extracted_text="-1000", visual_text="1000").state.value == "representation_conflict"
    assert comparison(meaning_bearing_edit=True).state.value == "representation_conflict"
