"""Belgian legal corpus ingestion, task 4 foundations (local, bounded, manual).

Loads a SMALL chosen corpus from a local directory described by a TOML
manifest. No network access, no crawling, no inference: every publication is
added deliberately, with its original preserved byte-identical, its derived
text linked to that original, and its temporal version DECLARED in the
manifest (confirmed by the lawyer), never guessed from dates or hashes.

Design: docs/engineering/lot2-corpus-ingestion-design.md. The Moniteur belge
character text has no legal value and may be incomplete (the publication
image is the authoritative original); Justel consolidations are unofficial.
The model therefore records both artefacts and their relation, and marks the
consolidation status explicitly.

The loader fails closed: any malformed manifest entry, hash mismatch or
missing file is an ingestion failure that surfaces in the metrics, never a
silently skipped article. `IngestionReport` carries the task-4 acceptance
metrics: ingestion failures and ambiguous versions.
"""
from __future__ import annotations

import hashlib
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from application.litigation.suitability_rules import article_key

CORPUS_FORMAT_VERSION = "caseproof-corpus-manifest-v1"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_MAX_TEXT_BYTES = 32 * 1024 * 1024
_MAX_ARTICLES = 10_000


class CorpusError(ValueError):
    """Malformed corpus manifest or corpus content."""


