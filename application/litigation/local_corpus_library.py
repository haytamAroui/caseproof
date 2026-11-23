"""Bounded, content-addressed local legal packs. No network or authenticity claim.

Installing a pack adds a new immutable identity. There is no current/latest
pointer: a caller must select the complete digest for each new check.
"""
from __future__ import annotations

import io
import json
import os
import re
import tempfile
from pathlib import Path
from zipfile import ZIP_STORED, BadZipFile, ZipFile

from application.litigation.corpus import CORPUS_FORMAT_VERSION, CorpusError
from application.litigation.legal_references import LegalCorpusConfig, load_corpus_config

MAX_PACK_BYTES = 40 * 1024 * 1024
_DIGEST = re.compile(r"[0-9a-f]{64}")


def _toml(value: object) -> str:
    return str(value).lower() if isinstance(value, bool) else json.dumps(value, ensure_ascii=False)


def encode_corpus_pack(config: LegalCorpusConfig) -> bytes:
    """Canonical transport of the legal-reference slice, without cabinet rules."""
    if config.failures or not config.records:
        raise CorpusError("complete corpus required")
    files: dict[str, bytes] = {}
    lines = ["format = " + _toml(CORPUS_FORMAT_VERSION)]
    for i, record in enumerate(sorted(config.records, key=lambda r: r.key)):
        if record.original_bytes is None:
            raise CorpusError("preserved source bytes required")
        source, derived = f"data/{i}-source.bin", f"data/{i}-article.txt"
        files[source] = record.original_bytes
        files[derived] = record.derived_text.encode()
        values = {key: getattr(record, key) for key in (
            "act", "article", "language", "version", "source_uri", "acquired_at", "consolidated",
            "original_sha256", "source_artifact_kind", "source_notes", "body_start")}
        if record.original_text_layer_sha256:
            layer = f"data/{i}-layer.txt"
            files[layer] = record.original_text_layer.encode()
            del values["body_start"]
            values.update(original_text_layer_file=layer, original_text_layer_sha256=record.original_text_layer_sha256)
        elif not values["body_start"]:
            del values["body_start"]
        values.update(original_file=source, derived_file=derived)
        lines += ["", "[[publication]]"] + [k + " = " + _toml(v) for k, v in values.items()]
    files["corpus-manifest.toml"] = "\n".join(lines).encode()
    aliases = []
    for name, mapping in (("act_aliases", config.act_aliases), ("chosen_versions", config.chosen_versions)):
        aliases += ["[" + name + "]"] + [_toml(k) + " = " + _toml(v) for k, v in sorted(mapping.items())]
    files["act-aliases.toml"] = "\n".join(aliases).encode()
    if sum(map(len, files.values())) > MAX_PACK_BYTES - 100000:
        raise CorpusError("corpus transport exceeds byte bound")
    output = io.BytesIO()
    with ZipFile(output, "w", compression=ZIP_STORED) as archive:
        for name, raw in sorted(files.items()):
            archive.writestr(name, raw)
    raw = output.getvalue()
    if decode_corpus_pack(raw).pack_sha256 != config.pack_sha256:
        raise CorpusError("corpus transport changed selection")
    return raw


def decode_corpus_pack(raw: bytes) -> LegalCorpusConfig:
    """Validate before returning a config. Never extract attacker-chosen paths."""
    if not 0 < len(raw) <= MAX_PACK_BYTES:
        raise CorpusError("corpus transport byte bound")
    try:
        with ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            names = [x.filename for x in infos]
            if (not 2 < len(infos) <= 20002 or len(set(names)) != len(names)
                    or any(x.compress_type != ZIP_STORED or x.flag_bits & 1 for x in infos)
                    or sum(x.file_size for x in infos) > MAX_PACK_BYTES
                    or any(not (name in ("corpus-manifest.toml", "act-aliases.toml")
                                or re.fullmatch(r"data/[0-9]+-(?:source\.bin|article\.txt)", name)) for name in names)):
                raise CorpusError("corpus transport inventory refused")
            with tempfile.TemporaryDirectory(prefix="caseproof-corpus-") as temp:
                directory = Path(temp)
                (directory / "data").mkdir()
                for name in names:
                    (directory / name).write_bytes(archive.read(name))
                config = load_corpus_config(directory)
                if config.failures or not config.records:
                    raise CorpusError("corpus ingestion failed")
                return config
    except (BadZipFile, OSError, UnicodeError, KeyError, TypeError, ValueError) as exc:
        raise CorpusError("local corpus pack refused") from exc


class LocalCorpusLibrary:
    """Append-only pack store. Full identity selection, no automatic upgrades."""

    def __init__(self, directory: Path):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)

    def install(self, raw: bytes) -> str:
        config = decode_corpus_pack(raw)
        digest = config.pack_sha256
        canonical = encode_corpus_pack(config)
        target = self.directory / (digest + ".zip")
        # Write privately, then publish atomically without replacing any old path.
        with tempfile.NamedTemporaryFile(dir=self.directory, prefix=".import-", delete=False) as handle:
            staging = Path(handle.name)
            handle.write(canonical)
        try:
            try:
                os.link(staging, target)
            except FileExistsError:
                self.select(digest)  # Never overwrite, including a damaged old pack.
        finally:
            staging.unlink()
        return digest

    def select(self, digest: str) -> LegalCorpusConfig:
        if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            raise CorpusError("full corpus identity required")
        path = self.directory / (digest + ".zip")
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_PACK_BYTES:
            raise CorpusError("selected corpus unavailable")
        config = decode_corpus_pack(path.read_bytes())
        if config.pack_sha256 != digest:
            raise CorpusError("installed corpus changed; frozen identity refused")
        return config

    def inventory(self) -> list[dict[str, object]]:
        rows = []
        for path in sorted(self.directory.glob("*.zip")):
            config = self.select(path.stem)
            rows.append({"digest": path.stem, "articles": len(config.records),
                         "versions": sorted({r.version for r in config.records}),
                         "languages": sorted({r.language for r in config.records}),
                         "requested_versions": dict(config.chosen_versions),
                         "provenance": sorted({r.source_artifact_kind for r in config.records})})
        return rows
