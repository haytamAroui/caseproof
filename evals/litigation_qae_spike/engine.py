"""Deterministic mechanical verification, hardening, and Tier-1 isolation engine.

None of the rules in this module promote a Level-1 model candidate to truth.
All reconciled conflicts remain Level-2 ``mechanically_grounded_lead`` entries
requiring explicit Level-3 lawyer confirmation bound to exact source hashes.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any, Literal

from domains.disputes.dossier_verification import build_findings
from domains.disputes.reference_detection import (
    ExhibitReference,
    detect_exhibit_references,
    detect_unsupported_references,
)
from evals.litigation_qae_spike.contracts import (
    ActionKind,
    ContentReleaseGrant,
    EntityLinkProof,
    EntityLinkStatus,
    IndexedDocument,
    LawyerActionState,
    MechanicallyGroundedLead,
    ModelCandidate,
    PageTextBlock,
    QaeCoverageManifest,
    ReconciledReviewLead,
    TransmissionManifest,
    TransmittedExcerpt,
    VisualAnchorStatus,
    VisualBox,
    canonical_digest,
)

# Unified FR/NL/EN negation, reservation, and status-qualifier vocabulary.
_CAUTION_CUE_RE = re.compile(
    r"(?:"
    r"\bsauf\b|\bhormis\b|\bexcept[ée]\b|\bsous\s+r[ée]serve\b|\bsans\s+pr[ée]judice\b|"
    r"\b[àa]\s+moins\s+que\b|\b[àa]\s+l['’]exception\b|\bpour\s+autant\s+que\b|"
    r"\benvoy[ée]\s+pour\s+signature\b|\bprojet\b|\bnon\s+sign[ée]\b|"
    r"\bne\b|\bn['’]|\bpas\b|\bjamais\b|\baucun(?:e)?\b|"
    r"\bbehoudens\b|\bonverminderd\b|\bonder\s+voorbehoud\b|\bmet\s+uitzondering\b|"
    r"\btenzij\b|\bter\s+ondertekening\s+verstuurd\b|\bontwerp\b|"
    r"\bniet\b|\bgeen\b|\bnooit\b|"
    r"\bunless\b|\bwithout\b|\bnever\b|\bnot\b|\bsubject\s+to\b|\bdraft\b|\balleged(?:ly)?\b"
    r")",
    re.IGNORECASE,
)

_AMOUNT_TOKEN_RE = re.compile(
    r"(?:€|eur)\s*\d[\d\s.,]*|\d+(?:[.,\s]\d{3})*(?:[.,]\d{2})?\s*(?:€|eur)\b",
    re.IGNORECASE,
)

_MONTHS: dict[str, int] = {
    "janvier": 1, "januari": 1, "january": 1,
    "février": 2, "fevrier": 2, "februari": 2, "february": 2,
    "mars": 3, "maart": 3, "march": 3,
    "avril": 4, "april": 4,
    "mai": 5, "mei": 5, "may": 5,
    "juin": 6, "juni": 6, "june": 6,
    "juillet": 7, "juli": 7, "july": 7,
    "août": 8, "aout": 8, "augustus": 8, "august": 8,
    "septembre": 9, "september": 9,
    "octobre": 10, "oktober": 10, "october": 10,
    "novembre": 11, "november": 11,
    "décembre": 12, "decembre": 12, "december": 12,
}

_DATE_TOKEN_RE = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|"
    r"(?:1er|\d{1,2})\s+(?:" + "|".join(_MONTHS) + r")\s+\d{4})\b",
    re.IGNORECASE,
)

_SHORTLIST_KEYWORDS_RE = re.compile(
    r"\b(?:avoir|note\s+de\s+cr[ée]dit|creditnota|avenant|r[ée]siliation|"
    r"opzegging|envoy[ée]\s+pour\s+signature|ter\s+ondertekening|ontwerp|projet)\b",
    re.IGNORECASE,
)

_SIGN_STATUS_DRAFT = frozenset({"sent_for_signature", "draft", "proposal", "unsigned"})
_SIGN_STATUS_SIGNED = frozenset({"signed", "executed", "binding"})


@dataclass(frozen=True, slots=True)
class _TextDiscovery:
    """Minimal discovery contract consumed by Tier-1 ``build_findings``."""

    references: tuple[ExhibitReference, ...]
    unsupported_references: tuple[ExhibitReference, ...]
    unscanned_parts: tuple[str, ...]
    text_coverage_complete: bool


def index_document_blocks(
    *,
    exhibit_id: str,
    document_id: str,
    version_id: str,
    representation_id: str,
    pages: Sequence[tuple[int, Sequence[tuple[str, tuple[VisualBox, ...]]], bool]],
) -> IndexedDocument:
    """Build an immutable block/page index preserving offsets and visual-box lineage."""
    parts: list[str] = []
    blocks: list[PageTextBlock] = []
    uncertain_pages: list[int] = []
    cursor = 0
    preliminary: list[tuple[str, int, int, int, str, tuple[VisualBox, ...], bool]] = []
    block_counter = 0

    for pdf_page, raw_blocks, ocr_uncertain in pages:
        if ocr_uncertain and pdf_page not in uncertain_pages:
            uncertain_pages.append(pdf_page)
        for text, boxes in raw_blocks:
            if parts:
                parts.append("\n")
                cursor += 1
            block_counter += 1
            block_id = f"{exhibit_id}:p{pdf_page}:b{block_counter}"
            start = cursor
            parts.append(text)
            cursor += len(text)
            preliminary.append((block_id, pdf_page, start, cursor, text, boxes, ocr_uncertain))

    full_text = "".join(parts)
    rep_sha = sha256(full_text.encode("utf-8")).hexdigest()
    ver_sha = canonical_digest({"document_id": document_id, "version_id": version_id, "rep_sha": rep_sha})
    for block_id, pdf_page, start, end, text, boxes, ocr_uncertain in preliminary:
        blocks.append(
            PageTextBlock(
                block_id=block_id,
                exhibit_id=exhibit_id,
                document_id=document_id,
                version_id=version_id,
                representation_id=representation_id,
                representation_sha256=rep_sha,
                pdf_page=pdf_page,
                char_start=start,
                char_end=end,
                text=text,
                visual_bboxes=boxes,
                ocr_uncertain=ocr_uncertain,
            )
        )
    return IndexedDocument(
        exhibit_id=exhibit_id,
        document_id=document_id,
        version_id=version_id,
        version_sha256=ver_sha,
        representation_id=representation_id,
        representation_sha256=rep_sha,
        full_text=full_text,
        blocks=tuple(blocks),
        ocr_uncertain_pages=tuple(uncertain_pages),
    )


def _sentence_bounds_crossing_blocks(full_text: str, start: int, end: int) -> tuple[int, int]:
    """Expand a span across block boundaries (\\n) to containing + adjacent sentences."""
    if not full_text:
        return 0, 0
    boundaries: list[int] = []
    for idx, ch in enumerate(full_text):
        if ch not in ".!?":
            continue
        # Decimal/thousands separator inside digits is not a sentence boundary.
        if ch == "." and 0 < idx < len(full_text) - 1 and full_text[idx - 1].isdigit() and full_text[idx + 1].isdigit():
            continue
        boundaries.append(idx)

    before = [b for b in boundaries if b < start]
    after = [b for b in boundaries if b >= end]
    # Expand one extra sentence backward and one extra sentence forward across block/page boundaries.
    ctx_start = (before[-2] + 1) if len(before) >= 2 else 0
    ctx_end = (after[1] + 1) if len(after) >= 2 else len(full_text)
    while ctx_start < len(full_text) and full_text[ctx_start].isspace():
        ctx_start += 1
    return ctx_start, ctx_end


def _containing_sentence(full_text: str, start: int, end: int) -> str:
    """Extract the single containing sentence (ignoring newline block breaks)."""
    boundaries = [
        idx
        for idx, ch in enumerate(full_text)
        if ch in ".!?"
        and not (
            ch == "."
            and 0 < idx < len(full_text) - 1
            and full_text[idx - 1].isdigit()
            and full_text[idx + 1].isdigit()
        )
    ]
    left = max((b + 1 for b in boundaries if b < start), default=0)
    right = min((b + 1 for b in boundaries if b >= end), default=len(full_text))
    return " ".join(full_text[left:right].split())


def verify_and_harden_candidate(
    candidate: ModelCandidate,
    document: IndexedDocument,
) -> tuple[MechanicallyGroundedLead | None, str | None]:
    """Mechanically locate an exact quote and attach cross-block, scalar, and pixel guards."""
    quote = candidate.quote
    if not quote.strip():
        return None, "empty_quote"
    first = document.full_text.find(quote)
    if first < 0:
        return None, "quote_not_found"
    if document.full_text.find(quote, first + 1) >= 0:
        return None, "ambiguous_quote"
    end = first + len(quote)

    spanned_blocks = tuple(
        blk for blk in document.blocks if blk.char_start < end and blk.char_end > first
    )
    if not spanned_blocks:
        return None, "block_lineage_missing"

    ctx_start, ctx_end = _sentence_bounds_crossing_blocks(document.full_text, first, end)
    surrounding_context = " ".join(document.full_text[ctx_start:ctx_end].split())
    containing_sentence = _containing_sentence(document.full_text, first, end)

    warnings: list[str] = []
    cues_in_context = [m.group(0).lower() for m in _CAUTION_CUE_RE.finditer(surrounding_context)]
    cues_in_quote = [m.group(0).lower() for m in _CAUTION_CUE_RE.finditer(quote)]
    if cues_in_context:
        warnings.append("SURROUNDING_NEGATION_OR_RESERVATION_DETECTED")
        if len(cues_in_context) > len(cues_in_quote) or candidate.polarity == "affirmative":
            warnings.append("TRUNCATED_QUOTE_OMITTED_CONTEXT_CUE")

    amount_hits = _AMOUNT_TOKEN_RE.findall(containing_sentence)
    date_hits = _DATE_TOKEN_RE.findall(containing_sentence)
    if len(amount_hits) >= 2 or len(date_hits) >= 2:
        warnings.append("MULTI_SCALAR_SENTENCE_ROLE_UNVERIFIED")

    boxes = tuple(box for blk in spanned_blocks for box in blk.visual_bboxes)
    any_missing_boxes = any(not blk.visual_bboxes for blk in spanned_blocks)
    visual_status: VisualAnchorStatus = (
        "visual_anchor_unavailable" if any_missing_boxes or not boxes else "visual_boxes_attached"
    )
    if visual_status == "visual_anchor_unavailable":
        warnings.append("VISUAL_ANCHOR_UNAVAILABLE")

    spanned_pages = tuple(sorted({blk.pdf_page for blk in spanned_blocks}))
    if any(p in document.ocr_uncertain_pages or blk.ocr_uncertain for p in spanned_pages for blk in spanned_blocks):
        warnings.append("OCR_UNRELIABLE_SOURCE_PAGE")

    lead_id = canonical_digest(
        {
            "doc": document.version_sha256,
            "rep": document.representation_sha256,
            "start": first,
            "end": end,
            "entity": candidate.entity_id,
            "slot": candidate.slot,
            "signal": candidate.signal,
            "raw_value": candidate.raw_value,
        }
    )[:16]
    return (
        MechanicallyGroundedLead(
            lead_id=f"lead-{lead_id}",
            epistemic_level="mechanically_grounded_lead",
            source_exhibit_id=document.exhibit_id,
            document_id=document.document_id,
            version_id=document.version_id,
            version_sha256=document.version_sha256,
            representation_id=document.representation_id,
            representation_sha256=document.representation_sha256,
            char_start=first,
            char_end=end,
            spanned_pages=spanned_pages,
            spanned_block_ids=tuple(blk.block_id for blk in spanned_blocks),
            visual_anchor_status=visual_status,
            visual_bboxes=boxes,
            quote=quote,
            surrounding_context=surrounding_context,
            entity_id=candidate.entity_id,
            slot=candidate.slot,
            signal=candidate.signal,
            raw_value=candidate.raw_value,
            polarity=candidate.polarity,
            warnings=tuple(dict.fromkeys(warnings)),
            candidate_provenance={
                "candidate_id": candidate.candidate_id,
                "provider": candidate.provider,
                "model": candidate.model,
                "prompt_version": candidate.prompt_version,
            },
        ),
        None,
    )


def normalize_belgian_money(raw: str) -> Decimal | None:
    """Parse unambiguous Belgian FR/NL or standard decimal amounts; refuse ambiguous commas."""
    cleaned = re.sub(r"(?:€|eur)", "", raw, flags=re.IGNORECASE).strip()
    cleaned = cleaned.replace("\u00a0", " ").replace(" ", "")
    if not cleaned:
        return None
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d{2})?", cleaned):
        normalized = cleaned.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d+(?:,\d{1,2})?", cleaned):
        normalized = cleaned.replace(",", ".")
    elif re.fullmatch(r"\d+(?:\.\d{1,2})?", cleaned):
        normalized = cleaned
    else:
        # e.g. "12,500" (3 digits after comma) is ambiguous between 12.5 and 12500.
        return None
    try:
        dec = Decimal(normalized)
    except InvalidOperation:
        return None
    return dec if dec.is_finite() else None


def normalize_belgian_date(raw: str) -> date | None:
    """Parse explicit ISO, Belgian DD/MM/YYYY, or FR/NL/EN named-month dates."""
    text = " ".join(raw.strip().casefold().split())
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
    dmy = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if dmy:
        day_n, month_n, year_n = int(dmy.group(1)), int(dmy.group(2)), int(dmy.group(3))
        if day_n <= 12 and month_n <= 12 and day_n != month_n:
            return None
        try:
            return date(year_n, month_n, day_n)
        except ValueError:
            return None
    named = re.fullmatch(r"(1er|\d{1,2})\s+([a-zà-ÿ]+)\s+(\d{4})", text)
    if named:
        day_n = 1 if named.group(1) == "1er" else int(named.group(1))
        month_n_opt = _MONTHS.get(named.group(2))
        if month_n_opt is None:
            return None
        try:
            return date(int(named.group(3)), month_n_opt, day_n)
        except ValueError:
            return None
    return None


def shortlist_uncited_exhibits(
    *,
    cited_exhibit_ids: set[str],
    reference_tokens: set[str],
    documents: Mapping[str, IndexedDocument],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Deterministic 2-stage funnel for uncited exhibits; explicitly names excluded exhibits."""
    shortlisted: list[str] = []
    excluded: list[str] = []
    tokens_lower = {tok.casefold() for tok in reference_tokens if tok.strip()}
    for exhibit_id in sorted(documents):
        if exhibit_id in cited_exhibit_ids:
            continue
        doc = documents[exhibit_id]
        if doc.ocr_uncertain_pages and not doc.full_text.strip():
            excluded.append(exhibit_id)
            continue
        haystack = doc.full_text.casefold()
        has_token = any(tok in haystack for tok in tokens_lower)
        has_keyword = _SHORTLIST_KEYWORDS_RE.search(doc.full_text) is not None
        if has_token or has_keyword:
            shortlisted.append(exhibit_id)
        else:
            excluded.append(exhibit_id)
    return tuple(shortlisted), tuple(excluded)


