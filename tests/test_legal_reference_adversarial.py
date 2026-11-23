"""Adversarial regressions from an external review of the delivered pilot (synthetic corpus text).

Each case names the failure that review reported against the earlier engine.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from application.litigation.corpus import CORPUS_FORMAT_VERSION, CorpusError, load_corpus
from application.litigation.offline_legal_pack import verify_legal_pack
from apps.api.offline_docx_check import check_offline_docx
from tests.signed_composed_rig import docx_without_custom_xml

ARTICLE = ("Hormis les cas où la loi en dispose autrement, la preuve doit être rapportée "
           "avec un degré raisonnable de certitude.")
PAGE = "Art. 8.4. Autre. Texte voisin.\nArt. 8.5. Règle générale - preuve certaine " + ARTICLE + "\nArt. 8.6. Suite."
DERIVED = "Art. 8.5. Règle générale - preuve certaine " + ARTICLE


def corpus(tmp_path: Path, derived: str = DERIVED, page: str = PAGE, body: str = "Hormis les cas") -> Path:
    d = tmp_path / "c"
    d.mkdir(exist_ok=True)
    (d / "capture.txt").write_text(page)
    (d / "art.txt").write_text(derived)
    entry = {"act": "be-civ", "article": "8.5", "language": "fr", "version": "v1",
             "source_uri": "urn:synthetic:capture", "acquired_at": "2026-11-23", "consolidated": True,
             "original_file": "capture.txt", "derived_file": "art.txt",
             "original_sha256": hashlib.sha256(page.encode()).hexdigest(), "body_start": body,
             "source_artifact_kind": "official_text_capture"}
    lines = ["format = " + json.dumps(CORPUS_FORMAT_VERSION), "[[publication]]"]
    lines += [k + " = " + (str(v).lower() if isinstance(v, bool) else json.dumps(v)) for k, v in entry.items()]
    (d / "corpus-manifest.toml").write_text("\n".join(lines))
    (d / "act-aliases.toml").write_text('[act_aliases]\n"C.civ." = "be-civ"\n[chosen_versions]\n"be-civ" = "v1"\n')
    return d


def run(tmp_path: Path, *paragraphs: str, **corpus_args: str):
    path = tmp_path / "b.docx"
    path.write_bytes(docx_without_custom_xml(list(paragraphs)))
    raw, cp = check_offline_docx(docx=path, corpus=corpus(tmp_path, **corpus_args))
    return verify_legal_pack(raw, expected_sha256=cp)["references"]


def verdict(refs, i=0):
    return refs[i]["status"], refs[i]["reason"]


def test_derived_text_must_occur_in_preserved_original(tmp_path):
    """Reviewer appended a false sentence to the derived file, original hash unchanged."""
    tampered = DERIVED + " La preuve est toujours inutile."
    report = load_corpus(corpus(tmp_path, tampered))
    assert not report.records and any("does not occur" in str(f) for f in report.failures)
    path = tmp_path / "b.docx"
    path.write_bytes(docx_without_custom_xml(["Article 8.5 du Code civil : « La preuve est toujours inutile. »"]))
    with pytest.raises(CorpusError):
        check_offline_docx(docx=path, corpus=corpus(tmp_path, tampered))


UNATTESTED = "quotation_starts_at_declared_body_start_not_attested"


def test_exact_full_quote_from_declared_body_start_is_left_to_a_human(tmp_path):
    """The declared body_start is preparer metadata: it never yields a PASS by itself (v3)."""
    assert verdict(run(tmp_path, f"Article 8.5 du Code civil : « {ARTICLE} »")) == ("UNDETERMINED", UNATTESTED)


def test_quote_from_the_article_start_passes(tmp_path):
    assert verdict(run(tmp_path, f"Article 8.5 du Code civil : « {DERIVED} »"))[0] == "PASS"


def test_dropped_reservation_is_not_a_pass(tmp_path):
    rest = "la preuve doit être rapportée avec un degré raisonnable de certitude."
    status, reason = verdict(run(tmp_path, f"Article 8.5 du Code civil : « {rest} »"))
    assert (status, reason) == ("UNDETERMINED", "quotation_partial_excerpt_review_required")


def test_midword_fragment_is_not_a_pass(tmp_path):
    status, reason = verdict(run(tmp_path, "Article 8.5 du Code civil : « preuve doit être rapportée avec un degré raisonnable de certit »"))
    assert status == "UNDETERMINED" and reason.startswith("quotation_")


@pytest.mark.parametrize("quote", [ARTICLE.replace("Hormis", "HORMIS"), ARTICLE.replace(",", ";"),
                                   ARTICLE + " Sauf exception.", "Sauf " + ARTICLE.lower()])
def test_case_punctuation_and_additions_fail(tmp_path, quote):
    assert verdict(run(tmp_path, f"Article 8.5 du Code civil : « {quote} »"))[0] == "FAIL"


def test_whitespace_and_nbsp_are_layout_not_wording(tmp_path):
    spaced = DERIVED.replace("la preuve", "la\u00a0 preuve")
    assert verdict(run(tmp_path, f"Article 8.5 du Code civil : « {spaced} »"))[0] == "PASS"


@pytest.mark.parametrize("quote_marks", [('"', '"'), ("\u201c", "\u201d"), ("\u201e", "\u201d")])
def test_false_quote_in_other_quotation_marks_fails(tmp_path, quote_marks):
    left, right = quote_marks
    refs = run(tmp_path, f"Article 8.5 du Code civil : {left}La preuve est toujours inutile.{right}")
    assert verdict(refs)[0] == "FAIL"


def test_unquoted_claim_is_not_verified(tmp_path):
    refs = run(tmp_path, "La preuve est absolue et sans exception, article 8.5 du Code civil.")
    assert verdict(refs) == ("UNDETERMINED", "article_exists_in_corpus_no_quotation_checked_claim_not_verified")


def test_second_false_quote_under_same_reference_is_not_ignored(tmp_path):
    refs = run(tmp_path, f"Article 8.5 du Code civil : « {ARTICLE} » et aussi « La preuve est toujours inutile. »")
    assert any(r["reason"] == "quotation_not_bound_to_a_checked_reference"
               and "toujours inutile" in r["quote"] for r in refs)


def test_two_bound_quotes_one_false_is_fail(tmp_path):
    refs = run(tmp_path, f"« {ARTICLE} » (article 8.5 du Code civil) : « La preuve est toujours inutile. »")
    assert "FAIL" in {r["status"] for r in refs}


@pytest.mark.parametrize("text", ["Article 8.5 du Code civil, alinéa 99 : « X »", "Article 8.5, § 99 du Code civil : « X »",
                                  "L'alinéa 99 de l'article 8.5 du Code civil prévoit cela."])
def test_invented_subdivision_is_unverified(tmp_path, text):
    status, reason = verdict(run(tmp_path, text))
    assert (status, reason) == ("UNDETERMINED", "sub_article_locator_not_checked_in_corpus")


def test_adjacent_unspaced_second_reference_is_surfaced(tmp_path):
    refs = run(tmp_path, f"Article 8.5 du Code civil : « {ARTICLE} ». Art.8.6 du Code civil.")
    assert len(refs) >= 2 and any("8.6" in r["raw_text"] for r in refs)
    assert [r["status"] for r in refs if "8.6" in r["raw_text"]][0] in ("UNVERIFIED", "UNDETERMINED")


def test_quote_in_next_paragraph_does_not_attach_across_boundary(tmp_path):
    refs = run(tmp_path, "Article 8.5 du Code civil :", f"« {ARTICLE} »")
    assert not any(r["reason"] == "quotation_found_verbatim_in_corpus_article" for r in refs)
    assert any(r["reason"] == "quotation_not_bound_to_a_checked_reference" for r in refs)


def test_survivors_absent_article_unmapped_act_and_negation(tmp_path):
    assert verdict(run(tmp_path, "Article 8.6 du Code civil."))[0] == "UNVERIFIED"
    assert verdict(run(tmp_path, "Article 8.5 du Code judiciaire."))[0] == "UNDETERMINED"
    assert verdict(run(tmp_path, f"Article 8.5 du Code civil : « {ARTICLE.replace('doit', 'ne doit pas')} »"))[0] == "FAIL"


def _fails(tmp_path, **kw):
    report = load_corpus(corpus(tmp_path, **kw))
    return not report.records and bool(report.failures)


def test_derived_must_be_the_declared_article_span_not_any_text_in_the_capture(tmp_path):
    other = "Art. 8.4. Autre. Texte voisin."
    assert _fails(tmp_path, derived=other)  # another article's text declared as 8.5
    assert _fails(tmp_path, derived="Art. 8.5. Règle générale - preuve certaine Hormis les cas où la loi en dispose autrement,")  # truncated span
    # An injected sentence in the capture (hash updated alongside) is not part of a heading-bounded span.
    injected = PAGE.replace("Art. 8.6. Suite.", "Art. 8.5bis texte injecté. Art. 8.6. Suite.")
    assert _fails(tmp_path, derived=DERIVED + " Art. 8.5bis texte injecté.", page=injected)


def test_omitted_prefix_with_capitalised_remainder_is_not_a_pass(tmp_path):
    """The earlier engine treated a capital letter as a sentence start."""
    article = ("Hormis les cas où la loi en dispose autrement, la preuve est libre. "
               "Sauf Convention contraire, Le juge apprécie souverainement.")
    page = "Art. 8.4. Autre.\nArt. 8.5. Règle générale - preuve certaine " + article + "\nArt. 8.6. Suite."
    derived = "Art. 8.5. Règle générale - preuve certaine " + article
    refs = run(tmp_path, "Article 8.5 du Code civil : « Le juge apprécie souverainement. »", derived=derived, page=page)
    assert verdict(refs) == ("UNDETERMINED", "quotation_partial_excerpt_review_required")
    refs = run(tmp_path, "Article 8.5 du Code civil : « Sauf Convention contraire, Le juge apprécie souverainement. »",
               derived=derived, page=page)
    assert verdict(refs)[0] == "PASS"


def test_without_declared_body_start_first_sentence_is_not_assumed_complete(tmp_path):
    refs = run(tmp_path, f"Article 8.5 du Code civil : « {ARTICLE} »", body="")
    assert verdict(refs) == ("UNDETERMINED", "quotation_partial_excerpt_review_required")


def test_report_accounts_for_every_quotation_and_labels_scope(tmp_path):
    import io
    from zipfile import ZipFile
    path = tmp_path / "b.docx"
    path.write_bytes(docx_without_custom_xml([
        f"Article 8.5 du Code civil : « {DERIVED} » et « La preuve est toujours inutile. »", "« Citation orpheline. »"]))
    raw, cp = check_offline_docx(docx=path, corpus=corpus(tmp_path))
    refs = verify_legal_pack(raw, expected_sha256=cp)["references"]
    assert sorted(r["quote"] for r in refs if r["quote"]) == sorted(
        [DERIVED, "La preuve est toujours inutile.", "Citation orpheline."])
    html = ZipFile(io.BytesIO(raw)).read("report.html").decode()
    assert "Citations entre guillemets dans le Word : 3. Citations avec un constat visible ci-dessous : 3" in html
    assert "Contexte, réserves, portée et applicabilité non évalués" in html and "Moteur de contrôle strict (v3)" in html


def test_moving_body_start_alone_never_turns_an_omitted_reserve_into_pass(tmp_path):
    """Audit: a manifest copy with only body_start moved must not give PASS for a quote that drops the reserve."""
    omitted = "Article 8.5 du Code civil : « la preuve doit être rapportée avec un degré raisonnable de certitude. »"
    for body in ("Hormis les cas", "la preuve doit être rapportée", "avec un degré"):
        status, reason = verdict(run(tmp_path, omitted, body=body))
        assert status == "UNDETERMINED", (body, status, reason)


def _docx(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "x.docx"
    p.write_bytes(docx_without_custom_xml([text]))
    return p


def test_signed_service_and_offline_check_give_identical_findings_for_the_same_word(tmp_path, monkeypatch):
    """Audit: same Word text, same corpus -> same findings on the signed service and the offline path."""
    from types import SimpleNamespace

    from application.litigation.legal_references import load_corpus_config
    from apps.api import litigation_check_service as svc

    paragraphs = [f"Article 8.5 du Code civil : « {ARTICLE} ». Article 8.5 du Code civil : ‘la preuve est toujours inutile’.",
                  "Article 8.5 du Code civil : « la preuve doit être rapportée avec un degré raisonnable de certitude. »"]
    path = tmp_path / "p.docx"
    path.write_bytes(docx_without_custom_xml(paragraphs))
    cdir = corpus(tmp_path)
    raw, cp = check_offline_docx(docx=path, corpus=cdir)
    offline = [(r["status"], r["reason"], r["quote"]) for r in verify_legal_pack(raw, expected_sha256=cp)["references"]]

    config = load_corpus_config(cdir)
    from apps.api.offline_docx_check import parse_docx
    text = parse_docx(path.read_bytes())["text"]
    seen: dict[str, object] = {}
    real = svc.check_legal_references

    def spy(*a, **k):
        seen.update(k)
        out = real(*a, **k)
        seen["obs"] = [(o.status.value, o.reason, o.quote) for o in out]
        raise RuntimeError("stop after the legal step")

    monkeypatch.setattr(svc, "check_legal_references", spy)
    checker = svc.AuthorizedLitigationChecker.__new__(svc.AuthorizedLitigationChecker)
    checker.legal_corpus_for = lambda _case: config
    checker.store = SimpleNamespace(load_bundle=lambda **_: svc.CheckBundle.__new__(svc.CheckBundle))
    monkeypatch.setattr(svc.AuthorizedLitigationChecker, "_verified", lambda self, b: None)
    monkeypatch.setattr(svc.AuthorizedLitigationChecker, "_scope", lambda self, s, c: SimpleNamespace(case_id=c))
    bundle = SimpleNamespace(representation=SimpleNamespace(text=text, brief=SimpleNamespace(version_id="v")),
                             previews=())
    monkeypatch.setattr(svc, "CheckBundle", SimpleNamespace)
    checker.store = SimpleNamespace(load_bundle=lambda **_: bundle)
    with pytest.raises(Exception):  # noqa: B017, PT011 - the spy aborts after the legal step on purpose
        checker.check(bearer="t", case_id="c", brief_version_id="v")
    assert seen["strict"] is True and seen["v3"] is True
    assert seen["obs"] == offline
