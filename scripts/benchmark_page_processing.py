"""Reproducible 200-page local parsing benchmark, not a signed OCR/user benchmark."""
from __future__ import annotations

import io
import json
import resource
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from uuid import uuid4

from reportlab.pdfgen import canvas

from application.extraction.contracts import Scope
from application.extraction.journal import MemoryJournal
from application.runtime.pages import PageCoordinator, PageInput, PagePlan
from infrastructure.execution.page_parser import BoundedPageParser


def main() -> None:
    originals = {}
    pages = []
    # Four source files respect the current 64-page per-source parser boundary.
    for document in range(4):
        out = io.BytesIO()
        pdf = canvas.Canvas(out, invariant=1)
        for number in range(1, 51):
            pdf.drawString(40, 740, f'SYNTHETIC source {document}, physical page {number}; EUR 1250.00')
            pdf.showPage()
        pdf.save()
        raw = out.getvalue()
        version = f'synthetic-{document}'
        originals[version] = raw
        pages.extend(PageInput(version, sha256(raw).hexdigest(), p) for p in range(1, 51))
    with TemporaryDirectory() as directory:
        count = 0
        def persist(page, identity, payload):
            nonlocal count
            path = Path(directory) / identity
            with path.open('xb') as file:
                file.write(payload)
                file.flush()
                import os
                os.fsync(file.fileno())
            count += 1
        processor = BoundedPageParser(load_original=lambda p: originals[p.version_id], persist_artifact=persist)
        scope = Scope(uuid4(), uuid4())
        coordinator = PageCoordinator(MemoryJournal(), authorize=lambda: None, cancelled=lambda: False)
        plan = PagePlan(tuple(pages), processor.identity, concurrency=2)
        started = monotonic()
        report = coordinator.run(scope, 'synthetic-200-page-benchmark', plan, processor)
        duration = monotonic() - started
        assert report['completed'] == count == 200 and report['failed'] == 0
        replay = coordinator.run(scope, 'synthetic-200-page-benchmark', plan,
                                 lambda p: (_ for _ in ()).throw(AssertionError('reparsed checkpoint')))
        assert replay == report
        print(json.dumps({'schema': 'page-benchmark-v1', 'pages': 200, 'source_files': 4,
                          'ocr_pages': 0, 'concurrency': 2, 'seconds': round(duration, 3),
                          'parent_peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                          'child_peak_rss_kib': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                          'completed': report['completed'], 'failed': report['failed'],
                          'checkpoint_replay_equal': True, 'signed_live': False,
                          'practitioner_accuracy_measured': False}, sort_keys=True))


if __name__ == '__main__':
    main()
