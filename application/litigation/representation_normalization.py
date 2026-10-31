"""Conservative visual-comparison normalization, never lexical quote rewriting."""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass

NORMALIZATION = "caseproof-visual-nfc-ligature-whitespace-v2"


@dataclass(frozen=True, slots=True)
class NormalizedRegion:
    text: str
    # Each normalized codepoint maps to a half-open raw codepoint interval.
    raw_ranges: tuple[tuple[int, int], ...]
    version: str = NORMALIZATION


def normalize_region(raw: str) -> NormalizedRegion:
    if type(raw) is not str or len(raw) > 4000:
        raise ValueError("bounded regional text required")
    output: list[str] = []
    ranges: list[tuple[int, int]] = []
    i = 0
    while i < len(raw):
        start = i
        if raw[i] == "\u00ad":
            i += 1
            continue
        if raw[i].isspace():
            while i < len(raw) and raw[i].isspace():
                i += 1
            if output and i < len(raw):
                output.append(" ")
                ranges.append((start, i))
            continue
        i += 1
        while i < len(raw) and unicodedata.combining(raw[i]):
            i += 1
        cluster = unicodedata.normalize("NFC", raw[start:i])
        for glyph, plain in (("\ufb00", "ff"), ("\ufb01", "fi"), ("\ufb02", "fl"),
                             ("\ufb03", "ffi"), ("\ufb04", "ffl"),
                             ("\ufb05", "st"), ("\ufb06", "st")):
            cluster = cluster.replace(glyph, plain)
        for char in cluster:
            output.append(char)
            ranges.append((start, i))
    return NormalizedRegion("".join(output), tuple(ranges))
