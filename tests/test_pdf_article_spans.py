"""An article followed by a page footer is complete only if the footer is followed by a structural title."""
from __future__ import annotations

import pytest

from application.litigation.corpus import CorpusError, check_derived_binding
from scripts.build_book8_fr_corpus import spans

FOOT = "Page 3 de 8                      Copyright Moniteur belge        05-06-2025"
LAYER = (
    "  Art. 8.6. Titre\n  Premiere ligne du corps\n suite du corps.\n\n" + FOOT + "\n  Section 6. Suivante\n\n  Art. 8.7. Autre\n  Corps sept.\n"
    "  Art. 8.8. Coupe\n  Debut de l'article\n\n" + FOOT + "\n la fin sur la page suivante.\n\n  Art. 8.9. Fin\n  Corps neuf.\n")


def test_span_stops_before_footer_and_titles_and_the_binding_accepts_only_complete_articles():
    got = spans(LAYER)
    assert got["8.6"].endswith("suite du corps.") and "Section" not in got["8.6"]
    check_derived_binding("official_text_capture", LAYER.encode(), got["8.6"], "8.6", layer=True)
    with pytest.raises(CorpusError):  # footer then running text: the article continues, derived text is truncated
        check_derived_binding("official_text_capture", LAYER.encode(), got["8.8"], "8.8", layer=True)
    with pytest.raises(CorpusError):  # a plain capture never accepts a structural title as its end
        check_derived_binding("official_text_capture", LAYER.encode(), got["8.6"], "8.6")
