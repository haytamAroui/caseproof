"""M2 first headless deterministic citation checks; no inferred legal outcomes."""
from dataclasses import replace
from hashlib import sha256

import pytest

from application.litigation.brief_checks import (
    CitationCheckState,
    DraftCheckError,
    DraftReference,
    VersionedBrief,
    check_brief_references,
)
from application.litigation.library import EvidencePreview, EvidenceRow
from domains.disputes.exhibits import ExhibitEntry, ExhibitPage, ExhibitRegister


def rig(*, duplicate=False, partial=False, ambiguous=False):
    quote = "Le paiement est dû."
    text = quote + (" Ensuite " + quote if duplicate else " Ensuite.")
    r = EvidenceRow("src-1", "doc-1", "version-1", sha256(b"original").hexdigest(),
                    "application/pdf", "partial" if partial else "ready",
                    "pdf-v1", "rep-1", (), ("needs_ocr",) if partial else ())
    preview = EvidencePreview(r, text, ((0, len(text), "pdf-page-0", 0),))
    entries = [ExhibitEntry("ex-1", "Pièce 1",
                            (ExhibitPage("src-1", "version-1", 1),),
                            ("Stuk 1",), confirmed=True)]
    if ambiguous:
        entries.append(ExhibitEntry("ex-2", "Pièce 2",
                                    (ExhibitPage("src-1", "version-1", 1),),
                                    ("Stuk 1",), confirmed=True))
    register = ExhibitRegister(4, tuple(entries))
    reference = DraftReference("ref-1", "Stuk 1", quote, 1)
    brief = VersionedBrief("case-a", "brief-v1", sha256(b"brief-original").hexdigest(), (reference,))
    return brief, register, (preview,)


def check(brief=None, register=None, previews=None):
    b,r,p=rig()
    return check_brief_references(
        brief=b if brief is None else brief,
        register=r if register is None else register,
        previews=p if previews is None else previews,
        authorized_case_id="case-a", authorized_register_revision=4,
    )


def test_french_quote_alias_matches_one_exact_source_page_without_legal_support():
    report = check()
    obs = report.observations[0]
    assert obs.state is CitationCheckState.EXACT_MATCH
    assert (obs.source_id, obs.source_version_id, obs.representation_id) == ("src-1", "version-1", "rep-1")
    assert (obs.text_start, obs.text_end) == (0, len("Le paiement est dû."))
    assert report.exact_count == 1 and report.mismatch_count == 0
    assert report.engine_version == "caseproof-literal-citation-v2"


def test_unmapped_label_never_defaults_to_first_exhibit():
    b,r,p=rig()
    new=replace(b, references=(replace(b.references[0], exhibit_label="Pièce 77"),))
    assert check(new,r,p).observations[0].state is CitationCheckState.REFERENCE_UNRESOLVED


def test_missing_quote_is_lexical_warning_not_semantic_contradiction():
    b,r,p=rig()
    new=replace(b, references=(replace(b.references[0], exact_quote="Jamais payé."),))
    report=check(new,r,p)
    assert report.observations[0].state is CitationCheckState.QUOTE_NOT_FOUND
    assert report.mismatch_count == 1


def test_ambiguous_alias_and_multiple_occurrences_require_review():
    b,r,p=rig(ambiguous=True)
    assert check(b,r,p).observations[0].state is CitationCheckState.REFERENCE_AMBIGUOUS
    b,r,p=rig(duplicate=True)
    assert check(b,r,p).observations[0].state is CitationCheckState.MULTIPLE_MATCHES


def test_missing_or_partial_source_is_unknown_not_mismatch():
    b,r,p=rig()
    assert check(b,r,()).observations[0].state is CitationCheckState.SOURCE_UNAVAILABLE
    b,r,p=rig(partial=True)
    assert check(b,r,p).observations[0].state is CitationCheckState.INCOMPLETE_EXTRACTION


def test_wrong_pdf_page_or_unmapped_pages_cannot_resolve_exact():
    b,r,p=rig()
    wrong=replace(b,references=(replace(b.references[0],pdf_page=2),))
    assert check(wrong,r,p).observations[0].state is CitationCheckState.PAGE_UNMAPPED
    wrong_span=replace(p[0],spans=((0,len(p[0].text),"paragraph",None),))
    assert check(b,r,(wrong_span,)).observations[0].state is CitationCheckState.QUOTE_NOT_FOUND


def test_cross_block_spanning_quote_does_not_fabricate_exact_anchor():
    b,r,p=rig()
    text=p[0].text
    first=text.index("dû.") + 1
    split=replace(p[0], spans=((0,first,"b1",0),(first,len(text),"b2",0)))
    assert check(b,r,(split,)).observations[0].state is CitationCheckState.QUOTE_NOT_FOUND


def test_partial_scan_and_different_case_fail_closed():
    b,r,p=rig()
    assert not check(b,r,()).evidence_scope_complete
    with pytest.raises(DraftCheckError,match="out-of-snapshot"):
        check_brief_references(brief=b,register=r,previews=p,
                              authorized_case_id="foreign",authorized_register_revision=4)
    with pytest.raises(DraftCheckError,match="out-of-snapshot"):
        check_brief_references(brief=b,register=r,previews=p,
                              authorized_case_id="case-a",authorized_register_revision=3)


def test_duplicate_source_version_inventory_is_rejected():
    b,r,p=rig()
    with pytest.raises(DraftCheckError,match="duplicate"):
        check(b,r,p+p)


def test_distinct_dutch_and_english_text_must_match_exact_not_translated():
    b,r,p=rig()
    variants=("De betaling is verschuldigd.","Payment is due.")
    for quote in variants:
        new=replace(b,references=(replace(b.references[0],exact_quote=quote),))
        assert check(new,r,p).observations[0].state is CitationCheckState.QUOTE_NOT_FOUND


def test_exhibit_physical_page_still_scopes_quote_when_draft_page_missing():
    brief, register, previews = rig()
    no_draft_page = replace(
        brief, references=(replace(brief.references[0], pdf_page=None),),
    )
    # Quote exists, but only on page 2 while confirmed exhibit maps page 1.
    source = replace(previews[0], spans=((0, len(previews[0].text), "pdf-page-1", 1),))
    report = check_brief_references(
        brief=no_draft_page, register=register, previews=(source,),
        authorized_case_id="case-a", authorized_register_revision=4,
    )
    assert report.observations[0].state is CitationCheckState.QUOTE_NOT_FOUND
