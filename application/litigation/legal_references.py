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
ENGINE_STRICT = "caseproof-legal-reference-check-v2"
# v3: wording that appeals to a legal authority. Cue words only: it flags for a human, it never judges.
_AUTHORITY_WINDOW = 150
_AUTHORITY_CUE = re.compile(
    r"(?i)\b(?:en vertu (?:de|du|des)|conform[ée]ment (?:à|au|aux)|jurisprudence|arr[êe]t(?:s)? de la cour|"
    r"cour de cassation|conseil d['’]\s?[ée]tat|la loi (?:dispose|impose|pr[ée]voit|exige)|"
    r"krachtens|overeenkomstig|rechtspraak|hof van cassatie|raad van state|de wet (?:bepaalt|bepaalt|schrijft|eist))\b")
ENGINE_STRICT3 = "caseproof-legal-reference-check-v3"
ENGINE_STRICT4 = "caseproof-legal-reference-check-v4"  # v3 + authority cues


def engine_mode(marker: object) -> tuple[bool, bool]:
    """(strict, v3) for a review's check_engine marker. Unmarked reviews replay with the original engine."""
    return marker in (ENGINE_STRICT, ENGINE_STRICT3, ENGINE_STRICT4), marker in (ENGINE_STRICT3, ENGINE_STRICT4)


def engine_authority(marker: object) -> bool:
    return marker == ENGINE_STRICT4
_WS = re.compile(r"\s+")
_QUOTE = re.compile(r"«\s*(.+?)\s*»", re.DOTALL)
# A mention that looks like an article citation, whatever its exact form.
_MENTION = re.compile(r"(?<![\w])(?:art(?:icles?|ikels?)?\.?)\s+\d", re.IGNORECASE)
_MENTION_STRICT = re.compile(r"(?<![\w])(?:art(?:icles?|ikels?)?\.?)\s*\d", re.IGNORECASE)
_QUOTE_STRICT = re.compile(r"«\s*(.+?)\s*»|\u201c\s*(.+?)\s*\u201d|\u201e\s*(.+?)\s*[\u201c\u201d]|\"\s*([^\"]+?)\s*\"", re.DOTALL)
# v3 also reads single curly, single low-9, angle and plain single quotes.
_QUOTE_V3 = re.compile(
    _QUOTE_STRICT.pattern
    + r"|\u2018\s*(.+?)\s*\u2019(?!\w)|\u201a\s*(.+?)\s*[\u2018\u2019](?!\w)|\u2039\s*(.+?)\s*\u203a"
    r"|(?<![\w'])'\s*([^'\n]+?)\s*'(?![\w'])", re.DOTALL)
# Opening marks that no pattern above consumed: shown as a finding, never skipped.
_QUOTE_OPENERS = re.compile("[\u00ab\u2018\u201a\u2039\u201c\u201e\"]")
_LOCATOR = re.compile(r"(?:\bal(?:in[ée]a|\.)\s*\d|§\s*\d|\b(?:lid|paragraaf|section|point|sous-section|littera|lit\.)\s*\d)",
                      re.IGNORECASE)
_STATUS_RANK = {"PASS": 0, "UNDETERMINED": 1, "FAIL": 2}
_BIND_GAP_MAX = 40
_QUOTE_MAX = 4000


LegalReferenceObservation = LegalObservation


def _norm(text: str) -> str:
    return _WS.sub(" ", text.replace("\u00a0", " ")).strip().casefold()


def _qtext(m: re.Match[str]) -> str:
    return next(g for g in m.groups() if g is not None)


def _norm_exact(text: str) -> str:
    """Whitespace and apostrophe shape only. Case, punctuation and letters stay exact."""
    return _WS.sub(" ", text.replace("\u00a0", " ").replace("\u2019", "'")).strip()


