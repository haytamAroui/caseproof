"""Concrete bounded local page extraction with mandatory immutable artifact persistence."""
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from application.extraction.contracts import ExtractionError, canonical
from application.runtime.pages import PageInput
from infrastructure.parsers.limited import LimitedDocumentParser
from packages.evidence_kernel.domain.source_versions import SourceVersion


class BoundedPageParser:
    def __init__(self, *, load_original: Callable[[PageInput], bytes],
                 persist_artifact: Callable[[PageInput, str, bytes], None]):
        # load_original must authorize the current scope; persist must be immutable,
        # scoped and durable before returning. Both are server composition ports.
        self.load_original, self.persist_artifact = load_original, persist_artifact
        self.parser = LimitedDocumentParser(timeout=8)

    @property
    def identity(self) -> str:
        return self.parser.identity

    def __call__(self, page: PageInput) -> dict[str, Any]:
        raw = self.load_original(page)
        if sha256(raw).hexdigest() != page.original_sha256:
            raise ExtractionError('page_source_hash_changed')
        artifact = self.parser.parse(SourceVersion(
            document_id=page.version_id, version_id=page.version_id,
            sha256_hex=page.original_sha256, content=raw, ingested_at=datetime.now(UTC),
            media_type='application/pdf'))
        blocks = [b for b in artifact['blocks'] if b['page_index'] == page.pdf_page - 1]
        warnings = artifact['warnings']
        known_page = bool(blocks) or any(w.endswith(f':page:{page.pdf_page - 1}') for w in warnings)
        if not known_page:
            raise ExtractionError('page_outside_parsed_source')
        payload = canonical({'schema': 'page-text-artifact-v1', 'original_sha256': page.original_sha256,
                             'version_id': page.version_id, 'pdf_page': page.pdf_page,
                             'parser_id': artifact['parser_id'],
                             'blocks': [{**b, 'text': artifact['text'][b['start']:b['end']]} for b in blocks],
                             'warnings': warnings,
                             'semantic_support': 'not_assessed'}).encode()
        if len(payload) > 512000:
            raise ExtractionError('page_artifact_limit')
        identity = sha256(payload).hexdigest()
        self.persist_artifact(page, identity, payload)
        # A scan remains uncertain; extraction success is not fidelity or support.
        return {'artifact_sha256': identity, 'uncertain': bool(warnings) or not blocks}
