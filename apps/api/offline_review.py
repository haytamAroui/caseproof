"""Record local decisions on an offline legal review and recheck a corrected Word.

Every step writes a new frozen review. The earlier export is never edited.
Decisions carry a local label, not an authenticated lawyer identity.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from application.litigation.corpus import CorpusError
from application.litigation.legal_references import LegalCorpusConfig
from application.litigation.legal_review_decisions import body_fingerprints, make_decision
from application.litigation.offline_legal_pack import _config, build_legal_pack, verify_legal_pack
from application.litigation.unified_review import LegalObservation
from apps.api.offline_docx_check import check_offline_docx


@dataclass(frozen=True, slots=True)
class _Run:
    snapshot_hash: str
    representation_sha256: str
    corpus_pack_sha256: str
    legal_observations: tuple[LegalObservation, ...]


def record_decisions(*, pack: bytes, checkpoint: str,
                     decisions: list[dict[str, Any]]) -> tuple[bytes, str]:
    """decisions: {"reference_index", "action", "reason", "reviewer_label"} per finding."""
    body = verify_legal_pack(pack, expected_sha256=checkpoint)
    review = dict(body["review"])
    if review.get("decision_layer") != 1:
        raise CorpusError("this export predates local decisions; run a fresh check")
    if int(review.get("fingerprint_scheme", 1)) < 2:
        raise CorpusError("this export binds decisions to content, not to the occurrence; run a fresh check")
    prints = body_fingerprints(body)
    existing = {d["fingerprint"] for d in review["decisions"]}
    revision = int(review["revision"]) + 1
    added = []
    for item in decisions:
        index = item["reference_index"]
        if type(index) is not int or not 0 <= index < len(prints) or prints[index] in existing:
            raise CorpusError("decision must target one finding without a decision")
        existing.add(prints[index])
        added.append(make_decision(fingerprint=prints[index], action=item["action"], reason=item.get("reason", ""),
                                   reviewer_label=item["reviewer_label"], revision=revision))
    if not added:
        raise CorpusError("no decision given")
    review.update(decisions=[*review["decisions"], *added], revision=revision,
                  prior_checkpoint=checkpoint, release_authorized=False)
    review["superseded"] = list(review.get("superseded", []))
    config: LegalCorpusConfig = _config(body)
    run = _Run(body["snapshot_hash"], body["brief_representation_sha256"], body["corpus_pack_sha256"],
               tuple(LegalObservation(**r) for r in body["references"]))
    return build_legal_pack(config=config, run=run, brief_text=body["brief_text"], review=review,
                            exhibits=body.get("exhibits"), passages=body.get("passages"), passages_rules=body.get("passages_rules"))


def recheck(*, docx: Path, corpus: Path | LegalCorpusConfig, prior_pack: bytes, prior_checkpoint: str,
            chosen_versions: dict[str, str] | None = None, exhibits: Path | None = None) -> tuple[bytes, str]:
    """Fresh check of a corrected Word. Only identical findings keep their decision."""
    return check_offline_docx(docx=docx, corpus=corpus, chosen_versions=chosen_versions,
                              prior=(prior_pack, prior_checkpoint), exhibits=exhibits)
