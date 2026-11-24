"""Retained original source bytes inside the signed offline pack (additive section, fail closed).

The section lists EVERY declared source of the snapshot, either with its exact original bytes (digest-checked at
export by the authorized original reader) or with an explicit omission and a closed reason. Replay re-hashes the
bytes and, for text sources, rebuilds the stored text from them and recomputes the conditions evidence, so the
excerpts are no longer only hash-consistent. It does not show that the bytes are the lawyer's real exhibit, only
that they are the bytes the signed service returned and digested at export.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import re
from collections.abc import Callable, Mapping
from types import SimpleNamespace
from typing import Any

from application.litigation.corpus import CorpusError

FORMAT = "caseproof-signed-sources-pack-v1"
NOTE = ("Octets d'origine des sources déclarées au moment de l'export, tels que le service signé les a renvoyés "
        "après contrôle de leur empreinte. Le rejeu recalcule les empreintes ; pour les sources texte lues, il refait "
        "aussi la recherche des conditions à partir de ces octets. Une source omise est listée avec sa raison. "
        "Ce pack ne prouve pas que ces octets sont la pièce d'origine de l'avocat.")
MAX_ENTRIES = 32
MAX_ENTRY_BYTES = 5_242_880
MAX_TOTAL_BYTES = 16 * 1024 * 1024
MAX_TEXT_CHARS = 120_000
SERVED_TYPES = ("application/pdf", "text/plain")
REASONS = ("media_type_not_served", "over_pack_budget", "read_failed", "text_differs_from_stored_representation")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_KEYS = {"source_id", "version_id", "piece", "original_sha256", "media_type", "state", "reason", "byte_length", "data_base64"}


def _order(r: Mapping[str, Any]) -> tuple[str, str, str]:
    return (r["piece"], r["source_id"], r["version_id"])


def build_section(previews: Any, labels: Mapping[str, str], fetch: Callable[[str, str], tuple[bytes, str] | None],
                  readable: Any) -> dict[str, Any]:
    """`fetch(source_id, version_id)` returns (bytes, media_type) from the authorized reader, or None when it failed."""
    entries: list[dict[str, Any]] = []
    total = 0
    for p in sorted(previews, key=lambda p: (labels.get(p.row.source_id) or p.row.source_id, p.row.source_id, p.row.version_id)):
        row = p.row
        base = {"source_id": row.source_id, "version_id": row.version_id,
                "piece": labels.get(row.source_id) or f"source {row.source_id[:8]}",
                "original_sha256": row.original_sha256, "media_type": row.media_type}
        def omit(reason: str, base: dict[str, Any] = base) -> dict[str, Any]:
            return {**base, "state": "omitted", "reason": reason, "byte_length": None, "data_base64": None}

        if row.media_type not in SERVED_TYPES:
            entries.append(omit("media_type_not_served"))
            continue
        got = None
        try:
            got = fetch(row.source_id, row.version_id)
        except Exception:
            got = None
        if (got is None or type(got[0]) is not bytes or not 0 < len(got[0]) <= MAX_ENTRY_BYTES
                or hashlib.sha256(got[0]).hexdigest() != row.original_sha256 or got[1] != row.media_type):
            entries.append(omit("read_failed"))
            continue
        data = got[0]
        if total + len(data) > MAX_TOTAL_BYTES:
            entries.append(omit("over_pack_budget"))
            continue
        if readable(p) and row.media_type == "text/plain":
            try:
                same = data.decode("utf-8", errors="strict") == p.text
            except UnicodeDecodeError:
                same = False
            if not same:
                entries.append(omit("text_differs_from_stored_representation"))
                continue
        total += len(data)
        entries.append({**base, "state": "retained", "reason": None, "byte_length": len(data),
                        "data_base64": base64.b64encode(data).decode()})
    entries.sort(key=_order)
    return {"format": FORMAT, "note": NOTE, "entries": entries}


def decode_entry(e: Mapping[str, Any]) -> bytes:
    try:
        data = base64.b64decode(e["data_base64"], validate=True)
    except (binascii.Error, ValueError, TypeError):
        raise CorpusError("retained source bytes invalid") from None
    if len(data) != e["byte_length"] or hashlib.sha256(data).hexdigest() != e["original_sha256"]:
        raise CorpusError("retained source bytes do not match their digest")
    return data


def validate_section(section: Any, conditions: Mapping[str, Any] | None) -> dict[str, Any]:
    if (not isinstance(section, dict) or set(section) != {"format", "note", "entries"}
            or section["format"] != FORMAT or section["note"] != NOTE
            or not isinstance(section["entries"], list) or len(section["entries"]) > MAX_ENTRIES):
        raise CorpusError("retained sources section invalid")
    entries = section["entries"]
    total = 0
    for e in entries:
        if (not isinstance(e, dict) or set(e) != _KEYS
                or any(type(e[k]) is not str or not e[k] for k in ("source_id", "version_id", "piece", "media_type"))
                or type(e["original_sha256"]) is not str or not _SHA.fullmatch(e["original_sha256"])):
            raise CorpusError("retained source entry invalid")
        if e["state"] == "retained":
            if (e["reason"] is not None or e["media_type"] not in SERVED_TYPES or type(e["byte_length"]) is not int
                    or not 0 < e["byte_length"] <= MAX_ENTRY_BYTES or type(e["data_base64"]) is not str):
                raise CorpusError("retained source entry invalid")
            total += e["byte_length"]
            decode_entry(e)
        elif e["state"] == "omitted":
            if e["reason"] not in REASONS or e["byte_length"] is not None or e["data_base64"] is not None:
                raise CorpusError("omitted source entry invalid")
        else:
            raise CorpusError("retained source entry invalid")
    if (total > MAX_TOTAL_BYTES or entries != sorted(entries, key=_order)
            or len({(e["source_id"], e["version_id"]) for e in entries}) != len(entries)):
        raise CorpusError("retained sources inventory invalid")
    if conditions is not None:
        inv = [(r["source_id"], r["version_id"], r["original_sha256"], r["piece"]) for r in conditions["inventory"]]
        got = [(e["source_id"], e["version_id"], e["original_sha256"], e["piece"]) for e in entries]
        if sorted(inv) != sorted(got):
            raise CorpusError("retained sources do not match the conditions inventory")
    return section


def text_replayable(section: Mapping[str, Any], conditions: Mapping[str, Any]) -> bool:
    kept = {(e["source_id"], e["version_id"]): e for e in section["entries"]}
    return all(not r["read"] or (kept[(r["source_id"], r["version_id"])]["state"] == "retained"
                                 and kept[(r["source_id"], r["version_id"])]["media_type"] == "text/plain")
               for r in conditions["inventory"])


def replay_conditions(brief_text: str, section: Mapping[str, Any], conditions: dict[str, Any],
                      spec: Mapping[str, Any]) -> str:
    """Rebuild stored text from retained bytes and recompute the conditions evidence.

    Returns "recomputed" or "partial" (some read source has no retained text bytes, so its excerpts stay
    hash-checked only). Raises CorpusError when the supplied evidence differs from what the retained bytes give."""
    from application.litigation.signed_conditions import match_conditions

    kept = {(e["source_id"], e["version_id"]): e for e in section["entries"]}
    previews = []
    for r in conditions["inventory"]:
        e = kept[(r["source_id"], r["version_id"])]
        row = SimpleNamespace(source_id=r["source_id"], version_id=r["version_id"], original_sha256=r["original_sha256"],
                              status="partial", warnings=("not_replayed",), representation_id=None, media_type=e["media_type"])
        text = ""
        if r["read"]:
            if e["state"] != "retained" or e["media_type"] != "text/plain":
                return "partial"
            try:
                text = decode_entry(e).decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                raise CorpusError("retained text source is not UTF-8") from None
            if not text.strip() or len(text) > MAX_TEXT_CHARS:
                raise CorpusError("retained text source cannot be a read source")
            row.status, row.warnings, row.representation_id = "ready", (), "rep:replayed"
        previews.append(SimpleNamespace(row=row, text=text, spans=((0, len(text), "identity_utf8", None),) if text else ()))
    labels = {r["source_id"]: r["piece"] for r in conditions["inventory"]}
    if not spec["conditions"]:
        return "recomputed"
    fresh = match_conditions(brief_text, spec, previews, labels)["anchors"]
    given = conditions["anchors"]
    keys = ("anchor_id", "condition_id", "status", "reason", "found", "pieces_read", "pieces_not_read")
    if len(fresh) != len(given) or any({k: a[k] for k in keys} != {k: b.get(k) for k in keys}
                                       for a, b in zip(fresh, given, strict=True)):
        raise CorpusError("conditions evidence does not replay from the retained source bytes")
    return "recomputed"
