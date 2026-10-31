"""Resumable signed-user worker: no stored bearer, no admin/RLS bypass, no LLM."""
from __future__ import annotations

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Event, Thread
from typing import Any

from application.extraction.contracts import ExtractionError
from apps.api.dossier_journey import canonical
from apps.api.signed_document_parse import parse_verified_original
from apps.api.signed_page_jobs import SignedPageJobs
from infrastructure.parsers.limited import LimitedDocumentParser
from infrastructure.parsers.ocr_geometry_sidecar import encode_page_geometry
from infrastructure.parsers.pdf_ocr import LocalPDFOCR, OCRUnavailable
from packages.evidence_kernel.domain.source_versions import SourceVersion


class SignedPageWorker:
    def __init__(self, jobs: SignedPageJobs, ocr: LocalPDFOCR | None = None):
        self.jobs = jobs
        self.ocr = ocr or LocalPDFOCR()
        self.engine = LimitedDocumentParser().identity + ';ocr=poppler+tesseract-tsv-v1;image=' + os.getenv('CASEPROOF_OCR_IMAGE', 'local-unapproved')

    def inputs(self, bearer: str, case: str, request: str) -> tuple[dict[str, Any], dict[str, bytes]]:
        context = self.jobs.dossier.rpc(bearer, case, 'context')
        sources, originals = self.jobs.dossier.sources(bearer, case, inspect_pdf=False)
        if sum(len(raw) for raw in originals.values()) > 20 * 1024 * 1024:
            raise ExtractionError('worker_bundle_byte_limit')
        pages = []
        for source in sorted(sources, key=lambda x: x['version_id']):
            if source['role'] != 'exhibit' or source['media_type'] != 'application/pdf':
                continue
            _, manifest = parse_verified_original(document_id=source['document_id'], version_id=source['version_id'],
                                                   data=originals[source['version_id']], media_type='application/pdf')
            for page in manifest['pages']:
                pages.append({'document_id': source['document_id'], 'version_id': source['version_id'],
                              'original_sha256': source['sha256'], 'pdf_page': page['pdf_page'],
                              'needs_ocr': page['status'] == 'needs_ocr'})
        if not 1 <= len(pages) <= 200:
            raise ExtractionError('worker_bundle_page_limit')
        return {'schema': 'caseproof-page-job-v1', 'case_id': case, 'request_id': request,
                'bundle_signature': context['bundle_signature'], 'engine_version': self.engine, 'pages': pages}, originals

    def enqueue(self, bearer: str, case: str, request: str) -> dict[str, Any]:
        manifest, _ = self.inputs(bearer, case, request)
        serialized = canonical(manifest)
        return self.jobs.call(bearer, case, request, 'enqueue',
                              {'manifest': serialized, 'manifest_hash': hashlib.sha256(serialized.encode()).hexdigest()})

    def run(self, bearer: str, case: str, request: str, *, max_pages: int = 200) -> dict[str, Any]:
        if type(max_pages) is not int or not 1 <= max_pages <= 200:
            raise ExtractionError('bounded worker batch required')
        status = self.jobs.call(bearer, case, request, 'status')
        manifest, originals = self.inputs(bearer, case, request)
        if canonical(manifest) != status['manifest'] or hashlib.sha256(canonical(manifest).encode()).hexdigest() != status['manifest_hash']:
            raise ExtractionError('worker_manifest_changed')
        expected_keys = {p['version_id'] + ':' + str(p['pdf_page']) for p in manifest['pages']}
        if len(expected_keys) != len(manifest['pages']):
            raise ExtractionError('worker_duplicate_page_identity')
        completed_rows = status['results']
        completed = {r['page_key'] for r in completed_rows}
        if len(completed) != len(completed_rows) or not completed.issubset(expected_keys):
            raise ExtractionError('worker_invalid_checkpoint')
        for key in completed:
            self.jobs.read_page(bearer, case, request, key, job=status)
        if status['state'] == 'succeeded':
            return status
        lease = self.jobs.call(bearer, case, request, 'claim')
        token = lease['lease_token']
        stop, lost = Event(), Event()

        def heartbeat() -> None:
            while not stop.wait(20):
                try:
                    self.jobs.call(bearer, case, request, 'heartbeat', {'lease_token': token})
                except Exception:
                    lost.set()
                    return
        renew = Thread(target=heartbeat, daemon=True)
        renew.start()
        pending = [p for p in manifest['pages'] if p['version_id'] + ':' + str(p['pdf_page']) not in completed][:max_pages]
        # Parse each text-bearing source once, not once per physical page.
        parsed_sources: dict[str, tuple[str, dict[str, Any]]] = {}
        for page in pending:
            if not page['needs_ocr'] and page['version_id'] not in parsed_sources:
                raw = originals[page['version_id']]
                parsed_sources[page['version_id']] = parse_verified_original(
                    document_id=page['document_id'], version_id=page['version_id'],
                    data=raw, media_type='application/pdf')

        def process(page: dict[str, Any]) -> None:
            if lost.is_set():
                raise ExtractionError('worker_lease_lost')
            raw = originals[page['version_id']]
            if hashlib.sha256(raw).hexdigest() != page['original_sha256']:
                raise ExtractionError('worker_source_changed')
            artifact: dict[str, Any] = {'schema': 'caseproof-page-artifact-v1', 'org_id': lease['org_id'],
                'actor_id': lease['actor_id'], 'case_id': case, 'request_id': request, 'manifest_hash': status['manifest_hash'],
                'engine_version': self.engine, **page, 'semantic_support': 'not_assessed'}
            if page['needs_ocr']:
                try:
                    source = SourceVersion(document_id=page['document_id'], version_id=page['version_id'],
                                           sha256_hex=page['original_sha256'], content=raw,
                                           ingested_at=datetime.now(UTC), media_type='application/pdf')
                    ocr = self.ocr.recognize(source, page_number=page['pdf_page'], languages=('nl', 'fr'))
                    reference, geometry = encode_page_geometry(ocr)
                    artifact.update({'state': 'ocr_candidate', 'geometry': json.loads(geometry),
                                     'geometry_sha256': reference.geometry_sha256, 'ocr_engine': ocr.engine})
                except OCRUnavailable:
                    artifact.update({'state': 'ocr_unavailable', 'reason': 'local_ocr_unavailable'})
            else:
                # Parse in a resource-limited child; preserve exact physical page offsets.
                text, parsed = parsed_sources[page['version_id']]
                blocks = [b for b in parsed['blocks'] if b['page_index'] == page['pdf_page'] - 1]
                artifact.update({'state': 'text_extracted', 'blocks': [
                    {**b, 'text': text[b['start']:b['end']]} for b in blocks]})
            artifact['server_receipt'] = self.jobs.seal(artifact)
            serialized = canonical(artifact)
            if lost.is_set():
                raise ExtractionError('worker_lease_lost')
            self.jobs.call(bearer, case, request, 'put', {'lease_token': token,
                'page_key': page['version_id'] + ':' + str(page['pdf_page']), 'serialized': serialized,
                'artifact_hash': hashlib.sha256(serialized.encode()).hexdigest()})
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(process, pending))
            current = self.jobs.call(bearer, case, request, 'status')
            current_keys = {r['page_key'] for r in current['results']}
            if len(current_keys) != len(current['results']) or not current_keys.issubset(expected_keys):
                raise ExtractionError('worker_invalid_checkpoint')
            if current_keys == expected_keys:
                for key in sorted(current_keys):
                    self.jobs.read_page(bearer, case, request, key, job=current)
            if lost.is_set():
                raise ExtractionError('worker_lease_lost')
            action = 'finish' if current_keys == expected_keys else 'yield'
            return self.jobs.call(bearer, case, request, action, {'lease_token': token})
        finally:
            stop.set()
            renew.join(timeout=31)


def main() -> None:
    import argparse

    from apps.api.dossier_journey import DossierStore
    parser = argparse.ArgumentParser(description='Signed development page-worker batch')
    parser.add_argument('--case', required=True)
    parser.add_argument('--job', required=True)
    parser.add_argument('--max-pages', type=int, default=200)
    args = parser.parse_args()
    jobs = SignedPageJobs(DossierStore(os.environ['CASEPROOF_DEV_PUBLISHABLE_KEY']),
                          os.environ['CASEPROOF_PAGE_WORKER_SECRET'])
    result = SignedPageWorker(jobs).run(os.environ['CASEPROOF_WORKER_BEARER'], args.case, args.job, max_pages=args.max_pages)
    # No actor, matter identifier, token, text, source hash or crop in console output.
    print(json.dumps({'schema': 'page-worker-receipt-v1', 'state': result['state'],
                      'pages_checkpointed': len(result['results']), 'semantic_support': 'not_assessed'}))


if __name__ == '__main__':
    main()
