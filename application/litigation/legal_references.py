"""Deterministic legal-reference check of a brief against the CHOSEN corpus.

Question answered, per cited Belgian article: is that article present in the
corpus chosen for this case, and, when the brief quotes it, does the quoted
text occur verbatim in the corpus text of that article?

What this is NOT: legal reasoning, applicability, entry into force, correct
interpretation, or proof that the article supports the lawyer's claim. A PASS
says only that the article exists in the chosen corpus (and, if quoted, that
the quotation is literally in its stored text). The LLM is never a source.

Status mapping onto the shared four-status contract:
- PASS: article present in the chosen corpus; if a quotation is bound to the
  citation, it occurs verbatim (whitespace-normalised) in the article text.
- FAIL: a quotation bound to the citation does NOT occur in the article text
  of the declared corpus version. Narrow rule only, never a legal conclusion.
- UNVERIFIED: reserved meaning, exactly "article absent from the chosen
  corpus": the act mapping is declared and no corpus record exists for the
  (act, article, language).
- UNDETERMINED: everything else the machine cannot decide, each with a named
  reason: act not mapped to a corpus act, several declared versions with none
  chosen, a quotation that cannot be bound unambiguously, or an article-like
  mention in a form the Level-1 parser does not read (never silently skipped).
"""
from __future__ import annotations

import hashlib
import json
import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from application.litigation.corpus import ArticleRecord, load_corpus
from application.litigation.rule_results import RuleStatus
from application.litigation.suitability_rules import article_key
from application.litigation.unified_review import LegalObservation
from domains.disputes.statute_parser import (
    AnchoredStatuteCitation,
    extract_anchored_statute_citations,
)

ENGINE = "caseproof-legal-reference-check-v1"
_WS = re.compile(r"\s+")
_QUOTE = re.compile(r"«\s*(.+?)\s*»", re.DOTALL)
# A mention that looks like an article citation, whatever its exact form.
_MENTION = re.compile(r"(?<![\w])(?:art(?:icles?|ikels?)?\.?)\s+\d", re.IGNORECASE)
_BIND_GAP_MAX = 40
_QUOTE_MAX = 4000


LegalReferenceObservation = LegalObservation


def _norm(text: str) -> str:
    return _WS.sub(" ", text.replace("\u00a0", " ")).strip().casefold()


def _article_in_text(record: ArticleRecord) -> str:
    return _norm(record.derived_text)


def _bound_quotes(text: str, cite: AnchoredStatuteCitation,
                  others: Sequence[AnchoredStatuteCitation]) -> list[str]:
    """Quotations tied to this citation by position only (no semantics).

    After: « … » starts within a short gap after the citation, before the
    next citation, with no sentence end in the gap. Before: « … » ends right
    before the citation, allowing only "(", ",", ":" and spaces.
    """
    found: list[str] = []
    start, end = cite.span.start, cite.span.end
    next_start = min((o.span.start for o in others if o.span.start >= end), default=len(text))
    m = _QUOTE.search(text, end, next_start)
    if m and m.start() - end <= _BIND_GAP_MAX and not re.search(r"[.;!?]", text[end:m.start()]):
        found.append(m.group(1))
    previous_end = max((o.span.end for o in others if o.span.end <= start), default=0)
    for q in _QUOTE.finditer(text, previous_end, start):
        if re.fullmatch(r"[\s(,:]*", text[q.end():start]) and q.end() <= start:
            found.append(q.group(1))
    return found


def check_legal_references(
    text: str,
    records: Sequence[ArticleRecord],
    act_aliases: Mapping[str, str],
    *,
    chosen_versions: Mapping[str, str] | None = None,
) -> tuple[LegalReferenceObservation, ...]:
    """Check every cited article of ``text`` against the chosen corpus.

    ``act_aliases`` maps the parser's canonical code (for example "C.civ.") to
    the corpus act identity. It is DECLARED by the corpus owner, never guessed.
    ``chosen_versions`` maps a corpus act identity to the declared version to
    use when several versions are present.
    """
    if not isinstance(text, str):
        raise TypeError("brief text must be a string")
    cites = extract_anchored_statute_citations(text)
    # Standalone act citations ("Loi du ...") carry no article: not assessed here.
    article_cites = [c for c in cites if c.citation.article and not _is_act_date(c)]
    by_base: dict[str, list[ArticleRecord]] = {}
    for r in records:
        by_base.setdefault(r.base_key, []).append(r)
    out: list[LegalReferenceObservation] = []
    covered: list[tuple[int, int]] = []
    for index, cite in enumerate(article_cites, start=1):
        c = cite.citation
        covered.append((cite.span.start, cite.span.end))
        ref_id = f"legal-ref-{index:02d}"
        base: dict[str, Any] = dict(reference_id=ref_id, raw_text=c.raw_text, start=cite.span.start,
                    end=cite.span.end, act_code=c.code, article=c.article, language=c.language)
        act = act_aliases.get(c.code)
        if act is None:
            out.append(LegalReferenceObservation(
                **base, status=RuleStatus.UNDETERMINED,
                reason="act_not_mapped_to_chosen_corpus"))
            continue
        matches = by_base.get(article_key(act, c.article, c.language), [])
        if not matches:
            out.append(LegalReferenceObservation(
                **base, status=RuleStatus.UNVERIFIED,
                reason="article_absent_from_chosen_corpus"))
            continue
        record = None
        wanted = (chosen_versions or {}).get(act)
        if wanted is not None:
            picked = [r for r in matches if r.version == wanted]
            if not picked:
                out.append(LegalReferenceObservation(
                    **base, status=RuleStatus.UNDETERMINED,
                    reason="requested_version_absent_from_chosen_corpus"))
                continue
            if len(picked) == 1:
                record = picked[0]
        elif len(matches) == 1:
            record = matches[0]
        if record is None:
            out.append(LegalReferenceObservation(
                **base, status=RuleStatus.UNDETERMINED,
                reason="several_declared_versions_none_chosen"))
            continue
        ident: dict[str, Any] = dict(corpus_key=record.key, corpus_version=record.version,
                     corpus_text_sha256=record.derived_sha256,
                     corpus_source_uri=record.source_uri)
        quotes = [q for q in _bound_quotes(text, cite, article_cites) if q]
        if len(quotes) > 1 and len({_norm(q) for q in quotes}) > 1:
            out.append(LegalReferenceObservation(
                **base, **ident, status=RuleStatus.UNDETERMINED,
                reason="quotation_binding_ambiguous"))
            continue
        if not quotes:
            out.append(LegalReferenceObservation(
                **base, **ident, status=RuleStatus.PASS,
                reason="article_present_in_chosen_corpus_no_quotation_bound"))
            continue
        quote = quotes[0][:_QUOTE_MAX]
        if _norm(quote) in _article_in_text(record):
            out.append(LegalReferenceObservation(
                **base, **ident, quote=quote, status=RuleStatus.PASS,
                reason="quotation_found_verbatim_in_corpus_article"))
        else:
            out.append(LegalReferenceObservation(
                **base, **ident, quote=quote, status=RuleStatus.FAIL,
                reason="quotation_absent_from_corpus_article_text"))
    # Mentions the Level-1 parser could not read are surfaced, never skipped.
    n = len(out)
    for m in _MENTION.finditer(text):
        if any(s <= m.start() < e for s, e in covered):
            continue
        n += 1
        out.append(LegalReferenceObservation(
            reference_id=f"legal-ref-{n:02d}", raw_text=text[m.start():m.start() + 60],
            start=m.start(), end=min(len(text), m.start() + 60), act_code=None,
            article=None, language=None, status=RuleStatus.UNDETERMINED,
            reason="article_mention_not_readable_by_level1_parser"))
    return tuple(sorted(out, key=lambda o: o.start))


