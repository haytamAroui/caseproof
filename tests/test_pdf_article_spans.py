"""Article boundaries in the publisher PDF layer: running page footers are elided, anything else must end an article cleanly."""
from __future__ import annotations

import pytest

from application.litigation.corpus import CorpusError, check_derived_binding
from scripts.build_book8_fr_corpus import spans

FOOT = "Page 3 de 8                      Copyright Moniteur belge        05-06-2025"
LAYER = (
    "  Art. 8.6. Titre\n  Premiere ligne du corps\n suite du corps.\n\n" + FOOT + "\n  Section 6. Suivante\n\n  Art. 8.7. Autre\n  Corps sept.\n"
    "  Art. 8.8. Coupe\n  Debut de l'article\n\n" + FOOT + "\n la fin sur la page suivante.\n\n  Art. 8.9. Fin\n  Corps neuf.\n")
ODD = ("  Art. 8.8. Coupe\n  Debut de l'article\n\nPage 3 de 8\n la fin sur la page suivante.\n\n  Art. 8.9. Fin\n  Corps neuf.\n")


def test_footer_at_the_end_is_not_part_of_the_article_and_a_footer_inside_is_elided():
    got = spans(LAYER)
    assert got["8.6"].endswith("suite du corps.") and "Section" not in got["8.6"] and "Copyright" not in got["8.6"]
    assert got["8.8"].endswith("la fin sur la page suivante.") and "Copyright" not in got["8.8"]
    for key in ("8.6", "8.7", "8.8"):
        check_derived_binding("official_text_capture", LAYER.encode(), got[key], key, layer=True)


def test_truncated_article_and_unknown_footer_shapes_are_refused():
    got = spans(LAYER)
    with pytest.raises(CorpusError):  # a plain capture never accepts a structural title as its end
        check_derived_binding("official_text_capture", LAYER.encode(), got["8.6"], "8.6")
    truncated = "Art. 8.8. Coupe Debut de l'article"
    with pytest.raises(CorpusError):  # the article continues after the footer: a prefix is not the article
        check_derived_binding("official_text_capture", LAYER.encode(), truncated, "8.8", layer=True)
    odd = spans(ODD)["8.8"]  # a footer shape we do not recognise ends the span: refused, never trimmed silently
    assert odd.endswith("Debut de l'article")
    with pytest.raises(CorpusError):
        check_derived_binding("official_text_capture", ODD.encode(), odd, "8.8", layer=True)


def test_corpus_pack_transport_roundtrips_a_publisher_pdf_corpus_with_its_text_layer(tmp_path):
    from application.litigation.legal_references import load_corpus_config
    from application.litigation.local_corpus_library import (
        LocalCorpusLibrary,
        decode_corpus_pack,
        encode_corpus_pack,
    )
    from tests.test_legal_reference_adversarial import pdf_corpus
    config = load_corpus_config(pdf_corpus(tmp_path))
    assert any(r.original_text_layer_sha256 for r in config.records)
    raw = encode_corpus_pack(config)
    assert decode_corpus_pack(raw).pack_sha256 == config.pack_sha256
    assert LocalCorpusLibrary(tmp_path / "lib").install(raw) == config.pack_sha256
