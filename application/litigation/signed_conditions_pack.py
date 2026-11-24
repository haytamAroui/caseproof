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
import re
from collections.abc import Mapping
from typing import Any

from application.litigation.corpus import CorpusError
from application.litigation.lawyer_conditions import R_FOUND, R_NONE, anchors
from application.litigation.signed_conditions import R_PARTIAL, load_stored

FORMAT = "caseproof-signed-conditions-pack-v1"
NOTE = ("Conditions définies par l'avocat pour ce dossier : mots littéraux, sans synonymes ni lecture du sens. "
        "Un extrait contient un mot demandé, il ne montre pas que la condition est remplie. Les extraits viennent du "
        "texte stocké des sources lisibles, pas des pages d'origine vérifiées. Les pièces non lues sont listées.")


def _inventory(previews: Any, labels: Mapping[str, str], readable: Any) -> list[dict[str, Any]]:
    inv = [{"source_id": p.row.source_id, "version_id": p.row.version_id, "original_sha256": p.row.original_sha256,
            "piece": labels.get(p.row.source_id) or f"source {p.row.source_id[:8]}", "read": bool(readable(p))}
           for p in previews]
    return sorted(inv, key=lambda r: (r["piece"], r["source_id"], r["version_id"]))


def _targeted(inventory: list[dict[str, Any]], pieces: list[str]) -> tuple[list[str], list[str], list[str]]:
    wanted = set(pieces)
    hit = [r for r in inventory if not wanted or r["piece"].lower() in wanted]
    known = {r["piece"].lower() for r in inventory}
    return (sorted(r["source_id"] for r in hit if r["read"]), sorted(r["source_id"] for r in hit if not r["read"]),
            sorted(w for w in wanted if w not in known))


_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")


def build_section(spec_text: str, spec_sha256: str, revision: int, matches: Mapping[str, Any],
                  spec: Mapping[str, Any], previews: Any, labels: Mapping[str, str], readable: Any,
                  events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    inventory = _inventory(previews, labels, readable)
    by_id = {c["id"]: c for c in spec["conditions"]}
    rows = []
    for a in matches["anchors"]:
        read_ids, not_read_ids, missing = _targeted(inventory, by_id[a["condition_id"]]["pieces"])
        rows.append({**a, "sources_read": read_ids, "sources_not_read": not_read_ids, "pieces_missing": missing})
    return {"format": FORMAT, "note": NOTE, "revision": revision, "state": "configured" if spec["conditions"] else "cleared",
            "spec_text": spec_text, "spec_sha256": spec_sha256, "events": events,
            "inventory": inventory, "anchors": rows}


def validate_section(brief_text: str, section: Any) -> dict[str, Any]:
    if (not isinstance(section, dict) or section.get("format") != FORMAT or section.get("note") != NOTE
            or set(section) != {"format", "note", "revision", "state", "spec_text", "spec_sha256", "events", "inventory", "anchors"}
            or type(section["revision"]) is not int or not 1 <= section["revision"] <= 100000):
        raise CorpusError("signed conditions section invalid")
    spec = load_stored(section["spec_text"], section["spec_sha256"])
    expected = anchors(brief_text, spec) if spec["conditions"] else []
    if section["state"] != ("configured" if spec["conditions"] else "cleared"):
        raise CorpusError("signed conditions state does not match the stored revision")
    ev = section["events"]
    if ev is not None and (
            not isinstance(ev, list) or len(ev) != section["revision"]
            or any(not isinstance(e, dict) or set(e) != {"revision", "spec_sha256", "actor_id", "recorded_at"}
                   or e["revision"] != n or type(e["revision"]) is not int
                   or not isinstance(e["spec_sha256"], str) or not _SHA.fullmatch(e["spec_sha256"])
                   or not isinstance(e["actor_id"], str) or not _UUID.fullmatch(e["actor_id"])
                   or not isinstance(e["recorded_at"], str) or not _STAMP.fullmatch(e["recorded_at"])
                   for n, e in enumerate(ev, start=1))
            or ev[-1]["spec_sha256"] != section["spec_sha256"]):
        raise CorpusError("signed conditions recorded events invalid")
    inventory = section["inventory"]
    if (not isinstance(inventory, list) or len(inventory) > 64
            or any(set(r) != {"source_id", "version_id", "original_sha256", "piece", "read"} or type(r["read"]) is not bool
                   for r in inventory)
            or len({(r["source_id"], r["version_id"]) for r in inventory}) != len(inventory)
            or inventory != sorted(inventory, key=lambda r: (r["piece"], r["source_id"], r["version_id"]))):
        raise CorpusError("signed conditions inventory invalid")
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
        # Coverage is recomputed from the fixed inventory; the supplied arrays are only compared, never trusted.
        ids_read, ids_not_read, missing = _targeted(inventory, by_id[anchor["condition"]]["pieces"])
        by_label_read = {r["piece"] for r in inventory if r["source_id"] in ids_read}
        by_label_unread = {r["piece"] for r in inventory if r["source_id"] in ids_not_read}
        if (row.get("sources_read") != ids_read or row.get("sources_not_read") != ids_not_read
                or row.get("pieces_missing") != missing
                or read != sorted(by_label_read - by_label_unread) or not_read != sorted(by_label_unread | set(missing))
                or len(set(read)) != len(read) or len(set(not_read)) != len(not_read) or set(read) & set(not_read)):
            raise CorpusError("signed condition coverage does not match the inventory")
        ok_sources = {r["source_id"]: r for r in inventory}
        for f in found:
            src = ok_sources.get(f.get("source_id"))
            if src is None or not src["read"] or src["piece"] != f.get("piece") or src["original_sha256"] != f.get("original_sha256"):
                raise CorpusError("signed condition excerpt names a source outside the read inventory")
        terms = {t.casefold() for t in by_id[anchor["condition"]]["evidence"]}
        for f in found:
            if (hashlib.sha256(f["excerpt"].encode()).hexdigest() != f["excerpt_sha256"]
                    or f["term"].casefold() not in terms):
                raise CorpusError("signed condition excerpt inconsistent")
        status, reason = row.get("status"), row.get("reason")
        if found:
            ok = (status, reason) == ("UNDETERMINED", R_FOUND)
        elif not not_read and not ids_not_read and read:
            ok = (status, reason) == ("UNVERIFIED", R_NONE)
        else:
            ok = (status, reason) == ("UNDETERMINED", R_PARTIAL)
        if not ok:
            raise CorpusError("signed condition status does not follow from its evidence")
    return section
