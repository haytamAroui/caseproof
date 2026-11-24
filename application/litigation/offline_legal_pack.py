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

from application.litigation.corpus import (
    BASIS_PDF,
    PDF_KIND,
    ArticleRecord,
    CorpusError,
    check_derived_binding,
    derive_pdf_body_start,
)
from application.litigation.exhibit_coverage import coverage as exhibit_coverage
from application.litigation.exhibit_coverage import exhibit_observations
from application.litigation.exhibit_passages import RULES as PASSAGE_RULES
from application.litigation.exhibit_passages import SCOPE as PASSAGE_SCOPE
from application.litigation.exhibit_passages import SCOPE_LEGACY as PASSAGE_SCOPE_LEGACY
from application.litigation.exhibit_passages import validate_passages
from application.litigation.lawyer_conditions import R_FOUND as COND_FOUND
from application.litigation.lawyer_conditions import R_NONE as COND_NONE
from application.litigation.lawyer_conditions import SCOPE as CONDITION_SCOPE
from application.litigation.lawyer_conditions import condition_observations, validate_evidence, validate_spec
from application.litigation.legal_references import (
    _QUOTE_STRICT,
    _QUOTE_V3,
    LegalCorpusConfig,
    check_legal_references,
    engine_authority,
    engine_conditions,
    engine_exhibits,
    engine_mode,
)
from application.litigation.legal_review_decisions import body_fingerprints, validate_review
from application.litigation.signed_conditions_pack import validate_section as validate_signed_section
from application.litigation.unified_review import LegalObservation

MAX_BYTES = 40 * 1024 * 1024
SCHEMA = "caseproof-offline-legal-review-v1"
SHARED_FORMAT = "shared-originals-v1"  # optional: identical originals and text layers stored once per export
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
    shared = data.get("shared_originals")
    if shared is not None and (not isinstance(shared, dict) or set(shared) != {"format", "blobs", "layers"}
                               or shared["format"] != SHARED_FORMAT):
        raise CorpusError("shared originals malformed")
    for row in rows:
        values = dict(row)
        if "original_base64" in values:
            encoded = values.pop("original_base64")
        else:
            if shared is None or values["original_sha256"] not in shared["blobs"]:
                raise CorpusError("original bytes missing")
            encoded = shared["blobs"][values["original_sha256"]]
        if "original_text_layer" not in values:
            if shared is None or values.get("original_text_layer_sha256") not in shared["layers"]:
                raise CorpusError("original text layer missing")
            values["original_text_layer"] = shared["layers"][values["original_text_layer_sha256"]]
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > 32 * 1024 * 1024 or _hash(raw) != values["original_sha256"]:
            raise CorpusError("original bytes changed")
        text = values["derived_text"]
        if not isinstance(text, str) or _hash(text.encode()) != values["derived_sha256"]:
            raise CorpusError("article text changed")
        record = ArticleRecord(**values, original_bytes=raw)
        if record.source_artifact_kind == PDF_KIND:
            layer = record.original_text_layer
            if not raw.startswith(b"%PDF-") or _hash(layer.encode()) != record.original_text_layer_sha256:
                raise CorpusError("PDF text layer changed")
            check_derived_binding("official_text_capture", layer.encode(), text, record.article, layer=True)
            if (derive_pdf_body_start(layer, text, record.article, raw) != record.body_start
                    or record.body_start_basis != BASIS_PDF):
                raise CorpusError("body start no longer follows the publisher PDF layout")
        else:
            check_derived_binding(record.source_artifact_kind, raw, text, record.article)
        records.append(record)
    if shared is not None:
        used_blobs = {r["original_sha256"] for r in rows if "original_base64" not in r}
        used_layers = {r["original_text_layer_sha256"] for r in rows if "original_text_layer" not in r}
        if set(shared["blobs"]) != used_blobs or set(shared["layers"]) != used_layers:
            raise CorpusError("shared originals hold bytes no article uses")
    if len({r.key for r in records}) != len(records):
        raise CorpusError("duplicate article identity")
    if not all(isinstance(m, dict) and all(isinstance(k, str) and isinstance(v, str)
                                         for k, v in m.items())
               for m in (data["act_aliases"], data["chosen_versions"])):
        raise CorpusError("declared selection required")
    return LegalCorpusConfig(tuple(records), data["act_aliases"], data["chosen_versions"])