def build_minimized_transmission(
    *,
    documents: Mapping[str, IndexedDocument],
    selected_blocks: Sequence[tuple[str, str]],
    release: ContentReleaseGrant,
) -> tuple[list[dict[str, Any]], TransmissionManifest]:
    """Minimize provider payload to explicitly selected blocks and emit a zero-text manifest."""
    if not release.authorized:
        raise PermissionError("explicit authorized ContentReleaseGrant required before transmission")

    full_bundle_chars = sum(len(doc.full_text) for doc in documents.values())
    block_lookup: dict[tuple[str, str], PageTextBlock] = {
        (exhibit_id, blk.block_id): blk
        for exhibit_id, doc in documents.items()
        for blk in doc.blocks
    }
    payload_items: list[dict[str, Any]] = []
    excerpts: list[TransmittedExcerpt] = []
    total_chars = 0

    for exhibit_id, block_id in selected_blocks:
        blk = block_lookup.get((exhibit_id, block_id))
        if blk is None:
            raise ValueError(f"unknown block {exhibit_id}/{block_id}")
        total_chars += len(blk.text)
        if total_chars > release.max_total_chars:
            raise ValueError("minimized payload exceeds ContentReleaseGrant character budget")
        payload_items.append(
            {
                "exhibit_id": exhibit_id,
                "block_id": block_id,
                "pdf_page": blk.pdf_page,
                "text": blk.text,
            }
        )
        excerpts.append(
            TransmittedExcerpt(
                exhibit_id=exhibit_id,
                pdf_page=blk.pdf_page,
                block_id=block_id,
                char_start=blk.char_start,
                char_end=blk.char_end,
                excerpt_sha256=sha256(blk.text.encode("utf-8")).hexdigest(),
                char_count=len(blk.text),
            )
        )

    manifest = TransmissionManifest(
        release_id=release.release_id,
        destination=release.destination,
        retention_policy=release.retention_policy,
        total_chars_sent=total_chars,
        full_bundle_chars=full_bundle_chars,
        excerpts=tuple(excerpts),
        raw_text_logged=False,
    )
    return payload_items, manifest


