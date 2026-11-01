"""Deterministic synthetic geometry/hostile/200-page viewer corpus and server candidate."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import time
from pathlib import Path

from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    DictionaryObject,
    FloatObject,
    NameObject,
    RectangleObject,
    TextStringObject,
)
from reportlab.pdfgen import canvas

from infrastructure.parsers.pdf_ocr import _run


def vector(pages=1, scan=False, hostile=False, mixed=False):
    raw = io.BytesIO()
    c = canvas.Canvas(raw, pagesize=(600, 800), invariant=True, pageCompression=1)
    for number in range(pages):
        if mixed and number % 2:
            c.setPageSize((800, 600))
        c.setFillColorRGB(0, 0, 0)
        if scan:
            image = Image.new("RGB", (600, 800), "white")
            ImageDraw.Draw(image).rectangle((140, 560, 260, 600), fill="black")
            from reportlab.lib.utils import ImageReader

            c.drawImage(ImageReader(image), 0, 0, width=600, height=800)
        else:
            c.rect(140, 200, 120, 40, stroke=0, fill=1)
            c.drawString(140, 400, "Repeated source text")
            c.drawString(140, 450, "Repeated source text")
            c.drawString(40, 730, f"Synthetic physical page {number + 1}")
        c.showPage()
    c.save()
    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(raw.getvalue())))
    if hostile:
        writer.add_js("globalThis.__caseproofPdfExecuted=1; app.alert('hostile synthetic');")
        annotation = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/Link"),
                NameObject("/Rect"): RectangleObject([40, 40, 120, 60]),
                NameObject("/A"): DictionaryObject(
                    {
                        NameObject("/S"): NameObject("/URI"),
                        NameObject("/URI"): TextStringObject("https://external.invalid/must-not-load"),
                    }
                ),
            }
        )
        writer.add_annotation(0, annotation)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def expected_box(crop, rotation, scale=2):
    left, bottom, right, top = crop
    points = []
    for x, y in ((140, 200), (260, 200), (260, 240), (140, 240)):
        points.append(
            {
                0: (x - left, top - y),
                90: (y - bottom, x - left),
                180: (right - x, y - bottom),
                270: (top - y, right - x),
            }[rotation]
        )
    return [
        min(p[0] for p in points) * scale,
        min(p[1] for p in points) * scale,
        max(p[0] for p in points) * scale,
        max(p[1] for p in points) * scale,
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--server", action="store_true")
    args = parser.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    specs = [
        ("clean", 0, False, 1, False, False),
        ("scan", 0, False, 1, True, False),
        ("rotate90", 90, False, 1, False, False),
        ("rotate180", 180, False, 1, False, False),
        ("rotate270", 270, False, 1, False, False),
        ("crop", 90, True, 1, False, False),
        ("mixed", 0, False, 2, False, False),
        ("hostile", 0, False, 1, False, True),
        ("large200", 0, False, 200, False, False),
        ("overflow201", 0, False, 201, False, False),
    ]
    rows = []
    for name, rotation, cropped, count, scan, hostile in specs:
        writer = PdfWriter()
        writer.append(PdfReader(io.BytesIO(vector(count, scan, hostile, name == "mixed"))))
        if hostile:
            writer.add_js("globalThis.__caseproofPdfExecuted=1; app.alert('hostile synthetic');")
        for p in writer.pages:
            if rotation:
                p.rotate(rotation)
            if cropped:
                p.cropbox = RectangleObject([100, 150, 500, 700])
            if name == "mixed" and p == writer.pages[1]:
                p[NameObject("/UserUnit")] = FloatObject(1.25)
        buffer = io.BytesIO()
        writer.write(buffer)
        pdf = buffer.getvalue()
        path = out / (name + ".pdf")
        path.write_bytes(pdf)
        crop = [100, 150, 500, 700] if cropped else [0, 0, 600, 800]
        row = {
            "name": name,
            "sha256": hashlib.sha256(pdf).hexdigest(),
            "bytes": len(pdf),
            "rotation": rotation,
            "cropBox": crop,
            "mediaBox": [0, 0, 600, 800],
            "expectedBox": expected_box(crop, rotation),
            "pages": count,
            "supported": count <= 200,
            "scan": scan,
            "server": [],
        }
        if args.server and count <= 200:
            for page in [1, 200] if count == 200 else [1, 2] if name == "mixed" else [1]:
                start = time.perf_counter()
                prefix = out / (name + "-server-" + str(page))
                _run(
                    [
                        str(shutil.which("pdftoppm")),
                        "-f",
                        str(page),
                        "-l",
                        str(page),
                        "-singlefile",
                        "-cropbox",
                        "-r",
                        "144",
                        "-png",
                        str(path),
                        str(prefix),
                    ],
                    timeout=15,
                )
                png = prefix.with_suffix(".png")
                with Image.open(png) as image:
                    image.load()
                    size = list(image.size)
                row["server"].append(
                    {
                        "page": page,
                        "elapsed_ms": (time.perf_counter() - start) * 1000,
                        "png": png.name,
                        "size": size,
                        "sha256": hashlib.sha256(png.read_bytes()).hexdigest(),
                    }
                )
        rows.append(row)
    (out / "corrupt.pdf").write_bytes(b"%PDF-1.7\ncorrupt synthetic body")
    (out / "manifest.json").write_text(
        json.dumps({"schema": "caseproof-f2-fixtures-v1", "fixtures": rows}, indent=2)
    )
    print("F2_SYNTHETIC_FIXTURES_GENERATED")


if __name__ == "__main__":
    main()