_SCOPE = {
    "quotation_found_verbatim_in_corpus_article": "Extrait littéral retrouvé dans le texte conservé de l'article. Contexte, réserves, portée et applicabilité non évalués.",
    "quotation_absent_from_corpus_article_text": "Extrait absent du texte conservé de l'article.",
    "quotation_starts_at_declared_body_start_not_attested": "Extrait littéral retrouvé, qui commence au début de corps déclaré par le préparateur du corpus (non attesté par l'éditeur) : la réserve ou le contexte qui précède n'est pas écarté par le moteur. Décision humaine requise.",
    "quotation_partial_excerpt_review_required": "Extrait littéral retrouvé, mais il ne commence pas ou ne finit pas à une limite de phrase du texte conservé. Appréciation de l'avocat requise.",
    "quotation_starts_or_ends_mid_word": "Fragment qui commence ou finit au milieu d'un mot. Appréciation de l'avocat requise.",
    "article_exists_in_corpus_no_quotation_checked_claim_not_verified": "Article présent dans le corpus. Aucune citation n'a été contrôlée : l'affirmation n'est pas vérifiée.",
    "sub_article_locator_not_checked_in_corpus": "Alinéa, paragraphe ou autre subdivision cité : non contrôlé, le corpus ne contient pas ce niveau.",
    "quotation_delimiter_not_recognised_text_not_checked": "Guillemet ouvrant non reconnu : le texte qui suit n'est pas contrôlé.",
    "exhibit_located_by_number_bytes_read_content_not_compared": "Renvoi à une pièce retrouvé dans le bordereau par son numéro ; le fichier a été lu (empreinte SHA-256 calculée sur ses octets). Le SENS de la pièce n'a PAS été vérifié par rapport à l'affirmation (au mieux, des dates ou montants identiques sont proposés en passages) : appréciation de l'avocat requise.",
    "exhibit_number_absent_from_bordereau": "Numéro de pièce absent du bordereau : renvoi non résolu.",
    "exhibit_listed_but_file_missing_check_impossible": "Pièce inscrite au bordereau, fichier absent : contrôle impossible.",
    "exhibit_file_has_no_readable_text_check_impossible": "Fichier présent mais sans texte lisible (scan, protégé ou illisible) : contrôle impossible, aucune lecture OCR.",
    "exhibit_range_endpoints_not_integers_not_expanded": "Plage de pièces non numérique : non développée, à vérifier à la main.",
    "exhibit_page_reference_not_checked_pdf_page_vs_printed_number_unresolved": "Renvoi à une page de pièce : non contrôlé. La page du PDF, le numéro imprimé et la position dans le dossier ne sont pas distingués ici.",
    "quotation_not_bound_to_a_checked_reference": "Citation entre guillemets non rattachée à un article contrôlé : non vérifiée.",
}


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
    strict, v3 = engine_mode(body["review"].get("check_engine"))
    if strict:
        quotes = [m for m in (_QUOTE_V3 if v3 else _QUOTE_STRICT).finditer(body["brief_text"])]
        accounted = sum(any(o.get("quote") and " ".join(o["quote"].split()) == " ".join(next(g for g in m.groups() if g is not None).split())
                            for o in body["references"]) for m in quotes)
        parts += ["<p class='note'>Moteur de contrôle strict (", "v6" if engine_conditions(body["review"].get("check_engine")) else "v5" if engine_exhibits(body["review"].get("check_engine")) else "v4" if engine_authority(body["review"].get("check_engine")) else "v3" if v3 else "v2", "). Les exports plus anciens, sans cette mention, utilisent un moteur plus large. ",
                  "Un PASS signifie seulement : extrait littéralement présent dans le texte conservé. Le contexte, les réserves, la portée et ",
                  "l'applicabilité restent à l'avocat.</p><h2>Couverture</h2><p>Citations entre guillemets dans le Word : ", str(len(quotes)),
                  ". Citations avec un constat visible ci-dessous : ", str(accounted), ". Références d'article : ",
                  str(sum(1 for o in body["references"] if o["act_code"] is not None)), ".</p>"]
    if "exhibits" in body:
        cov = exhibit_coverage(body["brief_text"], body["exhibits"])
        parts += ["<h2>Pièces : résolution des renvois et octets lus</h2><p class='note'>Ce contrôle résout les renvois « Pièce » / « Stuk » ",
                  "dans le bordereau local et lit les fichiers. Il ne vérifie PAS que le contenu d'une pièce établit ce que les conclusions affirment. ",
                  "Les empreintes ont été calculées sur les octets au moment du contrôle ; ce rejeu relit le bordereau enregistré, pas les fichiers.</p><p>",
                  "Pièces au bordereau : ", str(cov["listed"]), ". Numéros cités : ", esc(", ".join(cov["cited_numbers"]) or "aucun"),
                  ". Pièces jamais citées : ", esc(", ".join(cov["unreferenced"]) or "aucune"),
                  ". Fichiers absents : ", esc(", ".join(cov["missing_files"]) or "aucun"),
                  ". Sans texte lisible : ", esc(", ".join(cov["unreadable"]) or "aucune"), ".</p><pre>"]
        parts += [esc(f"{p['number']} | {p['label']} | {p['file']} | {p['sha256'] or 'absent'} | pages={p['pages']} | lisible={p['readable']}\n") for p in body["exhibits"]["pieces"]]
        parts += ["</pre>"]
    by_key = {r["key"]: r for r in body["article_index"]}
    prints = body_fingerprints(body)
    layered = body["review"].get("decision_layer") == 1
    decided = {d["fingerprint"]: d for d in body["review"].get("decisions", [])}
    cond_rows = iter(body.get("condition_evidence", []))
    cond_labels = {c["id"]: c for c in body.get("conditions", {}).get("conditions", [])}
    for obs, fp in zip(body["references"], prints, strict=True):
        parts += ["<article><h3>", esc(obs["raw_text"]), "</h3><strong>", esc(obs["status"]),
                  "</strong> · ", esc(obs["reason"]), "<pre>", esc(obs["quote"] or "Aucune citation liée"), "</pre>"]
        if strict and obs["reason"] in _SCOPE:
            parts += ["<p>", esc(_SCOPE[obs["reason"]]), "</p>"]
        row = by_key.get(obs["corpus_key"])
        if row is not None:
            parts += [f"<a href='#article-{row['index']}'>Rouvrir le passage exact du pack figé</a>"]
        elif obs["reason"] in (COND_FOUND, COND_NONE):
            ev = next(cond_rows, None)
            cond = cond_labels.get(ev["condition"]) if ev else None
            parts += ["<p class='note'>", esc(CONDITION_SCOPE), "</p>"]
            if ev is not None and cond is not None:
                parts += ["<p><strong>Condition :</strong> ", esc(cond["label"]), "</p>"]
                if cond["question"]:
                    parts += ["<p><strong>Question de l'avocat :</strong> ", esc(cond["question"]), "</p>"]
                parts += ["<p><strong>Phrase du mémoire :</strong> ", esc(ev["sentence"]), "</p><p>Pièces lues : ",
                          esc(", ".join(ev["pieces_read"]) or "aucune"), ". Mots à retrouver : ", esc(", ".join(cond["evidence"])), ". ",
                          ("Passages trouvés :" if ev["found"] else "Aucun passage trouvé dans les pièces lues (cela ne prouve pas l'absence : texte non lisible, formulation différente).") , "</p>"]
                parts += [f"<pre>Pièce {esc(f['piece'])}, p. {f['page']} · « {esc(f['term'])} »\n{esc(f['excerpt'])}</pre>" for f in ev["found"]]
        elif obs["reason"].startswith("exhibit_"):
            parts += ["<p>Renvoi à une pièce : aucun article de corpus concerné.</p>"]
            entry = next((e for e in body.get("passages", []) if e["reference_id"] == obs["reference_id"]), None)
            if entry is not None:
                parts += ["<p><strong>Affirmation :</strong> ", esc(entry["claim"]), "</p><p class='note'>", esc(PASSAGE_SCOPE if body.get("passages_rules") else PASSAGE_SCOPE_LEGACY), "</p>"]
                parts += ["<p>Passages de la pièce avec la même valeur : ", ("" if entry["found"] else "aucun"), "</p>"]
                parts += [f"<pre>p. {f['page']}{_page_ref_text(f)} · {esc(f['key'])}\n{esc(f['excerpt'])}</pre>" for f in entry["found"]]
                flagged: set[str] = set()
                for f in entry["found"]:
                    if "status_cue_mismatch" in f and f["excerpt_sha256"] not in flagged:
                        flagged.add(f["excerpt_sha256"])
                        m = f["status_cue_mismatch"]
                        parts += [f"<p><strong>Mot d'état divergent (détection partielle) :</strong> l'affirmation dit « {esc(m['claim_cue'])} », "
                                  f"le passage p. {f['page']} dit « {esc(m['passage_cue'])} ». Liste fixe de mots FR/NL, un seul cas de contradiction ; à lire par l'avocat.</p>"]
                if entry["missing_values"]:
                    parts += ["<p><strong>Différence candidate :</strong> valeur absente de toutes les pages lues de la pièce : ",
                              esc(", ".join(entry["missing_values"])), ". À examiner par l'avocat.</p>"]
                if entry["ambiguous_values"]:
                    parts += ["<p>Valeurs non interprétables sans ambiguïté (non comparées) : ", esc(", ".join(entry["ambiguous_values"])), ".</p>"]
                if not entry["claim_values"]:
                    parts += ["<p>Aucune date ni aucun montant dans l'affirmation : aucun passage proposé.</p>"]
        else:
            parts += ["<p>Pas de passage sélectionné. Aucune substitution par une autre version.</p>"]
        d = decided.get(fp)
        if not layered:
            pass
        elif d is None:
            parts += ["<p><strong>Décision requise.</strong> Aucune décision locale ne couvre ce constat exact.</p>"]
        else:
            parts += ["<p><strong>Décision locale : ", esc(d["action"]), "</strong> · ", esc(d["reviewer_label"]),
                      " (libellé local non authentifié, ", esc(d["origin"]), ")<br>", esc(d["reason"]), "</p>"]
        parts += ["</article>"]
    superseded = body["review"].get("superseded", [])
    if superseded and layered:
        parts += ["<h2>Décisions antérieures sans effet sur ce constat</h2><p>Revue précédente <code>",
                  esc(body["review"].get("prior_checkpoint")), "</code>. Ces décisions restent visibles mais ne couvrent plus aucun constat identique.</p><pre>",
                  esc(json.dumps(superseded, ensure_ascii=False, indent=2, sort_keys=True)), "</pre>"]
    if "signed_conditions" in body:
        parts += _signed_conditions_report(body["signed_conditions"])
    if "signed_sources" in body:
        parts += _signed_sources_report(body["signed_sources"], body.get("signed_conditions"))
    parts += ["<h2>Décisions de revue enregistrées</h2><pre>", esc(json.dumps(body["review"], ensure_ascii=False, indent=2, sort_keys=True)),
              "</pre><h2>Texte du mémoire vérifié</h2><pre>", esc(body["brief_text"]), "</pre><h2>Articles conservés</h2>"]
    for i, row in enumerate(body["articles"]):
        parts += [f"<section id='article-{i}'><h3>", esc(body["article_index"][i]["key"]), "</h3>",
                  "<p>Source conservée : ", esc(row["source_uri"]), "<small>Acquisition : ", esc(row["acquired_at"]),
                  " · Consolidation : ", esc(row["consolidated"]), "</small></p><pre>", esc(row["derived_text"]),
                  "</pre><small>Texte SHA-256 : <code>", esc(row["derived_sha256"]),
                  "</code></small><small>Artefact source SHA-256 : <code>", esc(row["original_sha256"]),
                  "</code></small><p>Type : ", esc(row["source_artifact_kind"]), "</p><p>", esc(row["source_notes"]), "</p>"]
        if body["review"].get("fingerprint_scheme", 1) >= 2:
            if row.get("body_start_basis") == BASIS_PDF:
                parts += ["<p>Début du corps de l'article, tiré de la mise en page du PDF consolidé de l'éditeur conservé (première ligne après la ligne d'intitulé ; les lignes de l'article sont relues dans le PDF conservé à chaque chargement et à chaque rejeu, mais c'est une mise en page, pas un balisage structuré) : <code>",
                          esc(row["body_start"]), "</code></p></section>"]
                continue
            parts += ["<p>Début du corps de l'article, déclaré par le préparateur du corpus et borné par le texte conservé, non attesté par l'éditeur : <code>",
                      esc(row.get("body_start") or "non déclaré (la première phrase n'est pas supposée complète)"), "</code></p>"]
        parts += ["</section>"]
    parts += ["</html>"]
    return "".join(parts).encode()