def _resolve_entity_link(
    *,
    entity_id: str,
    exhibit_a: str,
    exhibit_b: str,
    entity_links: Sequence[EntityLinkProof],
) -> tuple[EntityLinkStatus, tuple[str, ...]]:
    for proof in entity_links:
        if proof.entity_id == entity_id and {exhibit_a, exhibit_b}.issubset(set(proof.source_exhibit_ids)):
            if proof.link_basis == "human_confirmed":
                return "human_confirmed", ()
            if proof.link_basis == "explicit_reference_id":
                return "explicit_reference_id", ()
    return "unconfirmed_bordereau_insufficient", ("ENTITY_LINK_UNCONFIRMED_BORDEREAU_INSUFFICIENT",)


def _combined_visual_status(
    a: MechanicallyGroundedLead,
    b: MechanicallyGroundedLead,
) -> VisualAnchorStatus:
    if a.visual_anchor_status == "visual_anchor_unavailable" or b.visual_anchor_status == "visual_anchor_unavailable":
        return "visual_anchor_unavailable"
    return "visual_boxes_attached"


def reconcile_litigation_leads(
    *,
    brief_leads: Sequence[MechanicallyGroundedLead],
    exhibit_leads: Sequence[MechanicallyGroundedLead],
    entity_links: Sequence[EntityLinkProof],
    bordereau_confirmed: bool,
    max_p0: int = 8,
) -> tuple[tuple[ReconciledReviewLead, ...], tuple[ReconciledReviewLead, ...]]:
    """Run pure-Python litigation reconciliation rules emitting Level-2 leads only."""
    if max_p0 < 0:
        raise ValueError("max_p0 must be non-negative")
    all_leads: list[ReconciledReviewLead] = []

    for brief in brief_leads:
        matching = [ex for ex in exhibit_leads if ex.entity_id == brief.entity_id]
        for exhibit in matching:
            link_status, link_warnings = _resolve_entity_link(
                entity_id=brief.entity_id,
                exhibit_a=brief.source_exhibit_id,
                exhibit_b=exhibit.source_exhibit_id,
                entity_links=entity_links,
            )
            extra_warnings: list[str] = list(
                dict.fromkeys((*brief.warnings, *exhibit.warnings, *link_warnings))
            )
            if not bordereau_confirmed and "BORDEREAU_UNCONFIRMED" not in extra_warnings:
                extra_warnings.append("BORDEREAU_UNCONFIRMED")
            vis_status = _combined_visual_status(brief, exhibit)

            if "OCR_UNRELIABLE_SOURCE_PAGE" in exhibit.warnings:
                all_leads.append(
                    _make_reconciled(
                        rule_code="OCR_UNRELIABLE_MANUAL_INSPECTION_REQUIRED",
                        brief=brief,
                        exhibit=exhibit,
                        summary="Source page OCR uncertain: automatic comparison withheld.",
                        warnings=tuple(extra_warnings),
                        link_status=link_status,
                        vis_status=vis_status,
                        details={"skipped_comparison": True},
                    )
                )
                continue

            # Rule 1: Status shift or surrounding reservation/negation cue on contract status.
            if brief.slot == "contract_status" and exhibit.slot == "contract_status":
                b_val, e_val = brief.raw_value.casefold(), exhibit.raw_value.casefold()
                status_mismatch = (
                    (b_val in _SIGN_STATUS_SIGNED and e_val in _SIGN_STATUS_DRAFT)
                    or b_val != e_val
                    or "SURROUNDING_NEGATION_OR_RESERVATION_DETECTED" in exhibit.warnings
                )
                if status_mismatch:
                    all_leads.append(
                        _make_reconciled(
                            rule_code="STATUS_SHIFT_CANDIDATE",
                            brief=brief,
                            exhibit=exhibit,
                            summary=(
                                f"Conclusion states '{brief.raw_value}' while {exhibit.source_exhibit_id} "
                                f"states '{exhibit.raw_value}' with context cues."
                            ),
                            warnings=tuple(extra_warnings),
                            link_status=link_status,
                            vis_status=vis_status,
                            details={
                                "brief_value": brief.raw_value,
                                "exhibit_value": exhibit.raw_value,
                                "exhibit_context": exhibit.surrounding_context,
                            },
                        )
                    )
                    continue

            # Rule 2: Same-slot bilingual amount or date discrepancy (preserving multi-scalar guard).
            if brief.slot == exhibit.slot:
                amt_b = normalize_belgian_money(brief.raw_value)
                amt_e = normalize_belgian_money(exhibit.raw_value)
                if amt_b is not None and amt_e is not None and (amt_b != amt_e or extra_warnings):
                    all_leads.append(
                        _make_reconciled(
                            rule_code="BILINGUAL_SCALAR_DIFFERENCE_CANDIDATE",
                            brief=brief,
                            exhibit=exhibit,
                            summary=f"Decimal difference candidate: brief={amt_b} vs exhibit={amt_e}.",
                            warnings=tuple(extra_warnings),
                            link_status=link_status,
                            vis_status=vis_status,
                            details={"brief_decimal": str(amt_b), "exhibit_decimal": str(amt_e), "diff": str(amt_b - amt_e)},
                        )
                    )
                    continue
                date_b = normalize_belgian_date(brief.raw_value)
                date_e = normalize_belgian_date(exhibit.raw_value)
                if date_b is not None and date_e is not None and (date_b != date_e or extra_warnings):
                    all_leads.append(
                        _make_reconciled(
                            rule_code="BILINGUAL_DATE_DIFFERENCE_CANDIDATE",
                            brief=brief,
                            exhibit=exhibit,
                            summary=f"Date review candidate: brief={date_b.isoformat()} vs exhibit={date_e.isoformat()}.",
                            warnings=tuple(extra_warnings),
                            link_status=link_status,
                            vis_status=vis_status,
                            details={"brief_date": date_b.isoformat(), "exhibit_date": date_e.isoformat()},
                        )
                    )
                    continue

            # Rule 3: Cross-exhibit credit-note / counter-payment contradiction candidate.
            if brief.slot == "amount_claimed" and exhibit.slot in {"credit_note_amount", "amount_paid"}:
                amt_b = normalize_belgian_money(brief.raw_value)
                amt_e = normalize_belgian_money(exhibit.raw_value)
                if amt_b is not None and amt_e is not None:
                    all_leads.append(
                        _make_reconciled(
                            rule_code="CROSS_EXHIBIT_CONFLICT_CANDIDATE",
                            brief=brief,
                            exhibit=exhibit,
                            summary=(
                                f"Claimed {amt_b} EUR vs {exhibit.source_exhibit_id} ({exhibit.slot}={amt_e} EUR)."
                            ),
                            warnings=tuple(extra_warnings),
                            link_status=link_status,
                            vis_status=vis_status,
                            details={
                                "claimed_eur": str(amt_b),
                                "counter_eur": str(amt_e),
                                "net_remaining_eur": str(amt_b - amt_e),
                            },
                        )
                    )

            # Fallback: truncated negation or surrounding reservation warning even if scalar matches.
            if (
                "SURROUNDING_NEGATION_OR_RESERVATION_DETECTED" in exhibit.warnings
                or "MULTI_SCALAR_SENTENCE_ROLE_UNVERIFIED" in exhibit.warnings
            ) and not any(lead.exhibit_lead_id == exhibit.lead_id and lead.brief_lead_id == brief.lead_id for lead in all_leads):
                all_leads.append(
                    _make_reconciled(
                        rule_code="SURROUNDING_CONTEXT_TRAP_CANDIDATE",
                        brief=brief,
                        exhibit=exhibit,
                        summary="Context warning requires human passage inspection.",
                        warnings=tuple(extra_warnings),
                        link_status=link_status,
                        vis_status=vis_status,
                        details={"exhibit_context": exhibit.surrounding_context},
                    )
                )

    p0: list[ReconciledReviewLead] = []
    deferred: list[ReconciledReviewLead] = []
    for idx, lead in enumerate(all_leads):
        priority = "P0" if idx < max_p0 else "deferred"
        item = ReconciledReviewLead(
            lead_id=lead.lead_id,
            rule_code=lead.rule_code,
            priority=priority,
            epistemic_level="mechanically_grounded_lead",
            brief_lead_id=lead.brief_lead_id,
            exhibit_lead_id=lead.exhibit_lead_id,
            summary=lead.summary,
            warnings=lead.warnings,
            entity_link_status=lead.entity_link_status,
            visual_anchor_status=lead.visual_anchor_status,
            details=lead.details,
        )
        if priority == "P0":
            p0.append(item)
        else:
            deferred.append(item)
    return tuple(p0), tuple(deferred)


