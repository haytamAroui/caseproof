"""Bounded dual-view PDF adapter. Source parsing binaries use the OCR sandbox.

Observations are candidates, not proof of deletion/acceptance or calibrated
accuracy. Unsupported geometry/low quality remains explicit and reviewable.
"""
from __future__ import annotations

import base64
import hashlib
import io
import math
import os
import shutil
import tempfile
from dataclasses import dataclass
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path
from typing import Any

from defusedxml.ElementTree import fromstring  # type: ignore[import-untyped]
from PIL import Image
from pypdf import PdfReader
from pypdf.generic import ContentStream

from application.litigation.representation_normalization import NORMALIZATION, normalize_region
from infrastructure.parsers.pdf_ocr import RASTER_DPI, OCRUnavailable, _run, parse_tsv
from infrastructure.parsers.visual_edit_candidates import has_midline_candidate

ENGINE = "caseproof-dual-view-v2"
MAX_REGIONS = 96
MAX_PAGE_CROP_BYTES = 200_000


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class RasterWord:
    text: str
    box: tuple[int, int, int, int]
    score: str | None = None


def overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _vector_lines(raw: bytes, page_number: int, width: int, height: int) -> tuple[list[tuple[int, int, int, int]], bool]:
    """Read painted line segments, never interpret every line as a deletion.

    Only untransformed axis-aligned pages are supported. Form XObjects,
    clipping, transparency, nonstandard rendering and annotations require review.
    """
    reader = PdfReader(io.BytesIO(raw), strict=True)
    page = reader.pages[page_number - 1]
    w, h = float(page.mediabox.width), float(page.mediabox.height)
    if (page.rotation or list(page.cropbox) != list(page.mediabox)
            or float(page.mediabox.left) or float(page.mediabox.bottom)
            or not 0 < w <= 2400 or not 0 < h <= 3200):
        return [], False
    contents = page.get_contents()
    if contents is None or len(contents.get_data()) > 2_000_000:
        return [], False
    operations = ContentStream(contents, reader).operations
    if len(operations) > 20_000:
        return [], False
    lines: list[tuple[int, int, int, int]] = []
    pending: list[tuple[float, float, float, float]] = []
    point: tuple[float, float] | None = None
    supported = not bool(page.get('/Annots'))
    transformed = False
    transform_stack = []
    for operands, operator in operations:
        if operator == b'q':
            transform_stack.append(transformed)
        elif operator == b'Q':
            transformed = transform_stack.pop() if transform_stack else True
        elif operator == b'cm':
            transformed = transformed or [float(v) for v in operands] != [1, 0, 0, 1, 0, 0]
        elif operator in (b'Do', b'W', b'W*', b'gs'):
            supported = False
        elif operator == b'Tr' and operands and int(operands[0]) != 0:
            supported = False
        elif operator == b'm':
            point = (float(operands[0]), float(operands[1]))
        elif operator == b'l' and point:
            end = (float(operands[0]), float(operands[1]))
            if transformed:
                supported = False
            else:
                pending.append((*point, *end))
            point = end
        elif operator in (b'S', b's', b'B', b'B*', b'b', b'b*'):
            for x1, y1, x2, y2 in pending:
                values = (x1 * width / w, (h-y1) * height/h, x2 * width/w, (h-y2)*height/h)
                if all(math.isfinite(v) for v in values):
                    lines.append((round(values[0]), round(values[1]), round(values[2]), round(values[3])))
            pending = []
            point = None
        elif operator in (b'n', b'f', b'f*'):
            pending = []
            point = None
    return lines, supported


def _line_over_word(line: tuple[int, int, int, int], box: tuple[int, int, int, int]) -> bool:
    x1, y1, x2, y2 = line
    left, top, right, bottom = box
    coverage = max(0, min(max(x1, x2), right) - max(min(x1, x2), left))
    y = (y1 + y2) / 2
    return (coverage >= (right-left) * .65 and abs(y1-y2) <= (bottom-top)*.65
            and top+(bottom-top)*.2 <= y <= top+(bottom-top)*.8)


