"""Version-pinned, bounded legal-corpus review export. No network or legal opinion.

The ZIP contains data and an inert, self-contained HTML reading view. The
independent digest is an integrity checkpoint, not an author certificate.
Only the legal-reference slice is reopened here, not all exhibit evidence.
"""
from __future__ import annotations

import base64
import hashlib
import html
import io
import json
from dataclasses import asdict
from typing import Any, Protocol
from zipfile import ZIP_STORED, BadZipFile, ZipFile

from application.litigation.corpus import ArticleRecord, CorpusError
from application.litigation.legal_references import LegalCorpusConfig, check_legal_references
from application.litigation.unified_review import LegalObservation

MAX_BYTES = 40 * 1024 * 1024
SCHEMA = "caseproof-offline-legal-review-v1"
NOTE = ("Corpus presence and quotation integrity only. Applicability, interpretation and claim support "
        "are not assessed. Lawyer decision required. This is the legal-reference review slice, "
        "not a complete dossier export. No authenticity or legal signature is established.")


def _encode(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _config(data: dict[str, Any]) -> LegalCorpusConfig:
    rows = data["articles"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 10000:
        raise CorpusError("bounded article inventory required")
    records = []
    for row in rows:
        values = dict(row)
        raw = base64.b64decode(values.pop("original_base64"), validate=True)
        if len(raw) > 32 * 1024 * 1024 or _hash(raw) != values["original_sha256"]:
            raise CorpusError("original bytes changed")
        text = values["derived_text"]
        if not isinstance(text, str) or _hash(text.encode()) != values["derived_sha256"]:
            raise CorpusError("article text changed")
        records.append(ArticleRecord(**values, original_bytes=raw))
    if len({r.key for r in records}) != len(records):
        raise CorpusError("duplicate article identity")
    if not all(isinstance(m, dict) and all(isinstance(k, str) and isinstance(v, str)
                                         for k, v in m.items())
               for m in (data["act_aliases"], data["chosen_versions"])):
        raise CorpusError("declared selection required")
    return LegalCorpusConfig(tuple(records), data["act_aliases"], data["chosen_versions"])


def _report(body: dict[str, Any]) -> bytes:
    def esc(v: object) -> str:
        return html.escape(str(v), quote=True)
    parts = ["<!doctype html><html lang='fr'><meta charset='utf-8'>",
             '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">',
             "<title>CaseProof | Revue juridique hors ligne</title><style>",
             "body{font:16px/1.6 system-ui;max-width:1060px;margin:32px auto;padding:24px;color:#18313a}",
             "h1,h2,h3{line-height:1.2}article{border-top:1px solid #b7c5cc;padding:24px 0}",
             "pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f5f6;padding:20px}",
             "code{overflow-wrap:anywhere;font-size:13px}.note{background:#fff1ce;padding:16px}",
             "a{color:#07576c}small{display:block}section:target{outline:3px solid #b77e13;padding:16px}",
             "</style><h1>Revue juridique hors ligne</h1><p class='note'>", esc(NOTE), "</p>",
             "<p>Pack figé <code>", esc(body["corpus_pack_sha256"]), "</code></p>",
             "<p>Revue <code>", esc(body["snapshot_hash"]), "</code></p><h2>Références vérifiées</h2>"]
    by_key = {r["key"]: r for r in body["article_index"]}
    for obs in body["references"]:
        parts += ["<article><h3>", esc(obs["raw_text"]), "</h3><strong>", esc(obs["status"]),
                  "</strong> · ", esc(obs["reason"]), "<pre>", esc(obs["quote"] or "Aucune citation liée"), "</pre>"]
        row = by_key.get(obs["corpus_key"])
        if row is not None:
            parts += [f"<a href='#article-{row['index']}'>Rouvrir le passage exact du pack figé</a>"]
        else:
            parts += ["<p>Pas de passage sélectionné. Aucune substitution par une autre version.</p>"]
        parts += ["</article>"]
    parts += ["<h2>Décisions de revue enregistrées</h2><pre>", esc(json.dumps(body["review"], ensure_ascii=False, indent=2, sort_keys=True)),
              "</pre><h2>Texte du mémoire vérifié</h2><pre>", esc(body["brief_text"]), "</pre><h2>Articles conservés</h2>"]
    for i, row in enumerate(body["articles"]):
        parts += [f"<section id='article-{i}'><h3>", esc(body["article_index"][i]["key"]), "</h3>",
                  "<p>Source conservée : ", esc(row["source_uri"]), "<small>Acquisition : ", esc(row["acquired_at"]),
                  " · Consolidation : ", esc(row["consolidated"]), "</small></p><pre>", esc(row["derived_text"]),
                  "</pre><small>Texte SHA-256 : <code>", esc(row["derived_sha256"]),
                  "</code></small><small>Artefact source SHA-256 : <code>", esc(row["original_sha256"]),
                  "</code></small><p>Type : ", esc(row["source_artifact_kind"]), "</p><p>", esc(row["source_notes"]), "</p></section>"]
    parts += ["</html>"]
    return "".join(parts).encode()


class LegalRun(Protocol):
    @property
    def snapshot_hash(self) -> str: ...
    @property
    def representation_sha256(self) -> str: ...
    @property
    def corpus_pack_sha256(self) -> str | None: ...
    @property
    def legal_observations(self) -> tuple[LegalObservation, ...]: ...


def build_legal_pack(*, config: LegalCorpusConfig, run: LegalRun,
                     brief_text: str, review: dict[str, Any]) -> tuple[bytes, str]:
    if config.failures or not config.records or run.corpus_pack_sha256 != config.pack_sha256:
        raise CorpusError("complete exact chosen corpus required for export")
    if _hash(brief_text.encode()) != run.representation_sha256 or review.get("snapshot_hash") != run.snapshot_hash:
        raise CorpusError("review or brief snapshot changed")
    articles = []
    for record in config.records:
        if record.original_bytes is None:
            raise CorpusError("original corpus bytes unavailable; no network fallback")
        row = asdict(record)
        raw = row.pop("original_bytes")
        row["original_base64"] = base64.b64encode(raw).decode()
        articles.append(row)
    body = {"schema": SCHEMA, "note": NOTE, "snapshot_hash": run.snapshot_hash,
            "corpus_pack_sha256": config.pack_sha256, "brief_text": brief_text,
            "brief_representation_sha256": run.representation_sha256,
            "act_aliases": dict(config.act_aliases), "chosen_versions": dict(config.chosen_versions),
            "references": [asdict(x) for x in run.legal_observations], "review": review,
            "articles": articles, "article_index": [{"key": r.key, "index": i} for i, r in enumerate(config.records)]}
    payload = _encode(body)
    checkpoint = _hash(payload)
    report = _report(body)
    if len(payload) + len(report) > MAX_BYTES - 100000:
        raise CorpusError("offline review exceeds bounded size")
    output = io.BytesIO()
    with ZipFile(output, "w", compression=ZIP_STORED) as archive:
        archive.writestr("review.json", payload)
        archive.writestr("report.html", report)
    raw = output.getvalue()
    verify_legal_pack(raw, expected_sha256=checkpoint)
    return raw, checkpoint


def verify_legal_pack(raw: bytes, *, expected_sha256: str) -> dict[str, Any]:
    """Cold replay from bytes only, no database, installed corpus or Internet."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise CorpusError("offline pack size invalid")
    try:
        with ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            if (sorted(x.filename for x in infos) != ["report.html", "review.json"]
                    or any(x.compress_type != ZIP_STORED or x.flag_bits & 1 for x in infos)
                    or sum(x.file_size for x in infos) > MAX_BYTES):
                raise CorpusError("offline pack inventory invalid")
            payload, report = archive.read("review.json"), archive.read("report.html")
        if _hash(payload) != expected_sha256:
            raise CorpusError("independent review checkpoint mismatch")
        body = json.loads(payload)
        if not isinstance(body, dict):
            raise CorpusError("offline review must be an object")
        if body["schema"] != SCHEMA or body["note"] != NOTE:
            raise CorpusError("unknown offline review schema")
        config = _config(body)
        if config.pack_sha256 != body["corpus_pack_sha256"]:
            raise CorpusError("chosen corpus selection changed")
        if (_hash(body["brief_text"].encode()) != body["brief_representation_sha256"]
                or body["review"]["snapshot_hash"] != body["snapshot_hash"]):
            raise CorpusError("review snapshot changed")
        observed = check_legal_references(body["brief_text"], config.records, config.act_aliases,
                                         chosen_versions=config.chosen_versions)
        if _encode([asdict(x) for x in observed]) != _encode(body["references"]):
            raise CorpusError("legal checks do not replay")
        if body["article_index"] != [{"key": r.key, "index": i} for i, r in enumerate(config.records)]:
            raise CorpusError("article passage index changed")
        if report != _report(body):
            raise CorpusError("offline reading view changed")
        return body
    except (BadZipFile, UnicodeError, KeyError, TypeError, ValueError, OSError) as exc:
        raise CorpusError("offline legal review rejected") from exc
