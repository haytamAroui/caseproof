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
import zlib
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


_HEADING = r"(?:Art\.|Section|Chapitre|Afdeling|Hoofdstuk|Boek|Livre|Titre|Titel)"


def check_derived_binding(artifact_kind: str, original_bytes: bytes, derived_text: str, article: str = "", layer: bool = False) -> None:
    """A text capture's derived article must be the declared article's own span in its original.

    Hashing both files proves nothing about their relation. Occurring somewhere in a large
    capture is not enough either: text lifted from another article, or injected, would pass.
    So the derived text must start with the declared article heading, appear unmodified in
    the preserved capture, contain no other article heading, and end where the next heading
    (or the end of the capture) begins. Other artifact kinds (for example a PDF) need an
    extraction proof not built yet. This binds derivation, not publisher authenticity.
    """
    if artifact_kind != "official_text_capture":
        return
    try:
        original = original_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CorpusError("text capture original is not UTF-8") from exc
    needle, hay = _ws(derived_text), _ws(original)
    if not needle:
        raise CorpusError("derived article text is empty")
    if article and not re.match(rf"Art\.\s*{re.escape(article)}(?:\.|\s)", needle):
        raise CorpusError("derived text does not start with the declared article heading")
    if re.search(r"\bArt\.\s*\d", needle[4:]):
        raise CorpusError("derived text contains another article heading")
    at = hay.find(needle)
    while at != -1:
        tail = hay[at + len(needle):]
        if not tail.strip() or re.match(rf"\s*{_HEADING}(?=[\s\d])", tail) or (layer and _ends_article(tail)):
            return
        at = hay.find(needle, at + 1)
    raise CorpusError("derived article text does not occur as that article's own span in its preserved original capture")


_FOOTER = re.compile(r"\s*Page\s+\d+\s+de\s+\d+\s+Copyright Moniteur belge\s+\d{2}-\d{2}-\d{4}\s*")


def _ends_article(tail: str) -> bool:
    """True when what follows the derived text is a structural title, or a page footer that is itself followed by one.

    A footer followed by more running text means the article continues on the next page: the derived text
    would be a truncated article, so it is refused rather than accepted as complete.
    """
    footer = _FOOTER.match(tail)
    if footer is not None:
        rest = tail[footer.end():]
        return not rest.strip() or bool(re.match(rf"\s*{_HEADING}(?=[\s\d])", rest) or _STRUCTURAL.match(rest))
    return bool(_STRUCTURAL.match(tail)) and not re.match(r"\s*Page\s", tail)


PDF_KIND = "official_consolidated_pdf"
# Lines that end an article's span without being part of it: a page footer or a structural title.
# A footer INSIDE an article is never trimmed: that article then fails to load (fail closed).
_STRUCTURAL = re.compile(r"^\s*(?:Page\s+\d+\s+de\s+\d+|(?:Livre|Titre|Sous-titre|Chapitre|Section|Sous-section)\s+\d+(?:re|er|e|ère)?[\s.:])")
BASIS_PDF = "publisher_pdf_layout"
_NEXT_HEADING = re.compile(rf"^\s*{_HEADING}(?=[\s\d])")


def _pdf_span(layer: str, derived_text: str, article: str) -> list[str]:
    """Non-blank normalised layout lines from the article's "Art. N." line to its last line."""
    lines = layer.splitlines()
    want = _ws(derived_text)
    found: list[list[str]] = []
    for i, line in enumerate(lines):
        if not re.match(rf"\s*Art\.\s*{re.escape(article)}\.", line):
            continue
        j = i + 1
        while j < len(lines) and not _NEXT_HEADING.match(lines[j]) and not _STRUCTURAL.match(lines[j]):
            j += 1
        if _ws(" ".join(lines[i:j])) == want:
            found.append([_ws(ln) for ln in lines[i:j] if ln.strip()])
    if len(found) != 1 or len(found[0]) < 2:
        raise CorpusError("publisher PDF layout does not give exactly one heading/body boundary")
    return found[0]


