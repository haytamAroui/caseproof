"""Signed-matter lawyer conditions inside the offline pack: an OPTIONAL, additive section.

Not an engine change: the legal-reference check engine marker and its observations are untouched, so packs
without this section replay and render byte for byte as before. Unlike the offline v6 conditions (local files,
every piece read), a signed matter has pieces that were not read. Each row therefore keeps pieces_not_read, and
the replay refuses an UNVERIFIED row that has any, a PASS anywhere, or a found row with the wrong reason.
The excerpts are integrity-checked (hash) and tied to the brief by replaying the anchors; they are NOT replayed
against source bytes, because the pack does not carry the matter's sources.
"""
from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from application.litigation.corpus import CorpusError
from application.litigation.lawyer_conditions import R_FOUND, R_NONE, anchors
from application.litigation.signed_conditions import R_PARTIAL, load_stored

FORMAT = "caseproof-signed-conditions-pack-v1"
NOTE = ("Conditions définies par l'avocat pour ce dossier : mots littéraux, sans synonymes ni lecture du sens. "
        "Un extrait contient un mot demandé, il ne montre pas que la condition est remplie. Les extraits viennent du "
        "texte stocké des sources lisibles, pas des pages d'origine vérifiées. Les pièces non lues sont listées.")


def build_section(spec_text: str, spec_sha256: str, revision: int, matches: Mapping[str, Any]) -> dict[str, Any]:
    section = {"format": FORMAT, "note": NOTE, "revision": revision, "spec_text": spec_text,
               "spec_sha256": spec_sha256, "anchors": [dict(a) for a in matches["anchors"]]}
    return section


def validate_section(brief_text: str, section: Any) -> dict[str, Any]:
    if (not isinstance(section, dict) or section.get("format") != FORMAT or section.get("note") != NOTE
            or set(section) != {"format", "note", "revision", "spec_text", "spec_sha256", "anchors"}
            or type(section["revision"]) is not int or not 1 <= section["revision"] <= 100000):
        raise CorpusError("signed conditions section invalid")
    spec = load_stored(section["spec_text"], section["spec_sha256"])
    expected = anchors(brief_text, spec) if spec["conditions"] else []
    rows = section["anchors"]
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise CorpusError("signed conditions do not replay from the brief")
    by_id = {c["id"]: c for c in spec["conditions"]}
    for n, (row, anchor) in enumerate(zip(rows, expected, strict=True), start=1):
        if (row.get("anchor_id") != f"condition-anchor-{n:02d}" or row.get("condition_id") != anchor["condition"]
                or row.get("sentence") != anchor["sentence"] or row.get("start") != anchor["start"]
                or row.get("end") != anchor["end"] or row.get("label") != by_id[anchor["condition"]]["label"]):
            raise CorpusError("signed condition anchor does not replay from the brief")
        found, not_read, read = row.get("found"), row.get("pieces_not_read"), row.get("pieces_read")
        if not isinstance(found, list) or not isinstance(not_read, list) or not isinstance(read, list):
            raise CorpusError("signed condition evidence invalid")
        terms = {t.casefold() for t in by_id[anchor["condition"]]["evidence"]}
        for f in found:
            if (hashlib.sha256(f["excerpt"].encode()).hexdigest() != f["excerpt_sha256"]
                    or f["term"].casefold() not in terms):
                raise CorpusError("signed condition excerpt inconsistent")
        status, reason = row.get("status"), row.get("reason")
        if found:
            ok = (status, reason) == ("UNDETERMINED", R_FOUND)
        elif not not_read and read:
            ok = (status, reason) == ("UNVERIFIED", R_NONE)
        else:
            ok = (status, reason) == ("UNDETERMINED", R_PARTIAL)
        if not ok:
            raise CorpusError("signed condition status does not follow from its evidence")
    return section
