"""S2-008a3: real disposable PostgreSQL joined-row -> typed locator round trip.

Run AFTER scripts.verify_s2_008a_database in the same CI service. Each read
uses a NEW psql process/connection. The DB has test-only evidence metadata;
the reference SQL has named DB-API placeholders and is executed through a
fixture-only psql substitution layer, not a production driver. Never pass
external strings into this fixture's SQL substitution function.
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Any
from uuid import UUID

from apps.api.evidence_locator_codec import ExpectedEvidenceParent
from apps.api.postgres_evidence_reader import (
    SQL_SELECT_EXACT_ANCHOR,
    EvidenceRowNotFound,
    UnverifiedEvidenceMetadata,
    get_exact_anchor_metadata,
)
from scripts.verify_s2_002_database import _run
from scripts.verify_s2_007_disposable_tenancy import _isolated_postgres_env
from scripts.verify_s2_008a_database import (
    ANCHOR,
    CASE,
    DOC,
    ORG,
)

_CASE = UUID(CASE)
_ORG = UUID(ORG)
_SOURCE_SHA = "a" * 64
_REP_SHA = "c" * 64
_ANCHOR = "span:1"
_FIXTURE_PARENT = ExpectedEvidenceParent(
    org_id=_ORG, case_id=_CASE,
    document_id="invoice/source-A", version_id="v1",
    representation_id="ocr-1",
    source_sha256_hex=_SOURCE_SHA,
    representation_sha256_hex=_REP_SHA,
)
_PLACEHOLDER = re.compile(r"%\(([a-z_]+)\)s")


class _DisposablePsqlReader:
    """Synthetic-only DI adapter: no connection pool, credentials or user input."""

    def __init__(self, env: dict[str, str]) -> None:
        self._env = env
        self._row: dict[str, Any] | None = None
        self.query_count = 0

    def execute(self, query: str, params: dict[str, str]) -> None:
        if query != SQL_SELECT_EXACT_ANCHOR:
            raise AssertionError("Only reviewed exact evidence read statement supported")
        expected_keys = {
            "org_id", "case_id", "anchor_id", "document_id", "version_id",
            "representation_id", "source_sha256_hex", "representation_sha256_hex",
        }
        if set(params) != expected_keys:
            raise AssertionError("Unreviewed SQL placeholder or query parameter")

        # Every value must be one of the exact hardcoded synthetic fixtures.
        approved = {
            "org_id": {str(_ORG)},
            "case_id": {str(_CASE), "aaaaaaaa-2121-4121-8121-aaaaaaaaaaaa"},
            "anchor_id": {_ANCHOR, "missing-anchor"},
            "document_id": {"invoice/source-A", "other-document"},
            "version_id": {"v1", "v2"},
            "representation_id": {"ocr-1", "ocr-2"},
            "source_sha256_hex": {_SOURCE_SHA, "f" * 64},
            "representation_sha256_hex": {_REP_SHA, "f" * 64},
        }
        if any(value not in approved[name] for name, value in params.items()):
            raise ValueError("Unsafe non-fixture PostgreSQL parameter")

        used: set[str] = set()

        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in expected_keys:
                raise AssertionError("Unexpected SQL parameter")
            used.add(key)
            # Literal values are fixed test-only allowed strings; production
            # MUST use true DB-API bind arguments, never this substitution.
            return "'" + params[key] + "'"

        rendered = _PLACEHOLDER.sub(repl, query).strip()
        if used != expected_keys or "%(" in rendered or ";" in rendered:
            raise AssertionError("Unreviewed SQL statement shape")
        command = (
            "begin transaction read only;\n"
            "select coalesce(row_to_json(result)::text, 'null') from (\n"
            + rendered + "\n) as result;\ncommit;"
        )
        response = _run(command, self._env)
        self._row = json.loads(response) if response and response != "null" else None
        self.query_count += 1

    def fetchone(self) -> dict[str, Any] | None:
        return self._row


def _expect_missing(reader: _DisposablePsqlReader, parent: ExpectedEvidenceParent,
                    name: str) -> None:
    try:
        get_exact_anchor_metadata(reader, expected=parent, anchor_id=_ANCHOR)
    except EvidenceRowNotFound:
        print(f"S2-008a3 {name}: PASS")
    else:
        raise AssertionError(f"{name} returned foreign or stale evidence")


def main() -> None:
    env = _isolated_postgres_env()
    if _run(
        "select count(*)::text from caseproof.s2_008a_anchors "
        f"where anchor_pk='{ANCHOR}' and org_id='{ORG}' and case_id='{CASE}';",
        env,
    ) != "1":
        raise RuntimeError("S2-008a3 requires fresh disposable S2-008a fixtures")

    first = _DisposablePsqlReader(env)
    record: UnverifiedEvidenceMetadata = get_exact_anchor_metadata(
        first, expected=_FIXTURE_PARENT, anchor_id=_ANCHOR
    )
    if (
        record.anchor.anchor_id != _ANCHOR
        or record.anchor.document_id != "invoice/source-A"
        or record.anchor.version_id != "v1"
        or record.anchor.representation_id != "ocr-1"
        or record.anchor.locator.start != 0  # type: ignore[union-attr]
        or record.anchor.locator.end != 10  # type: ignore[union-attr]
        or record.eligibility_established
    ):
        raise AssertionError("Read-only PostgreSQL round-trip did not preserve locator")
    print("S2-008a3 typed KRN locator reconstructed from real PostgreSQL JSONB: PASS")

    # A second new psql connection sees the same exact immutable locator.
    second = _DisposablePsqlReader(env)
    again = get_exact_anchor_metadata(
        second, expected=_FIXTURE_PARENT, anchor_id=_ANCHOR
    )
    if second.query_count != 1 or again != record:
        raise AssertionError("New connection/restart changed immutable locator")
    print("S2-008a3 independent connection/restart reconstruction: PASS")

    _expect_missing(
        _DisposablePsqlReader(env),
        replace(_FIXTURE_PARENT, case_id=UUID("aaaaaaaa-2121-4121-8121-aaaaaaaaaaaa")),
        "same-organization foreign case masked",
    )
    _expect_missing(
        _DisposablePsqlReader(env),
        replace(_FIXTURE_PARENT, source_sha256_hex="f" * 64),
        "stale source digest masked",
    )
    _expect_missing(
        _DisposablePsqlReader(env),
        replace(_FIXTURE_PARENT, representation_id="ocr-2"),
        "different representation ID masked",
    )
    _expect_missing(
        _DisposablePsqlReader(env),
        replace(_FIXTURE_PARENT, version_id="v2"),
        "stale source version masked",
    )
    print("S2-008a3_DISPOSABLE_POSTGRES_READER_PASSED")


if __name__ == "__main__":
    main()
