"""Deterministic, synthetic mutation smoke test for DOCX discovery boundaries.

Run under an external process timeout and memory limit; this is not a sandbox or
coverage-guided fuzzing. Seeds contain no user data. A crash identifies the seed
and mutation index so a failing input can be reproduced without logging bytes.
"""
from __future__ import annotations

import io
import random
from zipfile import ZIP_DEFLATED, ZipFile

from infrastructure.parsers.docx_region_inventory import inventory_docx_regions
from infrastructure.parsers.docx_text_regions import extract_docx_text_regions

SEED = 20261104
CASES = 256


def seed_package() -> bytes:
    output = io.BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("_rels/.rels", "<Relationships/>")
        archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/'
                         'wordprocessingml/2006/main"><w:body/></w:document>')
    return output.getvalue()


def main() -> None:
    original = seed_package()
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
    print(f"DOCX discovery mutation smoke passed: seed={SEED} cases={CASES}")


if __name__ == "__main__":
    main()