def _make_reconciled(
    *,
    rule_code: str,
    brief: MechanicallyGroundedLead,
    exhibit: MechanicallyGroundedLead,
    summary: str,
    warnings: tuple[str, ...],
    link_status: EntityLinkStatus,
    vis_status: VisualAnchorStatus,
    details: dict[str, Any],
) -> ReconciledReviewLead:
    lead_id = canonical_digest(
        {"rule": rule_code, "brief": brief.lead_id, "exhibit": exhibit.lead_id}
    )[:16]
    return ReconciledReviewLead(
        lead_id=f"rec-{lead_id}",
        rule_code=rule_code,
        priority="P0",
        epistemic_level="mechanically_grounded_lead",
        brief_lead_id=brief.lead_id,
        exhibit_lead_id=exhibit.lead_id,
        summary=summary,
        warnings=warnings,
        entity_link_status=link_status,
        visual_anchor_status=vis_status,
        details=details,
    )


def record_source_open(state: LawyerActionState, *, opened_at: str) -> LawyerActionState:
    """Opening a PDF page records an access trace ONLY; semantic support remains NOT_ASSESSED."""
    return LawyerActionState(
        lead_id=state.lead_id,
        bound_source_sha256=state.bound_source_sha256,
        source_opened_at=opened_at,
        explicit_action=state.explicit_action,
        human_semantic_support=state.human_semantic_support,
        actor_id=state.actor_id,
    )


