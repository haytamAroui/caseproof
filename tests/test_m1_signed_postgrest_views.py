"""Offline checks for the genuine-signed-user PostgREST probe choreography."""
from __future__ import annotations

import pytest

from scripts.verify_m1_signed_postgrest_views import VIEWS, verify_signed_read_views


def test_genuinely_signed_empty_view_result_contract() -> None:
    visited: list[tuple[str, str]] = []

    def accepted(*, view: str, key: str, token: str) -> tuple[int, object]:
        assert key == "test-publishable"
        visited.append((view, token))
        if token in ("header.body.signatureA", "header.body.signatureB",
                     "header.body.signatureC"):
            return 200, []
        return 401, None

    verify_signed_read_views(
        tokens=("header.body.signatureA", "header.body.signatureB", "header.body.signatureC"),
        key="test-publishable", get=accepted,
    )
    assert len(visited) == 8
    assert set(x[0] for x in visited) == set(VIEWS)


@pytest.mark.parametrize("result", [(200, [{"case_id": "foreign"}]), (404, None), (401, None)])
def test_view_probe_fails_on_missing_view_or_any_visible_rows(
    result: tuple[int, object],
) -> None:
    def get(*, view: str, key: str, token: str) -> tuple[int, object]:
        return result

    with pytest.raises(AssertionError):
        verify_signed_read_views(
            tokens=("header.body.signatureA", "header.body.signatureB", "header.body.signatureC"),
            key="test-publishable", get=get,
        )


def test_view_probe_fails_when_invalid_signature_is_accepted() -> None:
    def get(*, view: str, key: str, token: str) -> tuple[int, object]:
        return 200, []

    with pytest.raises(AssertionError):
        verify_signed_read_views(
            tokens=("header.body.signatureA", "header.body.signatureB", "header.body.signatureC"),
            key="test-publishable", get=get,
        )


def test_reject_duplicate_auth_sessions() -> None:
    with pytest.raises(AssertionError):
        verify_signed_read_views(
            tokens=("duplicate", "duplicate", "different"),
            key="test-publishable",
            get=lambda **kwargs: (200, []),
        )
