"""Follow-ups to the representation gate: scoping, normalization, visibility."""
import random
from dataclasses import replace

import pytest

from application.litigation.brief_checks import CitationCheckState
from application.litigation.representation_fidelity import (
    RepresentationComparison,
    RepresentationState,
    normalize_for_comparison,
)


def comparison(**changes):
    base = RepresentationComparison("a" * 64, "rep-1", 1, "b" * 64,
                                    "EUR 1000 1200", "EUR 1000 1200", True, False)
    return replace(base, **changes)


@pytest.mark.parametrize("extracted,visual", [
    ("of\ufb01ce", "office"),
    ("pay\u00a0ment due", "pay ment due"),
    ("pay\u00adment", "payment"),
    ("EUR   1200\n", "EUR 1200"),
])
def test_extraction_noise_is_not_a_conflict(extracted, visual):
    result = comparison(extracted_text=extracted, visual_text=visual)
    assert result.state is RepresentationState.NOT_ASSESSED


@pytest.mark.parametrize("extracted,visual", [
    ("EUR 1200", "EUR 1\u200b200"),
    ("EUR 1200", "EUR \uff11\uff12\uff10\uff10"),
    ("EUR 1000", "EUR 1200"),
])
def test_lookalike_and_hidden_characters_stay_conflicts(extracted, visual):
    result = comparison(extracted_text=extracted, visual_text=visual)
    assert result.state is RepresentationState.REPRESENTATION_CONFLICT


def test_normalization_is_idempotent_and_minimal():
    text = "of\ufb01ce  pay\u00adment"
    once = normalize_for_comparison(text)
    assert once == "office payment"
    assert normalize_for_comparison(once) == once


def test_covers_whole_page_defaults_true_and_must_be_bool():
    assert comparison().covers_whole_page is True
    with pytest.raises(ValueError):
        comparison(covers_whole_page="no")


def test_unlocated_regional_conflict_still_blocks_unrelated_quote():
    from tests.test_litigation_m2_brief_checks import check, rig

    brief, register, previews = rig()
    preview = previews[0]
    item = comparison(original_sha256=preview.row.original_sha256,
                      meaning_bearing_edit=True, covers_whole_page=False)
    report = check(brief, register, (replace(preview, representation_comparisons=(item,)),))
    obs = report.observations[0]
    assert obs.state is CitationCheckState.REPRESENTATION_CONFLICT
    assert obs.visual_comparison_supplied is True
    assert obs.visual_coverage == "unknown"
    assert report.exact_without_visual_comparison_count == 0


def test_regional_comparison_overlapping_the_quote_still_blocks():
    from tests.test_litigation_m2_brief_checks import check, rig

    brief, register, previews = rig()
    preview = previews[0]
    item = comparison(original_sha256=preview.row.original_sha256,
                      extracted_text="Le paiement est d\u00fb.", visual_text="Le paiement",
                      covers_whole_page=False)
    report = check(brief, register, (replace(preview, representation_comparisons=(item,)),))
    obs = report.observations[0]
    assert obs.state is CitationCheckState.REPRESENTATION_CONFLICT
    assert obs.visual_comparison_supplied is True
    assert report.exact_count == 0


def test_whole_page_comparison_keeps_blocking_every_quote():
    from tests.test_litigation_m2_brief_checks import check, rig

    brief, register, previews = rig()
    preview = previews[0]
    item = comparison(original_sha256=preview.row.original_sha256,
                      meaning_bearing_edit=True)
    report = check(brief, register, (replace(preview, representation_comparisons=(item,)),))
    assert report.observations[0].state is CitationCheckState.REPRESENTATION_CONFLICT


def test_clean_supplied_comparison_is_visible_and_not_counted_as_missing():
    from tests.test_litigation_m2_brief_checks import check, rig

    brief, register, previews = rig()
    preview = previews[0]
    item = comparison(original_sha256=preview.row.original_sha256)
    report = check(brief, register, (replace(preview, representation_comparisons=(item,)),))
    assert report.observations[0].state is CitationCheckState.EXACT_MATCH
    assert report.observations[0].visual_comparison_supplied is True
    assert report.exact_without_visual_comparison_count == 0


def test_no_comparison_leaves_exact_match_visibly_unassessed():
    from tests.test_litigation_m2_brief_checks import check

    report = check()
    assert report.observations[0].state is CitationCheckState.EXACT_MATCH
    assert report.observations[0].visual_comparison_supplied is False
    assert report.exact_without_visual_comparison_count == 1


