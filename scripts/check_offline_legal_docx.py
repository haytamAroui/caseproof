"""Check a bounded Word brief against a local chosen corpus. No network needed."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from apps.api.offline_docx_check import check_offline_docx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('docx', type=Path)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--exhibits', type=Path, help='Directory with bordereau.toml and the exhibit files (reference resolution and byte coverage only)')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--versions-json', type=Path, help='Explicit act-to-requested-version mapping')
    args = parser.parse_args()
    versions = None
    if args.versions_json is not None:
        versions = json.loads(args.versions_json.read_text())
        if not isinstance(versions, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                                    for k, v in versions.items()):
            parser.error('version selection must map act identity to version')
    raw, checkpoint = check_offline_docx(docx=args.docx, corpus=args.corpus, chosen_versions=versions, exhibits=args.exhibits)
    with args.output.open('xb') as handle:
        handle.write(raw)
    print(json.dumps({'output': str(args.output), 'review_sha256': checkpoint,
                      'scope': 'legal_reference_slice_only', 'legal_applicability': 'not_assessed'}, indent=2))


if __name__ == '__main__':
    main()
