"""Bounded DOCX XML parsing; this is not an operating-system sandbox."""
from io import BytesIO
from typing import cast
from xml.etree.ElementTree import Element

from defusedxml import ElementTree as SafeXML  # type: ignore[import-untyped]

# These protect the in-process discovery adapter even when it is called outside
# the stricter upload preflight. They are limits, not a promise of isolation.
MAX_XML_NODES = 200_000
MAX_XML_DEPTH = 256


def parse_docx_xml(data: bytes) -> Element:
    """Reject unsafe declarations and excessive tree complexity before use."""
    # Expat does not support UTF-32. Refuse its common BOM and BOM-less
    # signatures explicitly instead of relying on a raw ASCII declaration scan.
    if data.startswith((b"\x00\x00\xfe\xff", b"\xff\xfe\x00\x00", b"\x00\x00\x00<", b"<\x00\x00\x00")):
        raise ValueError("unsupported XML encoding")
    depth = nodes = 0
    parser = SafeXML.iterparse(
        BytesIO(data), events=("start", "end"),
        forbid_dtd=True, forbid_entities=True, forbid_external=True,
    )
    for event, _ in parser:
        if event == "start":
            depth += 1
            nodes += 1
            if depth > MAX_XML_DEPTH or nodes > MAX_XML_NODES:
                raise ValueError("XML complexity limit exceeded")
        else:
            depth -= 1
    return cast(Element, parser.root)