def apply_lawyer_action(
    state: LawyerActionState,
    *,
    expected_source_sha256: str,
    action: ActionKind,
    actor_id: str,
) -> LawyerActionState:
    """Apply an explicit version-bound lawyer action; reject/waive never confirm support."""
    if not actor_id.strip():
        raise ValueError("authorized actor_id required")
    if expected_source_sha256 != state.bound_source_sha256:
        raise ValueError("stale source snapshot")
    if action == "confirm_discrepancy":
        support = "CONFIRMED_CONTRADICTED"
    elif action == "qualify":
        support = "CONFIRMED_QUALIFIED"
    else:
        # Rejecting or waiving a QAE lead never turns it into CONFIRMED_SUPPORTED.
        support = "NOT_ASSESSED"
    return LawyerActionState(
        lead_id=state.lead_id,
        bound_source_sha256=state.bound_source_sha256,
        source_opened_at=state.source_opened_at,
        explicit_action=action,
        human_semantic_support=support,
        actor_id=actor_id,
    )


def run_tier1_dossier_check(
    *,
    brief_text: str,
    documents: Mapping[str, IndexedDocument],
    bordereau_entries: Sequence[dict[str, Any]],
    bordereau_confirmed: bool,
) -> tuple[dict[str, Any], str]:
    """Execute the real deterministic Tier-1 engine (domains.disputes) and hash its output."""
    region = "word/document.xml"
    refs = detect_exhibit_references(brief_text, region=region)
    unsupported = detect_unsupported_references(brief_text, region=region)
    discovery = _TextDiscovery(
        references=refs,
        unsupported_references=unsupported,
        unscanned_parts=(),
        text_coverage_complete=True,
    )
    sources = [
        {
            "role": "exhibit",
            "document_id": doc.document_id,
            "version_id": doc.version_id,
            "sha256": doc.version_sha256,
            "page_count": max((blk.pdf_page for blk in doc.blocks), default=1),
            "image_only_pages": list(doc.ocr_uncertain_pages),
        }
        for doc in documents.values()
        if doc.exhibit_id != "brief"
    ]
    confirmation = {
        "payload": {
            "inventory_complete": bordereau_confirmed,
            "entries": list(bordereau_entries),
            "exceptions": [] if bordereau_confirmed else ["inventory_unconfirmed"],
        }
    }
    report = build_findings(discovery, {region: brief_text}, sources, confirmation)
    return report, canonical_digest(report)