def _is_act_date(cite: AnchoredStatuteCitation) -> bool:
    """Standalone "Loi du ..." / "Wet van ..." citations carry no article."""
    return cite.citation.raw_text.lower().startswith(("loi du", "wet van"))


@dataclass(frozen=True, slots=True)
class LegalCorpusConfig:
    """The corpus chosen for a case plus its DECLARED act mapping."""

    records: tuple[ArticleRecord, ...]
    act_aliases: Mapping[str, str]
    chosen_versions: Mapping[str, str]
    failures: tuple[str, ...] = ()
    suitability: Any = None  # SuitabilityConfig (lawyer rules + confirmed facts), optional

    @property
    def pack_sha256(self) -> str:
        """Entire chosen pack and selection, including unavailable requested versions.

        This is an integrity identity, not an authenticity or completeness claim.
        The source bytes are addressed by their checked hashes, never re-fetched.
        """
        body = {
            "schema": "caseproof-corpus-selection-v1",
            "articles": sorted((
                {"key": r.key, "source_uri": r.source_uri, "acquired_at": r.acquired_at,
                 "consolidated": r.consolidated, "original_sha256": r.original_sha256,
                 "derived_sha256": r.derived_sha256, "source_artifact_kind": r.source_artifact_kind,
                 "source_notes": r.source_notes}
                for r in self.records), key=lambda row: str(row["key"])),
            "act_aliases": dict(self.act_aliases),
            "chosen_versions": dict(self.chosen_versions), "failures": list(self.failures),
        }
        return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True,
                                         separators=(",", ":")).encode()).hexdigest()


def load_corpus_config(directory: Path) -> LegalCorpusConfig:
    """Local, offline: corpus-manifest.toml plus optional act-aliases.toml.

    act-aliases.toml: ``[act_aliases]`` maps a parser code such as "C.civ." to a
    corpus act id; ``[chosen_versions]`` maps a corpus act id to a declared
    version. Both are written by the corpus owner, never inferred.
    """
    report = load_corpus(directory)
    aliases: dict[str, str] = {}
    versions: dict[str, str] = {}
    path = directory / "act-aliases.toml"
    if path.is_file():
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        for key, target in (data.get("act_aliases") or {}).items():
            if isinstance(key, str) and isinstance(target, str):
                aliases[key] = target
        for key, target in (data.get("chosen_versions") or {}).items():
            if isinstance(key, str) and isinstance(target, str):
                versions[key] = target
    from application.litigation.suitability_review import load_suitability_config
    suitability = load_suitability_config(directory)
    return LegalCorpusConfig(
        report.records, aliases, versions, report.failures, suitability)


def to_wire(obs: LegalReferenceObservation) -> dict[str, object]:
    """Wire form: the four-status verdict, its reason and its exact source."""
    return {
        "reference_id": obs.reference_id, "raw_text": obs.raw_text,
        "span": [obs.start, obs.end], "act_code": obs.act_code,
        "article": obs.article, "language": obs.language,
        "status": str(obs.status), "reason": obs.reason,
        "corpus_key": obs.corpus_key, "corpus_version": obs.corpus_version,
        "corpus_text_sha256": obs.corpus_text_sha256,
        "corpus_source_uri": obs.corpus_source_uri, "quote": obs.quote,
        "claim_support": "not_assessed",
    }


__all__ = [
    "ENGINE", "LegalCorpusConfig", "LegalReferenceObservation",
    "check_legal_references", "load_corpus_config", "to_wire",
]