def _signed_sources_report(section: dict[str, Any], conditions: dict[str, Any] | None) -> list[str]:
    from application.litigation.signed_sources_pack import text_replayable

    def esc(v: object) -> str:
        return html.escape(str(v), quote=True)

    parts = ["<h2>Sources d'origine conservées</h2><p>", esc(section["note"]), "</p><ul>"]
    for e in section["entries"]:
        what = (f"conservée, {e['byte_length']} octets" if e["state"] == "retained" else f"omise ({e['reason']})")
        parts += ["<li>", esc(e["piece"]), " · ", esc(e["media_type"]), " · ", esc(what), " · <code>",
                  esc(e["original_sha256"]), "</code></li>"]
    parts += ["</ul>"]
    if conditions is not None:
        parts += ["<p>", ("Les extraits de conditions ont été recalculés au rejeu à partir des octets conservés de toutes les sources lues."
                          if text_replayable(section, conditions) else
                          "Certaines sources lues n'ont pas d'octets texte conservés : leurs extraits restent contrôlés par empreinte seulement, "
                          "sans nouvelle recherche dans la source."), "</p>"]
    parts += ["<p>Les sources conservées se rouvrent hors ligne avec le script de réouverture du dépôt, après rejeu complet du pack.</p>"]
    return parts