def _layer_words(xml: bytes, width: int, height: int) -> list[RasterWord]:
    if len(xml) > 1_000_000:
        raise OCRUnavailable('visual_layer_budget')
    tree = fromstring(xml, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    pages = [node for node in tree.iter() if node.tag.rsplit('}', 1)[-1] == 'page']
    if len(pages) != 1:
        raise OCRUnavailable('visual_layer_page')
    page = pages[0]
    pw, ph = float(page.attrib['width']), float(page.attrib['height'])
    if not 0 < pw < 5000 or not 0 < ph < 6500:
        raise OCRUnavailable('visual_layer_dimensions')
    words = []
    for node in page.iter():
        if node.tag.rsplit('}', 1)[-1] != 'word':
            continue
        coords = [float(node.attrib[k]) for k in ('xMin', 'yMin', 'xMax', 'yMax')]
        if not all(math.isfinite(c) for c in coords):
            raise OCRUnavailable('visual_layer_coordinates')
        box = (max(0, int(coords[0]*width/pw)), max(0, int(coords[1]*height/ph)),
               min(width, math.ceil(coords[2]*width/pw)), min(height, math.ceil(coords[3]*height/ph)))
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        text = node.text or ''
        if len(text) > 4000:
            raise OCRUnavailable('visual_word_budget')
        words.append(RasterWord(text, box))
        if len(words) > 20_000:
            raise OCRUnavailable('visual_word_count')
    return words


class PDFVisualFidelity:
    """No network or models; independent text and image paths for every PDF type."""

    def inspect(self, raw: bytes, *, original_sha256: str, page_number: int) -> dict[str, Any]:
        if digest(raw) != original_sha256:
            raise ValueError('visual_original_hash_mismatch')
        if not raw.startswith(b'%PDF-') or not 0 < len(raw) <= 3*1024*1024 or not 1 <= page_number <= 64:
            raise OCRUnavailable('visual_input_budget')
        binaries = {name: shutil.which(name) for name in ('pdftoppm', 'pdftotext', 'tesseract')}
        if not all(binaries.values()):
            raise OCRUnavailable('visual_binaries_missing')
        with tempfile.TemporaryDirectory(prefix='caseproof-visual-') as directory:
            root = Path(directory)
            source, prefix = root/'source.pdf', root/'page'
            source.write_bytes(raw)
            _run([str(binaries['pdftoppm']), '-f', str(page_number), '-l', str(page_number),
                  '-singlefile', '-r', str(RASTER_DPI), '-png', str(source), str(prefix)], timeout=12)
            png = prefix.with_suffix('.png').read_bytes()
            if len(png) > 12*1024*1024:
                raise OCRUnavailable('visual_raster_budget')
            with Image.open(io.BytesIO(png)) as opened:
                if not 0 < opened.width <= 5000 or not 0 < opened.height <= 6500 or opened.width*opened.height > 16_000_000:
                    raise OCRUnavailable('visual_raster_dimensions')
                image = opened.convert('RGB')
            _run([str(binaries['pdftotext']), '-f', str(page_number), '-l', str(page_number),
                  '-bbox', str(source), str(root/'layer.xml')], timeout=12)
            # Poppler emits a fixed XHTML doctype. Strip this known declaration;
            # all remaining DTD/entities are rejected by defusedxml.
            xml = (root/'layer.xml').read_bytes()
            xml = xml.replace(b'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">', b'')
            layer = _layer_words(xml, image.width, image.height)
            _run([str(binaries['tesseract']), str(prefix.with_suffix('.png')), str(prefix),
                  '-l', 'nld+fra+eng', 'tsv'], timeout=20)
            ocr = [RasterWord(w.text, (w.left, w.top, w.left+w.width, w.top+w.height), w.confidence)
                   for w in parse_tsv(prefix.with_suffix('.tsv').read_bytes(), width=image.width, height=image.height)]
        return self.compare(image, png, raw, page_number, layer, ocr)

    def compare(self, image: Image.Image, png: bytes, raw: bytes, page_number: int,
                layer: list[RasterWord], ocr: list[RasterWord]) -> dict[str, Any]:
        lines, vector_supported = _vector_lines(raw, page_number, image.width, image.height)
        regions = []
        representation_id = digest((digest(raw) + str(page_number) + ENGINE + NORMALIZATION +
                                    os.getenv('CASEPROOF_OCR_BUILD', 'unrecorded') +
                                    ' '.join(w.text for w in layer)).encode())
        crop_bytes = 0
        # Include layer-only words too: invisible text is exactly a split-view risk.
        targets = layer or ocr
        position = 0
        for word in targets[:MAX_REGIONS]:
            matches = [w for w in ocr if overlap(word.box, w.box)] if layer else [word]
            visual = ' '.join(w.text for w in matches)
            score = min((Decimal(w.score or '-1') for w in matches), default=Decimal(-1))
            vector_edit = any(_line_over_word(line, word.box) for line in lines)
            word_budget = (word.box[2]-word.box[0])*(word.box[3]-word.box[1]) <= 256_000
            pixel_edit = has_midline_candidate(image, word.box) if word_budget else False
            edit = vector_edit or pixel_edit
            normalized = normalize_region(word.text).text
            agreement = bool(layer and visual and normalize_region(visual).text == normalized)
            reason = ('painted_line_candidate' if vector_edit else 'pixel_line_candidate' if pixel_edit
                      else 'word_pixel_budget' if not word_budget else 'no_visual_text' if not visual else 'low_ocr_quality' if score < 60
                      else 'text_disagreement' if layer and not agreement else 'uncalibrated_agreement' if layer
                      else 'scan_without_independent_text_layer')
            status = ('representation_conflict' if edit else 'ocr_unreliable' if not word_budget or not visual or score < 60
                      else 'representation_conflict' if layer and not agreement else 'not_assessed')
            left, top, right, bottom = word.box
            pad = 6
            bounds = (max(0,left-pad),max(0,top-pad),min(image.width,right+pad),min(image.height,bottom+pad))
            out = io.BytesIO()
            image.crop(bounds).save(out, format='PNG', optimize=False)
            crop = out.getvalue()
            crop_bytes += len(crop)
            if crop_bytes > MAX_PAGE_CROP_BYTES:
                break
            record = {'original_sha256': digest(raw), 'representation_id': representation_id, 'page_number': page_number,
                      'text_start': position, 'text_end': position + len(word.text),
                      'page_image_sha256': digest(png), 'bbox': list(bounds), 'word_bbox': list(word.box),
                      'coordinate_basis': 'raster_pixels_top_left_150dpi',
                      'image_size': [image.width,image.height], 'dpi': RASTER_DPI,
                      'extracted_text': word.text if layer else '', 'visual_text': visual,
                      'normalization_version': NORMALIZATION,
                      'normalized_extracted': normalized if layer else '',
                      'normalized_visual': normalize_region(visual).text,
                      'state': status, 'reason': reason, 'edit_candidate': edit,
                      'quality': {'ocr_min_score': str(score), 'text_agreement': agreement,
                                  'calibration_status': 'not_available', 'probability': None},
                      'detector': ENGINE, 'runtime_image': os.getenv('CASEPROOF_OCR_BUILD', 'unrecorded'),
                      'pypdf_version': version('pypdf'),
                      'vector_geometry_supported': vector_supported,
                      'crop_sha256': digest(crop), 'crop_base64': base64.b64encode(crop).decode()}
            record['region_id'] = digest(str((representation_id,page_number,word.box,word.text,ENGINE)).encode())
            regions.append(record)
            position += len(word.text) + 1
        context: dict[str, Any] | None = None
        if not layer and len(png) <= MAX_PAGE_CROP_BYTES:
            context = {'region_id': digest((representation_id + ':page-context:' + digest(png)).encode()),
                       'original_sha256': digest(raw), 'representation_id': representation_id,
                       'page_number': page_number, 'page_image_sha256': digest(png),
                       'bbox': [0, 0, image.width, image.height],
                       'coordinate_basis': 'raster_pixels_top_left_150dpi',
                       'image_size': [image.width, image.height], 'dpi': RASTER_DPI,
                       'extracted_text': '', 'visual_text': ' '.join(w.text for w in ocr)[:4000],
                       'text_context_partial': len(' '.join(w.text for w in ocr)) > 4000,
                       'state': 'ocr_unreliable', 'reason': 'page_context_only_no_text_layer',
                       'anchor_scope': 'page_context_only', 'detector': ENGINE,
                       'runtime_image': os.getenv('CASEPROOF_OCR_BUILD', 'unrecorded'),
                       'crop_sha256': digest(png), 'crop_base64': base64.b64encode(png).decode()}
        return {'schema': 'caseproof.visual-page.v2', 'engine': ENGINE,
                'runtime_image': os.getenv('CASEPROOF_OCR_BUILD', 'unrecorded'),
                'pypdf_version': version('pypdf'), 'normalization_version': NORMALIZATION,
                'original_sha256': digest(raw), 'page_number': page_number,
                'representation_id': representation_id,
                'layer_text': ' '.join(w.text for w in layer),
                'visual_text': ' '.join(w.text for w in ocr),
                'regions': regions, 'page_context': context, 'processed_words': len(regions), 'total_words': len(targets),
                'complete': len(regions) == len(targets) and bool(targets),
                'vector_geometry_supported': vector_supported,
                'limitations': ['Candidate review only; no calibrated acceptance or legal interpretation.',
                                'Insertions, handwriting, complex graphics and blur may be undetected.',
                                'Agreement between views is not evidence of authenticity.']}
