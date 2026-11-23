"""Extend a local corpus with every FR article of the consolidated PDF it already holds. No network.

Reads the preserved publisher PDF and its text layer from an existing corpus directory (the file already
fetched), cuts one derived text per explicit "Art. N." heading and writes a new corpus directory. Each new
entry is loaded back through the normal fail-closed loader; an article that does not load (for example a
page footer inside it) is left out and listed, never repaired. Only what the PDF carries is added: no other
language, no other act, no other version.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import tomllib
from pathlib import Path

from application.litigation.corpus import (
    _NEXT_HEADING,
    _STRUCTURAL,
    CorpusError,
    _ws,
    load_corpus,
    strip_footers,
)

_HEAD = re.compile(r"^\s*Art\.\s*(\d+\.\d+)\.")


def spans(layer: str) -> dict[str, str]:
    lines = strip_footers(layer).splitlines()
    out: dict[str, str] = {}
    dup: set[str] = set()
    for i, line in enumerate(lines):
        m = _HEAD.match(line)
        if not m:
            continue
        j = i + 1
        while j < len(lines) and not _NEXT_HEADING.match(lines[j]) and not _STRUCTURAL.match(lines[j]):
            j += 1
        text = _ws(" ".join(ln for ln in lines[i:j] if ln.strip()))
        if m.group(1) in out:
            dup.add(m.group(1))
        out[m.group(1)] = text
    for d in dup:
        out.pop(d)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = tomllib.loads((args.corpus / "corpus-manifest.toml").read_text(encoding="utf-8"))
    base = next(e for e in manifest["publication"] if e["language"] == "fr" and e.get("source_artifact_kind") == "official_consolidated_pdf")
    layer = (args.corpus / base["original_text_layer_file"]).read_text(encoding="utf-8")
    shutil.copytree(args.corpus, args.output)
    kept, skipped = [], []
    for article, text in sorted(spans(layer).items(), key=lambda kv: tuple(int(x) for x in kv[0].split("."))):
        if article == base["article"]:
            continue
        name = f"fr-{article}.txt"
        (args.output / name).write_text(text, encoding="utf-8")
        probe = args.output / "_probe"
        probe.mkdir(exist_ok=True)
        entry = {**base, "article": article, "derived_file": name}
        for k in (base["original_file"], base["original_text_layer_file"], name):
            shutil.copy(args.output / k, probe / k)
        (probe / "corpus-manifest.toml").write_text('format = "caseproof-corpus-manifest-v1"\n\n' + _toml([entry]), encoding="utf-8")
        report = load_corpus(probe)
        if report.failures:
            skipped.append({"article": article, "why": report.failures[0][:160]})
            (args.output / name).unlink()
        else:
            kept.append((article, entry))
    shutil.rmtree(args.output / "_probe", ignore_errors=True)
    with (args.output / "corpus-manifest.toml").open("a", encoding="utf-8") as handle:
        handle.write("".join("\n" + _toml([e]) for _, e in kept))
    final = load_corpus(args.output)
    if final.failures:
        raise CorpusError("combined corpus failed to load: " + "; ".join(final.failures[:3]))
    print(json.dumps({"added": [a for a, _ in kept], "skipped": skipped, "total_records": len(final.records)}, ensure_ascii=False, indent=1))


def _toml(entries: list[dict[str, object]]) -> str:
    parts: list[str] = []
    for e in entries:
        parts.append("[[publication]]\n" + "".join(f"{k} = {json.dumps(v, ensure_ascii=False)}\n" for k, v in e.items()))
    return "".join(parts)


if __name__ == "__main__":
    main()