def derive_pdf_body_start(layer: str, derived_text: str, article: str, pdf: bytes | None = None) -> str:
    """Body start from the publisher PDF's own rendered lines, never from a declaration.

    The layer is the line-preserving text of the preserved PDF. The article is the lines from its
    "Art. N." heading line up to the next heading line; the derived text must equal exactly that span.
    The body starts on the first line after the heading line. When the PDF bytes are given, that span
    is also re-read from the PDF itself (``pdf_text_layer``): the same lines must occur consecutively
    in the PDF's own text, so a layer edited to move the line break no longer loads. This is the
    publisher's rendering (a heading paragraph, then a body paragraph), not structured markup: a heading
    that wrapped over two lines would shift the boundary into the title.
    """
    span = _pdf_span(layer, derived_text, article)
    if pdf is not None:
        from application.litigation.pdf_text_layer import PdfLayerError, extract_lines
        try:
            extracted = extract_lines(pdf)
            real = [ln.replace(" ", "") for ln in extracted]
        except (PdfLayerError, ValueError, KeyError, zlib.error) as exc:
            raise CorpusError(f"publisher PDF text could not be re-read: {exc}") from exc
        mine = [ln.replace(" ", "") for ln in span]
        head = re.compile(rf"Art\.\s*{re.escape(article)}\.")
        # Bind the identified occurrence: exactly one line of the PDF's own text opens this article,
        # the layer's lines must be that occurrence, and a heading, a page footer or the end must
        # follow. Similar lines elsewhere in the PDF prove nothing.
        starts = [k for k, ln in enumerate(extracted) if head.match(ln)]
        if len(starts) != 1:
            raise CorpusError("the PDF does not open this article exactly once")
        k = starts[0]
        after = extracted[k + len(mine)] if k + len(mine) < len(extracted) else ""
        if real[k:k + len(mine)] != mine or (after and not _NEXT_HEADING.match(after) and not _STRUCTURAL.match(after)):
            raise CorpusError("text layer lines do not match the preserved PDF's own text")
    want, first = _ws(derived_text), span[1]
    # Shortest word-aligned prefix of that line that identifies the position: a quote that
    # starts at the body start may be shorter than the whole first line.
    start = next((first[:m.end()] for m in re.finditer(r"\S+", first) if m.end() >= 24), first)[:200]
    if want.count(start) != 1 or want.startswith(start):
        raise CorpusError("publisher PDF layout does not give exactly one heading/body boundary")
    return start


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
    body_start: str = ""
    original_text_layer: str = field(default="", repr=False)
    original_text_layer_sha256: str = ""
    body_start_basis: str = "declared"

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
               "source_artifact_kind", "source_notes", "body_start",
               "original_text_layer_file", "original_text_layer_sha256"}
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
    if artifact_kind not in ("publisher_file", "official_text_capture", "synthetic", PDF_KIND):
        raise CorpusError("unknown source artifact kind")
    if not isinstance(notes, str) or len(notes) > 4000:
        raise CorpusError("bounded source provenance required")
    layer_text, layer_sha, basis = "", "", "declared"
    if artifact_kind == PDF_KIND:
        if "body_start" in entry:
            raise CorpusError("a publisher PDF entry takes its body start from the PDF layout, not a declaration")
        layer_name = _require_str(entry.get("original_text_layer_file"), "original_text_layer_file", 256)
        layer_sha = _require_hash(entry.get("original_text_layer_sha256"), "original_text_layer_sha256")
        if layer_name.startswith("/") or "\\" in layer_name or ".." in layer_name.split("/"):
            raise CorpusError(f"unsafe corpus path: {layer_name!r}")
        layer_path = directory / layer_name
        if not layer_path.resolve().is_relative_to(directory.resolve()) or layer_path.is_symlink() or not layer_path.is_file():
            raise CorpusError("missing PDF text layer")
        layer_bytes = layer_path.read_bytes()
        if len(layer_bytes) > _MAX_TEXT_BYTES or hashlib.sha256(layer_bytes).hexdigest() != layer_sha:
            raise CorpusError("PDF text layer hash mismatch")
        if not original_bytes.startswith(b"%PDF-"):
            raise CorpusError("publisher PDF original expected")
        layer_text = layer_bytes.decode("utf-8")
        check_derived_binding("official_text_capture", layer_text.encode(), derived_text, article, layer=True)
        entry = {**entry, "body_start": derive_pdf_body_start(layer_text, derived_text, article, original_bytes)}
        basis = BASIS_PDF
    else:
        check_derived_binding(artifact_kind, original_bytes, derived_text, article)
    body_start = entry.get("body_start", "")
    if not isinstance(body_start, str) or len(body_start) > 200:
        raise CorpusError("bounded body_start required")
    if body_start and (_ws(derived_text).count(body_start) != 1 or _ws(derived_text).startswith(body_start)):
        raise CorpusError("body_start must occur exactly once, after the heading, in the derived text")
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
        source_artifact_kind=artifact_kind, source_notes=notes, body_start=body_start,
        original_text_layer=layer_text, original_text_layer_sha256=layer_sha, body_start_basis=basis,
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