def _signed_conditions_report(section: dict[str, Any]) -> list[str]:
    def esc(v: object) -> str:
        return html.escape(str(v), quote=True)

    parts = ["<h2>Conditions définies par l'avocat</h2><p>", esc(section["note"]), "</p><p>Révision ", esc(section["revision"]),
             " · empreinte <code>", esc(section["spec_sha256"]), "</code></p>"]
    parts += ["<p><strong>Conditions effacées volontairement à cette révision : aucune condition n'est active (ce n'est pas un dossier jamais configuré).</strong></p>"
              if section["state"] == "cleared" else "<p>Conditions actives.</p>"]
    ev = section.get("events")
    if ev is None:
        parts += ["<p>Auteur et date d'enregistrement des révisions : non disponibles (le service n'a pas fourni ces valeurs).</p>"]
    else:
        parts += ["<p>Révisions enregistrées (auteur = identifiant du compte vérifié, date = horloge de la base, UTC) : ",
                  esc("; ".join(f"révision {e['revision']} par {e['actor_id']} le {e['recorded_at']}" for e in ev)),
                  ". Ces valeurs sont celles que le service a renvoyées au moment de l'export ; le pack ne permet pas de les revérifier seul.</p>"]
    parts += ["<p>Inventaire des sources au moment de l'export (", esc(len(section["inventory"])), ") : ",
              esc("; ".join(f"{r['piece']} {'lue' if r['read'] else 'non lue'}" for r in section["inventory"]) or "aucune"),
              ". Couverture recalculée au rejeu à partir de cet inventaire. Les empreintes d'extraits ne contrôlent que la cohérence interne du pack : les sources elles-mêmes ne sont pas rejointes ici et n'ont pas été revérifiées de façon indépendante.</p>"]
    for a in section["anchors"]:
        parts += ["<article><p><strong>", esc(a["status"]), "</strong> · ", esc(a["label"]), "<br>", esc(a["sentence"]),
                  "<br><small>", esc(a["reason"]), "</small></p>"]
        for f in a["found"]:
            parts += ["<p>", esc(f["piece"]), (f" p. {f['pdf_page']}" if f.get("pdf_page") else ""), " · mot « ", esc(f["term"]),
                      " » : ", esc(f["excerpt"]), "</p>"]
        if a["pieces_not_read"]:
            parts += ["<p>Pièces non lues : ", esc(", ".join(a["pieces_not_read"])), "</p>"]
        parts += ["</article>"]
    return parts