def _reference_detector(image, bounds):
    left, top, right, bottom = bounds
    width, height = right - left, bottom - top
    if width < 8 or height < 8:
        return False
    gray = image.crop(bounds).convert("L")
    for y in range(height // 3, 2 * height // 3 + 1):
        longest = current = 0
        for x in range(width):
            pixel = gray.getpixel((x, y))
            current = current + 1 if isinstance(pixel, int) and pixel < 100 else 0
            longest = max(longest, current)
        if longest * 5 >= width * 4:
            return True
    return False


def test_fast_detector_matches_the_original_pixel_loop():
    from PIL import Image, ImageDraw

    from infrastructure.parsers.visual_edit_candidates import has_midline_candidate

    rng = random.Random(7)
    seen = set()
    for _ in range(60):
        image = Image.new("RGB", (120, 60), "white")
        draw = ImageDraw.Draw(image)
        for _ in range(rng.randint(0, 6)):
            y = rng.randint(0, 59)
            x0 = rng.randint(0, 100)
            draw.line((x0, y, min(119, x0 + rng.randint(5, 119)), y),
                      fill=rng.choice(["black", "red", "blue", "gray", "yellow"]))
        for _ in range(rng.randint(0, 20)):
            draw.point((rng.randint(0, 119), rng.randint(0, 59)), fill="black")
        bounds = (rng.randint(0, 20), rng.randint(0, 10), rng.randint(60, 120), rng.randint(30, 60))
        expected = _reference_detector(image, bounds)
        assert has_midline_candidate(image, bounds) is expected
        seen.add(expected)
    assert seen == {True, False}


def test_clean_regional_common_word_never_claims_quote_coverage():
    from dataclasses import asdict

    from tests.test_litigation_m2_brief_checks import check, rig

    brief, register, previews = rig()
    preview = previews[0]
    item = comparison(original_sha256=preview.row.original_sha256,
                      extracted_text="Le", visual_text="Le", covers_whole_page=False)
    report = check(brief, register, (replace(preview, representation_comparisons=(item,)),))
    payload = asdict(report)
    obs = payload["observations"][0]
    assert obs["visual_comparison_supplied"] is True
    assert obs["visual_coverage"] == "unknown"
    assert obs["visual_assessment"] == "not_assessed"
    assert obs["fidelity_rules_version"] == "representation-gate-v2"
    assert payload["engine_version"] == "caseproof-literal-citation-v2"


def test_missing_visual_assessment_survives_serialization():
    from dataclasses import asdict

    from tests.test_litigation_m2_brief_checks import check

    obs = asdict(check())["observations"][0]
    assert obs["visual_comparison_supplied"] is False
    assert obs["visual_coverage"] == "not_supplied"
    assert obs["visual_assessment"] == "not_assessed"


def test_incomplete_extraction_does_not_claim_other_page_visual_coverage():
    from tests.test_litigation_m2_brief_checks import check, rig

    brief, register, previews = rig()
    preview = previews[0]
    item = comparison(original_sha256=preview.row.original_sha256, pdf_page=2,
                      meaning_bearing_edit=True)
    preview = replace(preview, row=replace(preview.row, warnings=("partial",)),
                      representation_comparisons=(item,))
    obs = check(brief, register, (preview,)).observations[0]
    assert obs.state is CitationCheckState.INCOMPLETE_EXTRACTION
    assert obs.visual_coverage == "not_supplied"
    assert obs.visual_assessment == "not_assessed"


def test_unlocated_page_conflict_gates_reference_without_quotation():
    from tests.test_litigation_m2_brief_checks import check, rig

    brief, register, previews = rig()
    brief = replace(brief, references=(replace(brief.references[0], exact_quote=None),))
    preview = previews[0]
    item = comparison(original_sha256=preview.row.original_sha256, meaning_bearing_edit=True)
    obs = check(brief, register, (replace(preview, representation_comparisons=(item,)),)).observations[0]
    assert obs.state is CitationCheckState.REPRESENTATION_CONFLICT


def test_regional_normalization_keeps_ligature_and_soft_hyphen_source_offsets():
    from application.litigation.representation_normalization import normalize_region

    raw = "of\ufb01ce pay\u00adment"
    normalized = normalize_region(raw)
    assert normalized.text == "office payment"
    assert normalized.raw_ranges[2] == normalized.raw_ranges[3] == (2, 3)
    assert raw[slice(normalized.raw_ranges[7][0], normalized.raw_ranges[-1][1])] == "pay\u00adment"


def test_disjoint_offsets_cannot_hide_stale_or_unbound_comparison():
    import pytest

    from application.litigation.brief_checks import DraftCheckError
    from tests.test_litigation_m2_brief_checks import check, rig

    brief, register, previews = rig()
    preview = previews[0]
    start = preview.text.index("Ensuite")
    item = comparison(original_sha256=preview.row.original_sha256,
                      text_start=start, text_end=len(preview.text),
                      extracted_text="forged offset text", visual_text="forged offset text")
    with pytest.raises(DraftCheckError, match="not bound"):
        check(brief, register, (replace(preview, representation_comparisons=(item,)),))
    stale = replace(item, original_sha256="d" * 64)
    obs = check(brief, register, (replace(preview, representation_comparisons=(stale,)),)).observations[0]
    assert obs.state is CitationCheckState.INCOMPLETE_EXTRACTION
