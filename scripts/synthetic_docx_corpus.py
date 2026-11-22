"""Synthetic DOCX control corpus for the task 6 coverage measurement.

Generates small hand-built DOCX packages, one per omission class the reader
declares, so the measurement harness can be checked against ground truth.
These files are harness validation only, never Belgian acceptance evidence.

Usage:
    uv run --locked python -m scripts.synthetic_docx_corpus --out DIR
"""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    "</Types>"
)


def _document(body: str) -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>'
    )


def _para(text: str) -> str:
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def build_docx(parts: dict[str, str]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        for name, xml in parts.items():
            archive.writestr(name, xml)
    return buffer.getvalue()


def control_files() -> dict[str, bytes]:
    """One synthetic DOCX per declared omission class."""
    plain = {"word/document.xml": _document(_para("Synthetic body text."))}
    comments = dict(plain)
    comments["word/comments.xml"] = (
        f'<?xml version="1.0"?><w:comments xmlns:w="{W}">'
        f'<w:comment w:id="1" w:author="synthetic"><w:p><w:r><w:t>note</w:t></w:r></w:p>'
        f"</w:comments>"
    )
    tracked = {"word/document.xml": _document(
        '<w:p><w:ins w:id="1" w:author="synthetic" w:date="2026-01-01T00:00:00Z">'
        "<w:r><w:t>inserted</w:t></w:r></w:ins></w:p>"
    )}
    hidden = {"word/document.xml": _document(
        "<w:p><w:r><w:rPr><w:vanish/></w:rPr><w:t>hidden</w:t></w:r></w:p>"
    )}
    textbox = {"word/document.xml": _document(
        "<w:p><w:r><w:drawing><wp:inline xmlns:wp="
        '"http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">'
        f"<w:txbxContent>{_para('boxed')}</w:txbxContent>"
        "</wp:inline></w:drawing></w:r></w:p>"
    )}
    header_footer = dict(plain)
    header_footer["word/header1.xml"] = (
        f'<?xml version="1.0"?><w:hdr xmlns:w="{W}">{_para("header")}</w:hdr>'
    )
    header_footer["word/footer1.xml"] = (
        f'<?xml version="1.0"?><w:ftr xmlns:w="{W}">{_para("footer")}</w:ftr>'
    )
    footnotes = dict(plain)
    footnotes["word/footnotes.xml"] = (
        f'<?xml version="1.0"?><w:footnotes xmlns:w="{W}">'
        f'<w:footnote w:id="1">{_para("footnote")}</w:footnote></w:footnotes>'
    )
    unknown_part = dict(plain)
    unknown_part["word/glossary.xml"] = f'<?xml version="1.0"?><w:glossary xmlns:w="{W}"/>'
    not_docx = {"word/document.xml": "not xml at all <"}
    return {
        "plain.docx": build_docx(plain),
        "with-comments.docx": build_docx(comments),
        "with-tracked-revisions.docx": build_docx(tracked),
        "with-hidden-text.docx": build_docx(hidden),
        "with-textbox.docx": build_docx(textbox),
        "with-header-footer.docx": build_docx(header_footer),
        "with-footnotes.docx": build_docx(footnotes),
        "with-unknown-part.docx": build_docx(unknown_part),
        "unreadable.docx": build_docx(not_docx),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="output directory")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, payload in control_files().items():
        (args.out / name).write_bytes(payload)
    print(f"wrote {len(control_files())} synthetic control files to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