class LegalRun(Protocol):
    @property
    def snapshot_hash(self) -> str: ...
    @property
    def representation_sha256(self) -> str: ...
    @property
    def corpus_pack_sha256(self) -> str | None: ...
    @property
    def legal_observations(self) -> tuple[LegalObservation, ...]: ...


def _page_ref_text(f: dict[str, Any]) -> str:
    ref = f.get("page_ref")
    if not ref:
        return ""
    bits = [f"position dans le fichier {ref['index']}"]
    bits.append(f"étiquette du PDF « {ref['label']} »" if ref["label"] else "pas d'étiquette de page dans le PDF")
    bits.append(f"numéro imprimé lu « {ref['printed']} »" if ref["printed"] else "pas de numéro imprimé reconnu")
    return " (" + " · ".join(bits) + ")"


def observe(text: str, config: LegalCorpusConfig, marker: object, exhibits: dict[str, Any] | None,
            conditions: tuple[dict[str, Any], list[dict[str, Any]]] | None = None) -> tuple[Any, ...]:
    """The one place legal and exhibit observations are produced, for build and cold replay alike."""
    strict, v3 = engine_mode(marker)
    obs = list(check_legal_references(text, config.records, config.act_aliases, chosen_versions=config.chosen_versions,
                                      strict=strict, v3=v3, authority=engine_authority(marker)))
    if engine_exhibits(marker):
        if exhibits is None:
            raise CorpusError("exhibit manifest required by this engine")
        obs += exhibit_observations(text, exhibits, len(obs) + 1)
        if engine_conditions(marker):
            if conditions is None:
                raise CorpusError("conditions required by this engine")
            obs += condition_observations(text, conditions[0], conditions[1], len(obs) + 1)
        obs.sort(key=lambda o: o.start)
    return tuple(obs)


