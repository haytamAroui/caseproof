"""Deterministic, synthetic mutation smoke test for DOCX discovery boundaries.

Run under an external process timeout and memory limit; this is not a sandbox or
coverage-guided fuzzing. Seeds contain no user data. A crash identifies the seed
and mutation index so a failing input can be reproduced without logging bytes.
"""
from __future__ import annotations

import io
import random
from xml.etree.ElementTree import ParseError
from zipfile import ZIP_DEFLATED, ZipFile

from defusedxml.common import DefusedXmlException  # type: ignore[import-untyped]

from application.extraction.contracts import ExtractionError
from infrastructure.parsers.docx_region_inventory import inventory_docx_regions
from infrastructure.parsers.docx_text_regions import extract_docx_text_regions
from infrastructure.parsers.engines import parse_docx

SEED = 20261104
CASES = 256


PARTS = {
    "[Content_Types].xml": b"<Types/>",
    "_rels/.rels": b"<Relationships/>",
    "word/document.xml": (
        b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        b"<w:body/></w:document>"
    ),
}


def seed_package(parts: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    return output.getvalue()


def main() -> None:
    original = seed_package(PARTS)
    parse_docx(original)
    rng = random.Random(SEED)  # noqa: S311 - reproducible synthetic input, not security randomness
    for index in range(CASES):
        data = bytearray(original)
        for _ in range(1 + index % 4):
            offset = rng.randrange(len(data))
            data[offset] ^= 1 << rng.randrange(8)
        if index % 8 == 0:
            del data[rng.randrange(len(data)):]
        try:
            inventory = inventory_docx_regions(bytes(data))
            extracted = extract_docx_text_regions(bytes(data))
            if inventory.coverage_unknown:
                assert not extracted.coverage_complete and not extracted.regions
        except Exception as exc:
            raise RuntimeError(f"DOCX discovery mutation failed: seed={SEED} case={index}") from exc
    for name, part in PARTS.items():
        for index in range(CASES):
            offset = rng.randrange(len(part))
            mutated = part[:offset] + bytes([part[offset] ^ (1 << rng.randrange(8))]) + part[offset + 1:]
            try:
                parse_docx(seed_package(PARTS | {name: mutated}))
            except (ExtractionError, DefusedXmlException, ParseError, ValueError):
                # A malformed part can fail at the XML boundary or document checks.
                continue
            except Exception as exc:
                raise RuntimeError(f"DOCX part mutation failed: seed={SEED} part={name} case={index}") from exc
    print(f"DOCX mutation smoke passed: seed={SEED} archive_cases={CASES} part_cases={len(PARTS) * CASES}")


if __name__ == "__main__":
    main()
