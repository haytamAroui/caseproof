"""Minimal, offline text extraction for the publisher PDFs the legal corpus preserves.

Purpose: let the loader re-derive the line layout of a preserved PDF from its own bytes, so the
text layer stored beside it is checked rather than trusted. It handles only what the Justel
consolidated PDFs use: FlateDecode content streams, Type0/Identity-H fonts with a ToUnicode
CMap, hex strings shown with Tj and positioned with Tm/Td. Anything else raises ``PdfLayerError``
and the caller fails closed. It is not a general PDF reader.
"""
from __future__ import annotations

import re
import zlib

_OBJ = re.compile(rb"(\d+) 0 obj\s*(.*?)endobj", re.S)
_STREAM = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.S)
_MAX_INFLATED = 64 * 1024 * 1024


class PdfLayerError(ValueError):
    """The PDF is outside the supported subset."""


def _inflate(raw: bytes) -> bytes:
    d = zlib.decompressobj()
    out = d.decompress(raw, _MAX_INFLATED)
    if d.unconsumed_tail:
        raise PdfLayerError("stream too large")
    return out


def _cmap(data: bytes) -> dict[int, str]:
    text = data.decode("latin-1")
    out: dict[int, str] = {}
    for block in re.findall(r"beginbfchar(.*?)endbfchar", text, re.S):
        for src, dst in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
            out[int(src, 16)] = bytes.fromhex(dst).decode("utf-16-be")
    for block in re.findall(r"beginbfrange(.*?)endbfrange", text, re.S):
        for lo, hi, arr, dst in re.findall(
                r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(?:\[([^\]]*)\]|<([0-9A-Fa-f]+)>)", block):
            first, last = int(lo, 16), int(hi, 16)
            if last - first > 0xFFFF:
                raise PdfLayerError("bad range")
            if arr:
                items = re.findall(r"<([0-9A-Fa-f]+)>", arr)
                for i, item in zip(range(first, last + 1), items, strict=False):
                    out[i] = bytes.fromhex(item).decode("utf-16-be")
            else:
                base = bytes.fromhex(dst).decode("utf-16-be")
                for i in range(first, last + 1):
                    out[i] = base[:-1] + chr(ord(base[-1]) + i - first)
    return out


def extract_lines(pdf: bytes) -> list[str]:
    """Visible text lines in reading order, whitespace-normalised, blank lines dropped."""
    if not pdf.startswith(b"%PDF-"):
        raise PdfLayerError("not a PDF")
    objs = {int(m.group(1)): m.group(2) for m in _OBJ.finditer(pdf)}
    if not 0 < len(objs) <= 100_000:
        raise PdfLayerError("unsupported object table")

    def body(n: int) -> bytes:
        return objs[n]

    def stream(n: int) -> bytes:
        m = _STREAM.search(objs[n])
        if m is None:
            raise PdfLayerError("stream missing")
        if b"/FlateDecode" in objs[n].split(b"stream", 1)[0]:
            return _inflate(m.group(1))
        return m.group(1)

    pages_obj = next((n for n, o in objs.items() if re.search(rb"/Type\s*/Pages\b", o) and b"/Kids" in o), None)
    if pages_obj is None:
        raise PdfLayerError("no page tree")
    kids = [int(x) for x in re.findall(rb"(\d+) 0 R", re.search(rb"/Kids\s*\[(.*?)\]", body(pages_obj), re.S).group(1))]  # type: ignore[union-attr]
    lines: list[str] = []
    for page in kids:
        po = body(page)
        res = re.search(rb"/Resources (\d+) 0 R", po)
        cont = re.search(rb"/Contents (\d+) 0 R", po)
        if res is None or cont is None:
            raise PdfLayerError("unsupported page")
        fonts: dict[bytes, dict[int, str]] = {}
        fdict = re.search(rb"/Font\s*<<(.*?)>>", body(int(res.group(1))), re.S)
        for name, num in re.findall(rb"/(\w+) (\d+) 0 R", fdict.group(1) if fdict else b""):
            tu = re.search(rb"/ToUnicode (\d+) 0 R", body(int(num)))
            if tu is None or b"Identity-H" not in body(int(num)):
                raise PdfLayerError("unsupported font")
            fonts[name] = _cmap(stream(int(tu.group(1))))
        runs: list[tuple[float, float, str]] = []
        content = stream(int(cont.group(1)))
        for bt in re.findall(rb"\bBT\b(.*?)\bET\b", content, re.S):
            font: dict[int, str] = {}
            x = y = 0.0
            text: list[str] = []
            start: tuple[float, float] | None = None
            for tok in re.finditer(rb"/(\w+) [\d.]+ Tf|([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+) Tm"
                                   rb"|([-\d.]+) ([-\d.]+) Td|<([0-9A-Fa-f]+)> Tj", bt):
                if tok.group(1):
                    if tok.group(1) not in fonts:
                        raise PdfLayerError("unknown font")
                    font = fonts[tok.group(1)]
                elif tok.group(2):
                    x, y = float(tok.group(6)), float(tok.group(7))
                elif tok.group(8):
                    x, y = x + float(tok.group(8)), y + float(tok.group(9))
                else:
                    if start is None:
                        start = (x, y)
                    h = tok.group(10).decode()
                    for i in range(0, len(h), 4):
                        text.append(font.get(int(h[i:i + 4], 16), "\ufffd"))
            if text and start is not None:
                runs.append((start[1], start[0], "".join(text)))
        page_lines: list[tuple[float, list[tuple[float, str]]]] = []
        for yy, xx, t in runs:
            if page_lines and abs(page_lines[-1][0] - yy) < 2:
                page_lines[-1][1].append((xx, t))
            else:
                page_lines.append((yy, [(xx, t)]))
        for _, parts in page_lines:
            line = re.sub(r"\s+", " ", "".join(t for _, t in sorted(parts))).strip()
            if line:
                lines.append(line)
    return lines


def layer_matches_pdf(layer: str, pdf: bytes) -> bool:
    """True when the stored text layer's non-blank lines equal the PDF's own extracted lines."""
    mine = [re.sub(r"\s+", " ", ln).strip() for ln in layer.replace("\f", "\n").splitlines()]
    return [ln for ln in mine if ln] == extract_lines(pdf)