def build_legal_pack(*, config: LegalCorpusConfig, run: LegalRun,
                     brief_text: str, review: dict[str, Any], exhibits: dict[str, Any] | None = None,
                     passages: list[dict[str, Any]] | None = None, passages_rules: str | None = PASSAGE_RULES,
                     conditions: dict[str, Any] | None = None, condition_evidence: list[dict[str, Any]] | None = None,
                     signed_conditions: dict[str, Any] | None = None,
                     signed_sources: dict[str, Any] | None = None) -> tuple[bytes, str]:
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
    shared_body: dict[str, Any] | None = None
    if len({r["original_sha256"] for r in articles}) < len(articles):
        blobs: dict[str, str] = {}
        layers: dict[str, str] = {}
        for row in articles:
            blobs.setdefault(row["original_sha256"], row.pop("original_base64"))
            if row.get("original_text_layer_sha256"):
                layers.setdefault(row["original_text_layer_sha256"], row.pop("original_text_layer"))
        shared_body = {"format": SHARED_FORMAT, "blobs": blobs, "layers": layers}
    body = {"schema": SCHEMA, "note": NOTE, "snapshot_hash": run.snapshot_hash,
            "corpus_pack_sha256": config.pack_sha256, "brief_text": brief_text,
            "brief_representation_sha256": run.representation_sha256,
            "act_aliases": dict(config.act_aliases), "chosen_versions": dict(config.chosen_versions),
            "references": [asdict(x) for x in run.legal_observations], "review": review,
            "articles": articles, "article_index": [{"key": r.key, "index": i} for i, r in enumerate(config.records)]}
    if shared_body is not None:
        body["shared_originals"] = shared_body
    if exhibits is not None:
        body["exhibits"] = exhibits
    if passages is not None:
        if exhibits is None:
            raise CorpusError("passages need an exhibit manifest")
        body["passages"] = passages
        if passages_rules is not None:
            body["passages_rules"] = passages_rules
    if conditions is not None:
        body["conditions"] = conditions
        body["condition_evidence"] = condition_evidence if condition_evidence is not None else []
    if signed_conditions is not None:
        if conditions is not None:
            raise CorpusError("two conditions sections")
        body["signed_conditions"] = signed_conditions
    if signed_sources is not None:
        body["signed_sources"] = signed_sources
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
        marker = body["review"].get("check_engine")
        if engine_exhibits(marker) != ("exhibits" in body):
            raise CorpusError("exhibit coverage section does not match the engine marker")
        if "passages" in body and not engine_exhibits(marker):
            raise CorpusError("passages without exhibit coverage")
        if engine_conditions(marker) != ("conditions" in body) or ("condition_evidence" in body) != ("conditions" in body):
            raise CorpusError("conditions section does not match the engine marker")
        cond = None
        if "conditions" in body:
            spec = validate_spec(body["conditions"])
            validate_evidence(body["brief_text"], spec, body["condition_evidence"])
            cond = (spec, body["condition_evidence"])
        if "signed_conditions" in body:
            if "conditions" in body:
                raise CorpusError("two conditions sections")
            validate_signed_section(body["brief_text"], body["signed_conditions"])
        if "signed_sources" in body:
            from application.litigation import signed_sources_pack as _ssp
            sc = body.get("signed_conditions")
            _ssp.validate_section(body["signed_sources"], sc)
            if sc is not None and _ssp.text_replayable(body["signed_sources"], sc):
                from application.litigation.signed_conditions import load_stored
                _ssp.replay_conditions(body["brief_text"], body["signed_sources"], sc,
                                       load_stored(sc["spec_text"], sc["spec_sha256"]))
        observed = observe(body["brief_text"], config, marker, body.get("exhibits"), cond)
        if "passages" in body:
            validate_passages(body["brief_text"], [asdict(x) for x in observed], body["passages"], body.get("passages_rules"))
        if _encode([asdict(x) for x in observed]) != _encode(body["references"]):
            raise CorpusError("legal checks do not replay")
        if body["article_index"] != [{"key": r.key, "index": i} for i, r in enumerate(config.records)]:
            raise CorpusError("article passage index changed")
        validate_review(body["review"], body_fingerprints(body))
        if report != _report(body):
            raise CorpusError("offline reading view changed")
        return body
    except (BadZipFile, UnicodeError, KeyError, TypeError, ValueError, OSError) as exc:
        raise CorpusError("offline legal review rejected") from exc
