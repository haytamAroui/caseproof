"""Archive metadata preflight before private original storage (ASVS 5.0 V5).

Unparseable originals may remain quarantined evidence; archive containers must
still respect traversal, encryption, expansion, entry and type limits. Full parsing
runs separately in the isolated worker and never inherits upload authority.
"""
from __future__ import annotations

import io
import stat
from zipfile import BadZipFile, ZipFile

from application.extraction.contracts import ExtractionError

DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


def validate_original_container(data: bytes, media_type: str) -> None:
    if media_type != DOCX or not data.startswith(b'PK'):
        return
    try:
        with ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if (not 2 <= len(entries) <= 128 or len({e.filename for e in entries}) != len(entries)
                    or sum(e.file_size for e in entries) > 8 * 1024 * 1024):
                raise ExtractionError('unsafe_original_archive')
            for entry in entries:
                name = entry.filename
                if (name.startswith('/') or '\\' in name or '..' in name.split('/') or ':' in name
                        or any(ord(c) < 32 or ord(c) == 127 for c in name)
                        or stat.S_IFMT(entry.external_attr >> 16) == stat.S_IFLNK
                        or entry.flag_bits & 1 or entry.file_size > 2 * 1024 * 1024
                        or entry.file_size > max(entry.compress_size, 1) * 80):
                    raise ExtractionError('unsafe_original_archive')
    except (BadZipFile, ValueError):
        raise ExtractionError('unsafe_original_archive') from None
