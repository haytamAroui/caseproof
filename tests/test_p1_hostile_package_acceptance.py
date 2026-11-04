"""Reproducible synthetic archive failures; no private documents or network."""
import io
import struct
import warnings
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import pytest

from infrastructure.parsers.docx_region_inventory import inventory_docx_regions
from infrastructure.parsers.docx_text_regions import extract_docx_text_regions


def _package(entries: list[tuple[str, bytes]], compression: int = ZIP_STORED) -> bytes:
    output = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with ZipFile(output, "w", compression=compression) as archive:
            for name, data in entries:
                archive.writestr(name, data)
    return output.getvalue()


def _entries() -> list[tuple[str, bytes]]:
    return [("[Content_Types].xml", b"<Types/>"), ("word/document.xml", b"<document/>")]


def _change_document_method(data: bytes, method: int) -> bytes:
    """Change both ZIP method fields while leaving the original payload intact."""
    output = bytearray(data)
    with ZipFile(io.BytesIO(data)) as archive:
        info = archive.getinfo("word/document.xml")
        local_offset = info.header_offset
        central_offset = archive.start_dir
        while output[central_offset:central_offset + 4] == b"PK\x01\x02":
            name_len, extra_len, comment_len = struct.unpack_from("<HHH", output, central_offset + 28)
            name = bytes(output[central_offset + 46:central_offset + 46 + name_len])
            if name == b"word/document.xml":
                struct.pack_into("<H", output, central_offset + 10, method)
                break
            central_offset += 46 + name_len + extra_len + comment_len
        else:
            raise AssertionError("central directory missing document")
        struct.pack_into("<H", output, local_offset + 8, method)
    return bytes(output)


def _assert_unknown(payload: bytes) -> None:
    coverage = inventory_docx_regions(payload)
    extraction = extract_docx_text_regions(payload)
    assert coverage.coverage_unknown
    assert not extraction.coverage_complete
    assert extraction.regions == ()
    assert extraction.manifest["coverage_unknown"] is True


@pytest.mark.parametrize("payload", [
    b"not a zip",
    _package(_entries() + [("../escape.xml", b"x")]),
    _package(_entries() + [("word/document.xml", b"<duplicate/>")]),
    _change_document_method(_package(_entries()), 99),
    _change_document_method(_package(_entries()), ZIP_DEFLATED),
])
def test_hostile_archives_have_controlled_unknown_coverage(payload: bytes) -> None:
    _assert_unknown(payload)


def test_corrupt_crc_fails_closed() -> None:
    payload = bytearray(_package(_entries()))
    with ZipFile(io.BytesIO(payload)) as archive:
        info = archive.getinfo("word/document.xml")
        name_len, extra_len = struct.unpack_from("<HH", payload, info.header_offset + 26)
        payload[info.header_offset + 30 + name_len + extra_len] ^= 1
    _assert_unknown(bytes(payload))


def test_part_limit_prevents_expansion(monkeypatch: pytest.MonkeyPatch) -> None:
    from infrastructure.parsers import docx_region_inventory

    monkeypatch.setattr(docx_region_inventory, "MAX_PART_BYTES", 10)
    _assert_unknown(_package(_entries(), ZIP_DEFLATED))


def test_encrypted_entry_is_refused_before_discovery() -> None:
    payload = bytearray(_package(_entries()))
    with ZipFile(io.BytesIO(payload)) as archive:
        info = archive.getinfo('word/document.xml')
        struct.pack_into('<H', payload, info.header_offset + 6, info.flag_bits | 1)
        offset = archive.start_dir
        while payload[offset:offset + 4] == b'PK\x01\x02':
            name_len, extra_len, comment_len = struct.unpack_from('<HHH', payload, offset + 28)
            name = bytes(payload[offset + 46:offset + 46 + name_len])
            if name == b'word/document.xml':
                flags = struct.unpack_from('<H', payload, offset + 8)[0]
                struct.pack_into('<H', payload, offset + 8, flags | 1)
                break
            offset += 46 + name_len + extra_len + comment_len
        else:
            raise AssertionError('central directory missing document')
    assert inventory_docx_regions(bytes(payload)).reason == 'ENCRYPTED_ZIP_ENTRY'
    _assert_unknown(bytes(payload))


def test_total_expanded_size_is_checked_before_reading(monkeypatch: pytest.MonkeyPatch) -> None:
    from infrastructure.parsers import docx_region_inventory

    monkeypatch.setattr(docx_region_inventory, 'MAX_TOTAL_UNCOMPRESSED', 12)
    payload = _package(_entries(), ZIP_DEFLATED)
    assert inventory_docx_regions(payload).reason == 'UNCOMPRESSED_LIMIT'
    _assert_unknown(payload)