def run_two_tier_evaluation(
    *,
    brief_text: str,
    documents: Mapping[str, IndexedDocument],
    bordereau_entries: Sequence[dict[str, Any]],
    bordereau_confirmed: bool,
    entity_links: Sequence[EntityLinkProof],
    release: ContentReleaseGrant,
    selected_blocks: Sequence[tuple[str, str]],
    provider_fn: Callable[[list[dict[str, Any]]], Sequence[ModelCandidate]] | None,
    reference_tokens: set[str] | None = None,
    max_p0: int = 8,
) -> dict[str, Any]:
    """Run independent Tier 1 plus exception-isolated optional Tier 2."""
    tier1_report, tier1_digest = run_tier1_dossier_check(
        brief_text=brief_text,
        documents=documents,
        bordereau_entries=bordereau_entries,
        bordereau_confirmed=bordereau_confirmed,
    )
    bundle_ids = tuple(sorted(k for k in documents if k != "brief"))
    cited_ids = {eid for eid, _ in selected_blocks if eid != "brief"}
    shortlisted, excluded = shortlist_uncited_exhibits(
        cited_exhibit_ids=cited_ids,
        reference_tokens=reference_tokens or set(),
        documents={k: v for k, v in documents.items() if k != "brief"},
    )
    unreadable_pages = tuple(
        f"{doc.exhibit_id}#p{page}"
        for doc in documents.values()
        if doc.exhibit_id != "brief"
        for page in doc.ocr_uncertain_pages
    )

    if provider_fn is None:
        coverage = QaeCoverageManifest(
            exhibits_in_bundle=bundle_ids,
            exhibits_read_by_qae=(),
            unread_exhibits=bundle_ids,
            unreadable_ocr_pages=unreadable_pages,
            excluded_by_preselection=excluded,
            p0_leads_count=0,
            deferred_leads_count=0,
            rejected_candidates_count=0,
            model_status="failed_or_unavailable",
        )
        return {
            "tier1_report": tier1_report,
            "tier1_digest": tier1_digest,
            "tier2": None,
            "coverage_manifest": coverage,
        }

    # Combine cited blocks with deterministically shortlisted uncited exhibit blocks.
    scoped_blocks = list(selected_blocks)
    for eid in shortlisted:
        for blk in documents[eid].blocks:
            pair = (eid, blk.block_id)
            if pair not in scoped_blocks:
                scoped_blocks.append(pair)

    payload_items, transmission_manifest = build_minimized_transmission(
        documents=documents,
        selected_blocks=scoped_blocks,
        release=release,
    )
    read_exhibits = tuple(sorted({item["exhibit_id"] for item in payload_items if item["exhibit_id"] != "brief"}))
    unread_exhibits = tuple(sorted(set(bundle_ids) - set(read_exhibits)))

    ModelStatus = Literal["completed", "partial_failure", "failed_or_unavailable"]
    try:
        candidates = list(provider_fn(payload_items))
        model_status: ModelStatus = "completed"
    except Exception as exc:  # Provider failure MUST leave Tier 1 completely untouched.
        coverage = QaeCoverageManifest(
            exhibits_in_bundle=bundle_ids,
            exhibits_read_by_qae=(),
            unread_exhibits=bundle_ids,
            unreadable_ocr_pages=unreadable_pages,
            excluded_by_preselection=excluded,
            p0_leads_count=0,
            deferred_leads_count=0,
            rejected_candidates_count=0,
            model_status="failed_or_unavailable",
        )
        return {
            "tier1_report": tier1_report,
            "tier1_digest": tier1_digest,
            "tier2": {
                "error_type": type(exc).__name__,
                "p0_leads": (),
                "deferred_leads": (),
                "rejected_candidates": (),
                "transmission_manifest": asdict(transmission_manifest),
            },
            "coverage_manifest": coverage,
        }

    if not candidates:
        model_status = "failed_or_unavailable"

    brief_leads: list[MechanicallyGroundedLead] = []
    exhibit_leads: list[MechanicallyGroundedLead] = []
    rejected: list[tuple[str, str]] = []
    for cand in candidates:
        doc = documents.get(cand.exhibit_id)
        if doc is None:
            rejected.append((cand.candidate_id, "unknown_exhibit_id"))
            continue
        lead, err = verify_and_harden_candidate(cand, doc)
        if lead is None:
            rejected.append((cand.candidate_id, err or "rejected"))
        elif cand.exhibit_id == "brief":
            brief_leads.append(lead)
        else:
            exhibit_leads.append(lead)

    p0_leads, deferred_leads = reconcile_litigation_leads(
        brief_leads=brief_leads,
        exhibit_leads=exhibit_leads,
        entity_links=entity_links,
        bordereau_confirmed=bordereau_confirmed,
        max_p0=max_p0,
    )
    resolved_status: ModelStatus = (
        "partial_failure"
        if rejected and (p0_leads or deferred_leads)
        else model_status
    )
    coverage = QaeCoverageManifest(
        exhibits_in_bundle=bundle_ids,
        exhibits_read_by_qae=read_exhibits,
        unread_exhibits=unread_exhibits,
        unreadable_ocr_pages=unreadable_pages,
        excluded_by_preselection=excluded,
        p0_leads_count=len(p0_leads),
        deferred_leads_count=len(deferred_leads),
        rejected_candidates_count=len(rejected),
        model_status=resolved_status,
    )
    return {
        "tier1_report": tier1_report,
        "tier1_digest": tier1_digest,
        "tier2": {
            "p0_leads": p0_leads,
            "deferred_leads": deferred_leads,
            "rejected_candidates": tuple(rejected),
            "brief_leads": tuple(brief_leads),
            "exhibit_leads": tuple(exhibit_leads),
            "transmission_manifest": asdict(transmission_manifest),
        },
        "coverage_manifest": coverage,
    }
