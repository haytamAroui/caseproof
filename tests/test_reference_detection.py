"""Conservative reference discovery regression fixtures."""

from domains.disputes.reference_detection import detect_exhibit_references


def test_dutch_and_french_references_preserve_offsets() -> None:
    text = "Zie stuk 12 en pièce n° 4bis, niet stuk 99."
    found = detect_exhibit_references(text, region="word/document.xml")
    assert [item.number for item in found] == ["12", "4bis", "99"]
    assert all(text[item.start:item.end] == item.raw for item in found)
    assert all(item.region == "word/document.xml" for item in found)


def test_no_implicit_exhibit_from_unqualified_number() -> None:
    assert not detect_exhibit_references("Article 12, page 4", region="page:1")


def test_region_must_be_present() -> None:
    import pytest

    with pytest.raises(ValueError):
        detect_exhibit_references("stuk 1", region="")