def _ws(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()


def check_derived_binding(artifact_kind: str, original_bytes: bytes, derived_text: str) -> None:
    """A text capture's derived article must literally occur in its preserved original.

    Hashing both files proves nothing about their relation: a derived text edited
    beside an intact original would otherwise be checked against as "the source".
    Other artifact kinds (for example a PDF) need an extraction proof not built yet.
    """
    if artifact_kind != "official_text_capture":
        return
    try:
        original = original_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CorpusError("text capture original is not UTF-8") from exc
    needle = _ws(derived_text)
    if not needle or needle not in _ws(original):
        raise CorpusError("derived article text does not occur in its preserved original capture")


@dataclass(frozen=True, slots=True)
class ArticleRecord:
    """One corpus article: identity, declared version, provenance, texts."""

    act: str
    article: str
    language: str
    version: str
    source_uri: str
    acquired_at: str
    consolidated: bool
    original_sha256: str
    derived_text: str
    derived_sha256: str
    original_bytes: bytes | None = field(default=None, repr=False)
    source_artifact_kind: str = "publisher_file"
    source_notes: str = ""

    @property
    def key(self) -> str:
        return article_key(self.act, self.article, self.language, self.version)

    @property
    def base_key(self) -> str:
        return article_key(self.act, self.article, self.language)


@dataclass(frozen=True, slots=True)
class IngestionReport:
    """Task-4 acceptance metrics plus the ingested records."""

    records: tuple[ArticleRecord, ...]
    failures: tuple[str, ...]
    ambiguous_versions: tuple[str, ...] = field(default_factory=tuple)

    @property
    def article_keys(self) -> set[str]:
        return {record.key for record in self.records}


def _require_str(value: Any, name: str, limit: int) -> str:
    if not isinstance(value, str) or not 0 < len(value.strip()) <= limit:
        raise CorpusError(f"bounded non-empty string required for {name}")
    return value.strip()


def _require_hash(value: Any, name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise CorpusError(f"well-formed sha256 required for {name}")
    return value


def _load_entry(directory: Path, entry: Any, index: int) -> ArticleRecord:
    if not isinstance(entry, dict):
        raise CorpusError(f"manifest entry {index} is not a table")
    allowed = {"act", "article", "language", "version", "source_uri", "acquired_at",
               "consolidated", "original_file", "original_sha256", "derived_file",
               "source_artifact_kind", "source_notes"}
    if not set(entry) <= allowed:
        raise CorpusError(f"manifest entry {index} holds unknown keys: {sorted(set(entry) - allowed)}")
    act = _require_str(entry.get("act"), "act", 256)
    article = _require_str(entry.get("article"), "article", 64)
    language = _require_str(entry.get("language"), "language", 8)
    if language not in ("nl", "fr"):
        raise CorpusError("language is 'nl' or 'fr'")
    version = _require_str(entry.get("version"), "version", 128)
    if any("#" in part for part in (act, article, language, version)):
        raise CorpusError("identity parts must not contain '#'")
    source_uri = _require_str(entry.get("source_uri"), "source_uri", 512)
    acquired_at = _require_str(entry.get("acquired_at"), "acquired_at", 64)
    consolidated = entry.get("consolidated", False)
    if type(consolidated) is not bool:
        raise CorpusError("consolidated is an explicit boolean")

    original_file = _require_str(entry.get("original_file"), "original_file", 256)
    original_sha = _require_hash(entry.get("original_sha256"), "original_sha256")
    derived_file = _require_str(entry.get("derived_file"), "derived_file", 256)
    for name in (original_file, derived_file):
        if name.startswith("/") or "\\" in name or ".." in name.split("/"):
            raise CorpusError(f"unsafe corpus path: {name!r}")
    original_path = directory / original_file
    derived_path = directory / derived_file
    for path in (original_path, derived_path):
        if not path.resolve().is_relative_to(directory.resolve()) or path.is_symlink():
            raise CorpusError("corpus path escapes its pack")
    if not original_path.is_file():
        raise CorpusError(f"missing original publication file: {original_file}")
    if not derived_path.is_file():
        raise CorpusError(f"missing derived text file: {derived_file}")
    original_bytes = original_path.read_bytes()
    if len(original_bytes) > _MAX_TEXT_BYTES:
        raise CorpusError(f"original publication exceeds bounded size: {original_file}")
    if hashlib.sha256(original_bytes).hexdigest() != original_sha:
        raise CorpusError(f"original publication hash mismatch: {original_file}")
    derived_bytes = derived_path.read_bytes()
    if len(derived_bytes) > _MAX_TEXT_BYTES:
        raise CorpusError(f"derived text exceeds bounded size: {derived_file}")
    try:
        derived_text = derived_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CorpusError(f"derived text is not valid UTF-8: {derived_file}") from exc

    artifact_kind = entry.get("source_artifact_kind", "publisher_file")
    notes = entry.get("source_notes", "")
    if artifact_kind not in ("publisher_file", "official_text_capture", "synthetic"):
        raise CorpusError("unknown source artifact kind")
    if not isinstance(notes, str) or len(notes) > 4000:
        raise CorpusError("bounded source provenance required")
    check_derived_binding(artifact_kind, original_bytes, derived_text)
    return ArticleRecord(
        act=act,
        article=article,
        language=language,
        version=version,
        source_uri=source_uri,
        acquired_at=acquired_at,
        consolidated=consolidated,
        original_sha256=original_sha,
        derived_text=derived_text,
        derived_sha256=hashlib.sha256(derived_bytes).hexdigest(),
        original_bytes=original_bytes,
        source_artifact_kind=artifact_kind, source_notes=notes,
    )


def load_corpus(directory: Path) -> IngestionReport:
    """Load and validate a manifest-described local corpus; fail closed.

    Returns an IngestionReport even when individual entries fail, so the
    task-4 metrics (failures, ambiguous versions) are always measurable.
    A missing or malformed manifest itself raises CorpusError.
    """
    manifest_path = directory / "corpus-manifest.toml"
    if not manifest_path.is_file():
        raise CorpusError(f"missing corpus manifest: {manifest_path}")
    try:
        data = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise CorpusError(f"invalid corpus manifest: {exc}") from exc
    if not isinstance(data, dict) or data.get("format") != CORPUS_FORMAT_VERSION:
        raise CorpusError(f"manifest format must be {CORPUS_FORMAT_VERSION!r}")
    entries = data.get("publication")
    if not isinstance(entries, list) or not entries:
        raise CorpusError("manifest holds a non-empty [[publication]] list")
    if len(entries) > _MAX_ARTICLES:
        raise CorpusError("the number of corpus articles is bounded")

    records: list[ArticleRecord] = []
    failures: list[str] = []
    seen_keys: set[str] = set()
    for index, entry in enumerate(entries):
        try:
            record = _load_entry(directory, entry, index)
        except CorpusError as exc:
            failures.append(f"entry {index}: {exc}")
            continue
        if record.key in seen_keys:
            failures.append(f"entry {index}: duplicate article key {record.key}")
            continue
        seen_keys.add(record.key)
        records.append(record)

    versions_by_base: dict[str, set[str]] = {}
    for record in records:
        versions_by_base.setdefault(record.base_key, set()).add(record.version)
    ambiguous = tuple(sorted(base for base, versions in versions_by_base.items() if len(versions) > 1))

    return IngestionReport(records=tuple(records), failures=tuple(failures),
                           ambiguous_versions=ambiguous)
