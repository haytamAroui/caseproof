"""Prepare, install or list local legal packs. Never chooses a latest version."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from application.litigation.legal_references import load_corpus_config
from application.litigation.local_corpus_library import LocalCorpusLibrary, encode_corpus_pack


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Package a cleared local corpus directory")
    prepare.add_argument("--corpus", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    install = commands.add_parser("install", help="Add a pack without replacing earlier packs")
    install.add_argument("pack", type=Path)
    install.add_argument("--library", type=Path, required=True)
    inventory = commands.add_parser("list")
    inventory.add_argument("--library", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        config = load_corpus_config(args.corpus)
        raw = encode_corpus_pack(config)
        with args.output.open("xb") as handle:
            handle.write(raw)
        result: object = {"output": str(args.output), "digest": config.pack_sha256}
    elif args.command == "install":
        result = {"digest": LocalCorpusLibrary(args.library).install(args.pack.read_bytes())}
    else:
        result = LocalCorpusLibrary(args.library).inventory()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