def _excerpt_issue(quote: str, article: str, body_start: str = "", v3: bool = False, attested: bool = False) -> str | None:
    """None when some literal occurrence starts and ends where a reader expects.

    A fragment that begins mid-sentence or mid-word, or stops before the sentence
    does, is literally present but omits context (for example an opening
    reservation). That needs a human decision, not a PASS.
    """
    start = article.find(quote)
    word_issue = False
    unattested_body = False
    while start != -1:
        end = start + len(quote)
        before = article[:start].rstrip()
        # Heading and body are flattened into one run in a text capture. The body start
        # is therefore declared in the corpus manifest. Without it, only a quote that
        # starts at the article's first character or after a sentence end can be complete.
        at_body = bool(body_start) and article.startswith(body_start, start) and article[:start].endswith(" ")
        sentence_ok = start == 0 or (article[start - 1] == " " and before[-1:] in ".;:!?")
        # v3: a declared body_start is preparer metadata, not publisher evidence. It can never
        # turn a quote that begins mid-sentence into a PASS; it only leaves it for a human.
        starts_ok = sentence_ok or (at_body and (not v3 or attested))
        word_ok = (start == 0 or not article[start - 1].isalnum()) and (end == len(article) or not article[end].isalnum())
        ends_ok = end == len(article) or quote[-1] in ".;:!?" or article[end] in ".;:!?"
        if starts_ok and word_ok and ends_ok:
            return None
        word_issue = word_issue or not word_ok
        unattested_body = unattested_body or (v3 and not attested and at_body and not sentence_ok and word_ok and ends_ok)
        start = article.find(quote, start + 1)
    if unattested_body and not word_issue:
        return "quotation_starts_at_declared_body_start_not_attested"
    return "quotation_starts_or_ends_mid_word" if word_issue else "quotation_partial_excerpt_review_required"


