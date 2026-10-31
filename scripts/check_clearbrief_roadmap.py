"""Guard the frozen Belgian pre-submission verification product against scope drift.

Kept at the original module path because CI and older developer commands already
refer to it. This is a documentation-consistency check, NOT proof of legal
correctness, deployed functionality, customer confidentiality, or commercial demand.
Run: python -m scripts.check_clearbrief_roadmap
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "roadmap": ROOT / "docs" / "ROADMAP.md",
    "workflow": ROOT / "docs" / "PRODUCT_WORKFLOW.md",
    "adr": ROOT / "docs" / "adr" / "0018-pre-submission-verification-freeze.md",
    "matrix": ROOT / "docs" / "FEATURE_DELIVERY_MATRIX.md",
    "word": ROOT / "docs" / "m3" / "WORD_INTEGRATION_ACCEPTANCE.md",
    "delivery": ROOT / "docs" / "m4" / "DELIVERY_ACCEPTANCE.md",
    "agents": ROOT / "AGENTS.md",
    "readme": ROOT / "README.md",
    "pre_m3": ROOT / "docs" / "contracts" / "PRE_M3_VERIFICATION_SPEC.md",
    "vision": ROOT / "docs" / "adr" / "0019-evidence-engine-and-first-market.md",
    "product_definition": ROOT / "docs" / "PRODUCT_DEFINITION_2026-10-31.md",
    "pilot_security": ROOT / "docs" / "security" / "PILOT_DATA_SECURITY_GATE.md",
}
FEATURE_ROW = re.compile(r"^\| (F\d{2}) \| ([^|]+) \|", re.MULTILINE)
EXPECTED_FEATURES = [f"F{i:02d}" for i in range(1, 43)]


def _contains_all(text: str, terms: tuple[str, ...], path: Path) -> None:
    missing = [term for term in terms if term not in text]
    if missing:
        raise AssertionError(f"{path}: missing product scope contracts: {missing}")


def main() -> None:
    documents: dict[str, str] = {}
    for label, path in FILES.items():
        if not path.is_file():
            raise AssertionError(f"missing authoritative scope document: {path}")
        documents[label] = path.read_text(encoding="utf-8")

    roadmap = documents["roadmap"]
    workflow = documents["workflow"]
    matrix = documents["matrix"]
    word = documents["word"]
    delivery = documents["delivery"]

    for n in range(7):
        _contains_all(roadmap, (f"## M{n} —",), FILES["roadmap"])
    _contains_all(
        roadmap,
        (
            "pre-submission", "Stuk/Pièce", "OCR_UNRELIABLE",
            "NOT_IN_INVENTORY", "CONFIRMED_SUPPORTED",
            "2 December 2027", "five weeks",
            "Word add-in is a", "MCP",
            "M3 — Independent web verification",
            "M4 — Reviewed document",
            "M5 — Five-week practitioner",
            "## Pre-M3 hard prerequisites",
            "## Pre-M5 hard prerequisites",
            "TRANSLATION_REVIEW_REQUIRED",
            "NOT_ASSESSED",
            "P3-01", "P3-02", "P3-03", "P3-04",
            "P5-01", "P5-02", "P5-03", "P5-04",
            "PILOT_DATA_SECURITY_GATE.md",
        ),
        FILES["roadmap"],
    )
    _contains_all(
        workflow,
        (
            "upload → verify → inspect source → review → export",
            "### 0. Sign in", "### 5. Inspect", "### 7. Recheck",
            "## One complete v1 launch acceptance",
            "## Interface independence",
            "OCR_UNRELIABLE", "NOT_IN_INVENTORY",
            "CONFIRMED_QUALIFIED", "MAPPED", "NOT_ASSESSED",
            "not required", "No court filing",
            "## Pre-M3 contractual readiness",
            "TRANSLATION_REVIEW_REQUIRED",
            "INVENTORY_MISSING",
            "regions_discovered",
            "PILOT_DATA_SECURITY_GATE.md",
            "P5-01..04",
        ),
        FILES["workflow"],
    )
    # Owner's 31 October vision and delivery refinement must not regress into
    # Word-first, generic legal research, a one-colour verdict or local-only.
    _contains_all(
        documents["vision"],
        ("independent post-assembly verification", "First commercial experience",
         "four separate dimensions", "web", "professional-secrecy",
         "A deterministic core is not a legal clearance"),
        FILES["vision"],
    )
    _contains_all(
        documents["product_definition"],
        ("independent pre-submission verification", "Priority 1 — M1–M4 browser",
         "EUIPO/BOIP", "field-level", "one frozen manifest"),
        FILES["product_definition"],
    )
    _contains_all(
        roadmap,
        ("independent post-assembly checking", "Current implementation checkpoint",
         "Immediate delivery sequence", "17 successful automatic post-merge checks",
         "SEC-01–16", "Word add-in is a"),
        FILES["roadmap"],
    )
    _contains_all(
        workflow,
        ("inventory/source confirmation", "independent post-assembly check",
         "cold reopen"),
        FILES["workflow"],
    )
    _contains_all(
        documents["pre_m3"],
        ("merged synthetic-path engineering implementation", "not complete M3 acceptance"),
        FILES["pre_m3"],
    )
    _contains_all(
        documents["adr"],
        ("Supersedes ADR 0016", "five weeks", "Word add-in", "human"),
        FILES["adr"],
    )
    _contains_all(
        delivery,
        ("without Microsoft Word installed", "MAPPED", "OCR", "actual DOCX"),
        FILES["delivery"],
    )
    _contains_all(
        word,
        ("not M3 or v1", "not v1", "M6", "not a", "existing"),
        FILES["word"],
    )
    _contains_all(
        documents["agents"],
        ("Current commercial hypothesis (ADR 0018", "pre-submission"),
        FILES["agents"],
    )
    _contains_all(
        documents["pre_m3"],
        (
            "P3-01", "P3-02", "P3-03", "P3-04",
            "TRANSLATION_REVIEW_REQUIRED",
            "OCR_LOCAL_WORKER", "UNPROCESSED_REGION",
            "INVENTORY_MISSING", "NOT_IN_INVENTORY",
            "M3 may start",
        ),
        FILES["pre_m3"],
    )
    _contains_all(
        documents["pilot_security"],
        tuple(f"SEC-{i:02d}" for i in range(1, 17))
        + ("OPEN / NOT APPROVED", "not automatically", "APPROVED FOR THIS EXACT PILOT"),
        FILES["pilot_security"],
    )
    _contains_all(
        documents["readme"],
        ("Frozen first commercial hypothesis", "Web workspace first"),
        FILES["readme"],
    )

    ids = [match.group(1) for match in FEATURE_ROW.finditer(matrix)]
    if ids != EXPECTED_FEATURES:
        raise AssertionError(
            f"historical matrix must retain exactly ordered F01-F42, got {ids!r}"
        )
    _contains_all(
        matrix,
        (
            "not a v1 product roadmap", "Current v1 applicability",
            "M3:** real signed independent browser",
            "F01 | Word task pane | M6 optional Word",
            "F35 | Cite Check Report | M4 v1 report",
        ),
        FILES["matrix"],
    )

    # These actively misleading past product commands must not reappear in the
    # authoritative roadmap/workflow. Historical documents may still quote them.
    forbidden = (
        "Word task pane is a mandatory first-product client",
        "Word workflow and validated deliverables are **mandatory**",
        "Frozen commercial product reference: Clearbrief-class",
        "finance-first ExceptionDesk",
        "M3 — Write with evidence",
    )
    for label in ("roadmap", "workflow"):
        for phrase in forbidden:
            if phrase in documents[label]:
                raise AssertionError(
                    f"{FILES[label]}: obsolete product direction reintroduced: {phrase}"
                )

    print("CASEPROOF_PRE_SUBMISSION_V1_SCOPE_AND_M0_TO_M6_CONTRACT_PASSED")


if __name__ == "__main__":
    main()
