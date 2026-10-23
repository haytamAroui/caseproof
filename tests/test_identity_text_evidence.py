"""Identity parsing must not silently normalize source coordinates."""

import pytest

from apps.api.disposable_text_evidence import identity_text_layout
from apps.api.evidence_locator_codec import StoredLocatorError
from apps.api.evidence_vault_protocol import MAX_REFERENCE_BYTES


def test_unicode_coordinates_count_codepoints_and_preserve_raw_source() -> None:
    text = "é\r\nCafe\u0301  1150 EUR"
    raw = text.encode("utf-8")
    result = identity_text_layout(raw)
    assert result == {"normalization": "none", "codepoints": len(text)}
    assert result["codepoints"] != len(raw)
    assert raw.decode("utf-8") == text


@pytest.mark.parametrize("data", [b"", b"\xff", "not bytes", b"x" * (MAX_REFERENCE_BYTES + 1)])
def test_unsupported_or_unbounded_identity_input_fails_closed(data) -> None:
    with pytest.raises(StoredLocatorError):
        identity_text_layout(data)
