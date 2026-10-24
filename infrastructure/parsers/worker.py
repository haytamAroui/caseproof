"""Private subprocess entry point. No provider credentials or network client."""

from __future__ import annotations

import base64
import json
import resource
import sys


def main() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (384 * 1024 * 1024, 384 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    resource.setrlimit(resource.RLIMIT_FSIZE, (4 * 1024 * 1024, 4 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    from application.documents.contracts import MAX_SOURCE_BYTES
    from infrastructure.parsers.engines import parse_bytes

    try:
        request = json.loads(sys.stdin.buffer.read(8 * 1024 * 1024))
        raw = base64.b64decode(request["data"], validate=True)
        if not 0 < len(raw) <= MAX_SOURCE_BYTES:
            raise ValueError("invalid parser input size")
        result = parse_bytes(raw, request["media_type"])
        sys.stdout.write(json.dumps({"ok": True, "artifact": result}, ensure_ascii=False, allow_nan=False))
    except Exception:
        # Raw parser exceptions can contain document text, URLs and paths.
        sys.stdout.write('{"ok":false,"reason":"document_parse_rejected"}')
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
