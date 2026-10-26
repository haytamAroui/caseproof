"""Malformed model fields remain rejected and diagnostics never echo their contents."""
from dataclasses import replace

import pytest

from application.extraction.pipeline import SYSTEM, check_atom
from scripts.verify_live_requesty_litigation import (
    FIXTURES,
    SmokeLiteralPolicy,
    request_for,
)

REQ = request_for(FIXTURES[0])
RAW = {
    "entity_id": "E1", "source_id": REQ.sources[0].source_id,
    "quote": FIXTURES[0].text, "statement": "Synthetic observation",
    "signal": "amount_mentioned", "slot": "amount_mentioned",
    "value": "125,00", "polarity": "affirmative", "relation": "supports",
}


@pytest.mark.parametrize("field", sorted(RAW))
def test_missing_required_field_remains_rejected(field):
    raw = {k: v for k, v in RAW.items() if k != field}
    atom = check_atom(raw, REQ, SmokeLiteralPolicy(), "test", "2026-10-26T00:00:00+00:00")
    assert atom.state == "rejected" and atom.reason == "invalid_atom_schema"
    assert "missing_" + field in atom.schema_issues


@pytest.mark.parametrize("bad", [125, None, {}, [], True])
def test_value_is_never_coerced_into_a_string(bad):
    atom = check_atom({**RAW, "value": bad}, REQ, SmokeLiteralPolicy(), "test", "now")
    assert atom.state == "rejected"
    assert atom.schema_issues == ("non_string_value",)


def test_untrusted_keys_values_and_enums_are_not_logged_in_diagnostics():
    for raw, expected in (
        ({**RAW, "PRIVATE-KEY": "PRIVATE-VALUE"}, ("extra_fields",)),
        ({**RAW, "polarity": "PRIVATE-VALUE"}, ("invalid_enum",)),
        ({**RAW, "statement": ""}, ("empty_statement",)),
    ):
        atom = check_atom(raw, REQ, SmokeLiteralPolicy(), "test", "now")
        assert atom.state == "rejected"
        assert atom.schema_issues == expected
        assert "PRIVATE" not in repr(atom.schema_issues)


def test_valid_atom_and_default_report_compatibility():
    atom = check_atom(RAW, REQ, SmokeLiteralPolicy(), "test", "now")
    assert atom.state == "validated" and atom.schema_issues == ()
    assert replace(atom, state="needs_review").schema_issues == ()
    assert "nonempty JSON strings" in SYSTEM
    assert len(SYSTEM) <= 3000
