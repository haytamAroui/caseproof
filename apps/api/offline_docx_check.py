"""Run the existing fail-closed Word parser and legal checker with no network.

This is a legal-reference slice, not signed identity, exhibit checking, a
lawyer's review or filing approval. Use only corpus files cleared for reuse.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from application.litigation.corpus import CorpusError
from application.litigation.exhibit_coverage import load_exhibit_set
from application.litigation.exhibit_passages import build_passages, read_piece_texts
from application.litigation.legal_references import (
    ENGINE_STRICT4,
    ENGINE_STRICT5,
    LegalCorpusConfig,
    load_corpus_config,
)
from application.litigation.legal_review_decisions import FINGERPRINT_SCHEME, carry, occurrence_fingerprints
from application.litigation.offline_legal_pack import build_legal_pack, observe, verify_legal_pack
from application.litigation.unified_review import LegalObservation
from infrastructure.parsers.engines import parse_docx


@dataclass(frozen=True, slots=True)
class OfflineLegalRun:
    snapshot_hash: str
    representation_sha256: str
    corpus_pack_sha256: str
    legal_observations: tuple[LegalObservation, ...]


def check_offline_docx(*, docx: Path, corpus: Path | LegalCorpusConfig,
                       chosen_versions: dict[str, str] | None = None,
                       prior: tuple[bytes, str] | None = None, exhibits: Path | None = None) -> tuple[bytes, str]:
    """Checks execute now from local bytes, never from saved/precomputed results.

    Corpus selection is explicit. Override only for an intentionally requested
    version; an absent version never falls back to an installed current one.
    """
    from dataclasses import replace

    raw = docx.read_bytes()
    if not 0 < len(raw) <= 8 * 1024 * 1024:
        raise CorpusError("bounded Word input required")
    artifact = parse_docx(raw)
    warnings = set(artifact["warnings"]) - {"docx_layout_page_numbers_unverified"}
    if warnings or not artifact["text"]:
        raise CorpusError("unsupported Word content: " + ", ".join(sorted(warnings)))
    config = corpus if isinstance(corpus, LegalCorpusConfig) else load_corpus_config(corpus)
    if config.failures:
        raise CorpusError("corpus ingestion failed; partial corpus refused")
    if chosen_versions is not None:
        config = replace(config, chosen_versions=chosen_versions)
    text = artifact["text"]
    exhibit_set = load_exhibit_set(exhibits, lambda raw: parse_docx(raw)["text"]) if exhibits is not None else None
    engine = ENGINE_STRICT5 if exhibit_set is not None else ENGINE_STRICT4
    observations = observe(text, config, engine, exhibit_set)
    passages = None
    if exhibit_set is not None and exhibits is not None:
        passages = build_passages(text, observations, read_piece_texts(exhibits, exhibit_set, lambda raw: parse_docx(raw)["text"]))
    if not observations:
        raise CorpusError("no supported explicit legal reference detected; no success claim")
    representation_sha = hashlib.sha256(text.encode()).hexdigest()
    identity = {"engine": "caseproof-offline-docx-legal-v1", "input_sha256": hashlib.sha256(raw).hexdigest(),
                "parser_id": artifact["parser_id"], "representation_sha256": representation_sha,
                "corpus_pack_sha256": config.pack_sha256,
                "legal_observations": [asdict(x) for x in observations]}
    snapshot = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False,
                                         separators=(",", ":")).encode()).hexdigest()
    run = OfflineLegalRun(snapshot, representation_sha, config.pack_sha256, observations)
    review = {"snapshot_hash": snapshot, "revision": 0, "decisions": [], "release_authorized": False,
              "origin": "local_offline_check_not_authenticated_lawyer_review", "input_binding": identity,
              "decision_layer": 1, "fingerprint_scheme": FINGERPRINT_SCHEME,
              "check_engine": engine}
    if prior is not None:
        # The earlier review is replayed cold first: a changed or forged export carries nothing.
        before = verify_legal_pack(prior[0], expected_sha256=prior[1])
        by_key = {r.key: r.derived_sha256 for r in config.records}
        current = occurrence_fingerprints([asdict(o) for o in observations], by_key, config.pack_sha256, text)
        review.update(carry(before["review"], prior[1], current))
        review["revision"] = int(before["review"].get("revision", 0)) + 1
    return build_legal_pack(config=config, run=run, brief_text=text, review=review, exhibits=exhibit_set, passages=passages)
