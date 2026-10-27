"""Keep the one Clearbrief-class product roadmap and F01–F42 ledger aligned.

Run this offline with `python -m scripts.check_clearbrief_roadmap`. The
check concerns **planning integrity only**, not implemented feature parity,
customer readiness, legal correctness or Microsoft Office compatibility.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROADMAP = ROOT / "docs" / "ROADMAP.md"
MATRIX = ROOT / "docs" / "FEATURE_DELIVERY_MATRIX.md"
WORKFLOW = ROOT / "docs" / "PRODUCT_WORKFLOW.md"
M3 = ROOT / "docs" / "m3" / "WORD_INTEGRATION_ACCEPTANCE.md"
M4 = ROOT / "docs" / "m4" / "DELIVERY_ACCEPTANCE.md"

FEATURE_ROW = re.compile(r"^\\| (F\\d{2}) \\| ([^|]+) \\|", re.MULTILINE)
EXPECTED = [f"F{i:02d}" for i in range(1, 43)]


def _check_feature_rows(text: str, *, path: Path) -> list[tuple[str, str]]:
    rows = [(key, name.strip()) for key, name in FEATURE_ROW.findall(text)]
    ids = [key for key, _ in rows]
    if ids != EXPECTED:
        raise AssertionError(
            f"{path}: exactly one ordered F01–F42 row required; got {ids!r}"
        )
    return rows


def main() -> None:
    for path in (ROADMAP, MATRIX, WORKFLOW, M3, M4):
        if not path.is_file():
            raise AssertionError(f"missing agreed product contract: {path}")

    roadmap = ROADMAP.read_text(encoding="utf-8")
    matrix = MATRIX.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    word = M3.read_text(encoding="utf-8")
    delivery = M4.read_text(encoding="utf-8")
    roadmap_rows = _check_feature_rows(roadmap, path=ROADMAP)
    matrix_rows = _check_feature_rows(matrix, path=MATRIX)
    if roadmap_rows != matrix_rows:
        raise AssertionError("feature IDs/names drifted between authoritative scope and ledger")

    for ref in (
        "FEATURE_DELIVERY_MATRIX.md",
        "m3/WORD_INTEGRATION_ACCEPTANCE.md",
        "m4/DELIVERY_ACCEPTANCE.md",
    ):
        if ref not in roadmap or ref not in workflow:
            raise AssertionError(f"missing product document link in roadmap/workflow: {ref}")

    # Guard against accidentally reframing the first sellable product as
    # a headless quote/date checker while putting Word and outputs off scope.
    for word_of_contract in (
        "Clearbrief-class",
        "Microsoft Word",
        "dynamic exhibits",
        "DOCX/PDF",
        "M1–M4",
    ):
        if word_of_contract not in roadmap:
            raise AssertionError(f"missing full-product launch contract: {word_of_contract}")

    if "not a commercial launch" not in matrix.lower() and (
        "not commercial completion" not in matrix.lower()
    ):
        raise AssertionError("ledger must distinguish M2 engineering from product launch")
    if "apps/word_addin/" not in matrix or "Not built" not in matrix:
        raise AssertionError("missing honest current Word feature status")
    if "not implemented" not in word.lower() or "not product-complete" not in delivery.lower():
        raise AssertionError("M3/M4 acceptance must not claim completed functionality")
    if "Minimum complete launch demonstration" not in workflow:
        raise AssertionError("full integrated user journey not specified")

    print("CLEARBRIEF_42_FEATURES_AND_M1_TO_M4_PRODUCT_CONTRACT_PASSED")


if __name__ == "__main__":
    main()