def _bound_quote_matches(text: str, cite: AnchoredStatuteCitation,
                         others: Sequence[AnchoredStatuteCitation],
                         qre: re.Pattern[str] = _QUOTE_STRICT) -> list[re.Match[str]]:
    found: list[re.Match[str]] = []
    start, end = cite.span.start, cite.span.end
    next_start = min((o.span.start for o in others if o.span.start >= end), default=len(text))
    m = qre.search(text, end, next_start)
    if m and m.start() - end <= _BIND_GAP_MAX and not re.search(r"[.;!?\n]", text[end:m.start()]):
        found.append(m)
    previous_end = max((o.span.end for o in others if o.span.end <= start), default=0)
    for q in qre.finditer(text, previous_end, start):
        if re.fullmatch(r"[ \t(,:]*", text[q.end():start]):
            found.append(q)
    return found


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
    strict: bool = False,
    v3: bool = False,
    authority: bool = False,
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
    qre = _QUOTE_V3 if v3 else _QUOTE_STRICT
    out: list[LegalReferenceObservation] = []
    covered: list[tuple[int, int]] = []
    bound_spans: list[tuple[int, int]] = []
    for index, cite in enumerate(article_cites, start=1):
        c = cite.citation
        covered.append((cite.span.start, cite.span.end))
        ref_id = f"legal-ref-{index:02d}"
        base: dict[str, Any] = dict(reference_id=ref_id, raw_text=c.raw_text, start=cite.span.start,
                    end=cite.span.end, act_code=c.code, article=c.article, language=c.language)
        act = act_aliases.get(c.code)
        qk: dict[str, Any] = {}
        if strict:
            early = _bound_quote_matches(text, cite, article_cites, qre)
            bound_spans.extend(m.span() for m in early)
            if early:
                qk = {"quote": _qtext(early[0])[:_QUOTE_MAX]}
        if strict and (_LOCATOR.search(c.raw_text) or _LOCATOR.search(
                text[max(0, cite.span.start - 40):cite.span.start] + " | " + text[cite.span.end:cite.span.end + 40].split("\n")[0])):
            out.append(LegalReferenceObservation(
                **base, **qk, status=RuleStatus.UNDETERMINED, reason="sub_article_locator_not_checked_in_corpus"))
            continue
        if act is None:
            out.append(LegalReferenceObservation(
                **base, **qk, status=RuleStatus.UNDETERMINED,
                reason="act_not_mapped_to_chosen_corpus"))
            continue
        matches = by_base.get(article_key(act, c.article, c.language), [])
        if not matches:
            out.append(LegalReferenceObservation(
                **base, **qk, status=RuleStatus.UNVERIFIED,
                reason="article_absent_from_chosen_corpus"))
            continue
        record = None
        wanted = (chosen_versions or {}).get(act)
        if wanted is not None:
            picked = [r for r in matches if r.version == wanted]
            if not picked:
                out.append(LegalReferenceObservation(
                    **base, **qk, status=RuleStatus.UNDETERMINED,
                    reason="requested_version_absent_from_chosen_corpus"))
                continue
            if len(picked) == 1:
                record = picked[0]
        elif len(matches) == 1:
            record = matches[0]
        if record is None:
            out.append(LegalReferenceObservation(
                **base, **qk, status=RuleStatus.UNDETERMINED,
                reason="several_declared_versions_none_chosen"))
            continue
        ident: dict[str, Any] = dict(corpus_key=record.key, corpus_version=record.version,
                     corpus_text_sha256=record.derived_sha256,
                     corpus_source_uri=record.source_uri)
        if strict:
            matches_q = _bound_quote_matches(text, cite, article_cites, qre)
            verdicts: list[tuple[str, str, str]] = []
            article_norm = _norm_exact(record.derived_text)
            for m in matches_q:
                raw_q = _qtext(m)[:_QUOTE_MAX]
                q = _norm_exact(raw_q)
                if not q:
                    continue
                if q not in article_norm:
                    verdicts.append(("FAIL", "quotation_absent_from_corpus_article_text", raw_q))
                    continue
                issue = _excerpt_issue(q, article_norm, _norm_exact(record.body_start), v3,
                                       record.body_start_basis == "publisher_pdf_layout")
                verdicts.append(("UNDETERMINED", issue, raw_q) if issue else
                                ("PASS", "quotation_found_verbatim_in_corpus_article", raw_q))
            if not verdicts:
                out.append(LegalReferenceObservation(
                    **base, **ident, status=RuleStatus.UNDETERMINED,
                    reason="article_exists_in_corpus_no_quotation_checked_claim_not_verified"))
                continue
            for k, (verdict_status, verdict_reason, verdict_quote) in enumerate(verdicts):
                row = dict(base, reference_id=base["reference_id"] if k == 0 else f"{base['reference_id']}-q{k + 1}")
                out.append(LegalReferenceObservation(
                    **row, **ident, quote=verdict_quote, status=RuleStatus(verdict_status), reason=verdict_reason))
            continue
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
    if strict:
        for qm in qre.finditer(text):
            if any(a <= qm.start() and qm.end() <= b or qm.span() == (a, b) for a, b in bound_spans):
                continue
            n += 1
            out.append(LegalReferenceObservation(
                reference_id=f"legal-ref-{n:02d}", raw_text=qm.group(0)[:60], start=qm.start(),
                end=min(len(text), qm.start() + 60), act_code=None, article=None, language=None,
                status=RuleStatus.UNDETERMINED, reason="quotation_not_bound_to_a_checked_reference",
                quote=_qtext(qm)[:_QUOTE_MAX]))
    if v3:
        parsed = [m.span() for m in qre.finditer(text)]
        for om in _QUOTE_OPENERS.finditer(text):
            if any(a <= om.start() < b for a, b in parsed):
                continue
            n += 1
            out.append(LegalReferenceObservation(
                reference_id=f"legal-ref-{n:02d}", raw_text=text[om.start():om.start() + 60], start=om.start(),
                end=min(len(text), om.start() + 60), act_code=None, article=None, language=None,
                status=RuleStatus.UNDETERMINED, reason="quotation_delimiter_not_recognised_text_not_checked"))
    mention_spans: list[tuple[int, int]] = []
    for m in (_MENTION_STRICT if strict else _MENTION).finditer(text):
        if any(s <= m.start() < e for s, e in covered):
            continue
        mention_spans.append(m.span())
        n += 1
        out.append(LegalReferenceObservation(
            reference_id=f"legal-ref-{n:02d}", raw_text=text[m.start():m.start() + 60],
            start=m.start(), end=min(len(text), m.start() + 60), act_code=None,
            article=None, language=None, status=RuleStatus.UNDETERMINED,
            reason="article_mention_not_readable_by_level1_parser"))
    if authority:
        # Authority asserted with no identifiable reference nearby: never silently skipped.
        known = covered + mention_spans
        last_end = -1
        for am in _AUTHORITY_CUE.finditer(text):
            if am.start() < last_end:
                continue
            line_start = text.rfind("\n", 0, am.start()) + 1
            line_end = text.find("\n", am.end())
            line_end = len(text) if line_end < 0 else line_end
            if any(line_start <= a and b <= line_end and abs(a - am.start()) <= _AUTHORITY_WINDOW for a, b in known):
                continue
            last_end = min(line_end, am.start() + _AUTHORITY_WINDOW)
            n += 1
            out.append(LegalReferenceObservation(
                reference_id=f"legal-ref-{n:02d}", raw_text=text[am.start():am.start() + 60],
                start=am.start(), end=min(len(text), am.start() + 60), act_code=None,
                article=None, language=None, status=RuleStatus.UNDETERMINED,
                reason="legal_authority_asserted_without_identifiable_reference_not_checked"))
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
                 "source_notes": r.source_notes, **({"body_start": r.body_start} if r.body_start else {}),
                 **({"original_text_layer_sha256": r.original_text_layer_sha256,
                     "body_start_basis": r.body_start_basis} if r.original_text_layer_sha256 else {})}
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
