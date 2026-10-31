"""Signed dossier orchestration; original bytes and current grants on every request."""
from __future__ import annotations

import base64
import hashlib
import hmac
import http.client
import io
import json
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from application.litigation.regional_fidelity import select_visual_assessment
from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.litigation_evidence_app import _token
from apps.api.litigation_headless_verification import DecisionBody
from apps.api.litigation_live_journey import HOST, JourneyClient
from apps.api.signed_supabase_originals import PrivateStorageFailure
from domains.disputes.dossier_verification import build_findings
from domains.disputes.reference_detection import detect_exhibit_references
from infrastructure.parsers.docx_reference_discovery import discover_docx_references
from infrastructure.parsers.docx_text_regions import extract_docx_text_regions
from infrastructure.parsers.dossier_docx_export import annotated_docx
from infrastructure.parsers.pdf_ocr import OCRUnavailable
from infrastructure.parsers.pdf_visual_fidelity import PDFVisualFidelity


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


class PageConfirmation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    space: Literal['printed', 'bundle']
    label: str = Field(pattern=r'^\d{1,6}$')
    pdf_page: int = Field(ge=1, le=64)
    rationale: str = Field(min_length=3, max_length=500)


class IdentityConfirmation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    label: Literal['stuk', 'piece']
    number: str = Field(pattern=r'^\d{1,4}(?:bis|ter)?$')
    source_version_id: str | None = None
    pages: list[PageConfirmation] = Field(default_factory=list, max_length=128)


class InventoryConfirmation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    bundle_signature: str = Field(pattern=r'^[0-9a-f]{64}$')
    request_id: str
    inventory_complete: bool
    entries: list[IdentityConfirmation] = Field(max_length=512)


class VisualDecisionBody(DecisionBody):
    reviewed_region_ids: list[str] = Field(default_factory=list, max_length=96)


class DossierStore:
    def __init__(self, key: str, receipt_secret: str | None = None):
        self.key = key
        self.client = JourneyClient(key)
        self.visual = PDFVisualFidelity()
        # Domain-separated receipt key, never the public client key. No key is
        # serialized, logged, persisted in source, or accepted from HTTP.
        self.receipt_key = (hmac.digest(receipt_secret.encode(), b'caseproof:dossier-receipt:v1', 'sha256')
                            if receipt_secret and len(receipt_secret) >= 32
                            and not receipt_secret.startswith('sb_publishable_') else None)

    def rpc(self, bearer: str, case: str, action: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        con = http.client.HTTPSConnection(HOST, timeout=30)
        try:
            function = 'caseproof_dossier_snapshot_read' if action == 'read' else 'caseproof_dossier'
            params = ({'p_case': case, 'p_snapshot': (data or {}).get('snapshot_hash')} if action == 'read'
                      else {'p_case': case, 'p_action': action, 'p_data': data or {}})
            con.request('POST', '/rest/v1/rpc/' + function, canonical(params).encode(),
                        {'apikey': self.key, 'Authorization': 'Bearer ' + bearer,
                         'Content-Type': 'application/json', 'Cache-Control': 'no-store'})
            res = con.getresponse()
            status, raw = res.status, res.read(4_000_001)
        except (OSError, TimeoutError, http.client.HTTPException):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        finally:
            con.close()
        if status in (400, 401, 403, 404):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        if status == 409:
            raise HTTPException(409, 'stale dossier or idempotency conflict')
        if status != 200 or len(raw) > 4_000_000:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return result

    def receipt(self, payload: dict[str, Any]) -> str:
        key = getattr(self, 'receipt_key', None)
        if not key:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return hmac.new(key, canonical(payload).encode(), hashlib.sha256).hexdigest()

    def reopen(self, bearer: str, case: str, brief: str, snapshot: str) -> tuple[dict[str, Any], bytes]:
        stored = self.rpc(bearer, case, 'read', {'snapshot_hash': snapshot})
        serialized = stored.get('serialized')
        if not isinstance(serialized, str) or hashlib.sha256(serialized.encode()).hexdigest() != snapshot:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        report = json.loads(serialized)
        attestation = report.pop('server_receipt', None)
        expected = self.receipt(report)
        if not isinstance(attestation, str) or not hmac.compare_digest(expected, attestation):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        report['server_receipt'] = attestation
        if report.get('case_id') != case or report.get('brief_id') != brief:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        sources, originals = self.sources(bearer, case)
        current = {(s['version_id'], s['sha256']) for s in sources}
        recorded = {(s['version_id'], s['sha256']) for s in report.get('sources', [])}
        if not recorded or recorded != current:
            raise HTTPException(409, 'source snapshot changed')
        report['snapshot_hash'] = snapshot
        return report, originals[brief]

    def sources(self, bearer: str, case: str) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
        manifest = self.client.bundle_manifest(bearer, case)['sources']
        originals = {}
        sources = []
        for item in manifest:
            row = dict(item)
            try:
                raw = self.client.library.read(bearer=bearer, case_id=case,
                                               document_id=row['document_id'], version_id=row['version_id'])
            except PrivateStorageFailure:
                raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
            if len(raw) != row['byte_length'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
                raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
            originals[row['version_id']] = raw
            if row['media_type'] == 'application/pdf':
                try:
                    reader = PdfReader(io.BytesIO(raw), strict=True)
                    if reader.is_encrypted or not 0 < len(reader.pages) <= 64:
                        raise ValueError('unsupported PDF')
                    row['page_count'] = len(reader.pages)
                    row['image_only_pages'] = [i for i, page in enumerate(reader.pages, 1)
                                              if not (page.extract_text() or '').strip()]
                    row['image_only'] = len(row['image_only_pages']) == row['page_count']
                except (ValueError, PdfReadError, OSError, KeyError):
                    row['page_count'] = 0
                    row['parse_error'] = 'unreadable_or_unsupported_pdf'
            sources.append(row)
        return sources, originals

    def load(self, bearer: str, case: str, brief: str) -> tuple[dict[str, Any], bytes]:
        context = self.rpc(bearer, case, 'context')
        sources, originals = self.sources(bearer, case)
        drafts = [s for s in sources if s['role'] == 'draft' and s['version_id'] == brief]
        if len(drafts) != 1:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        raw = originals[brief]
        discovery = discover_docx_references(raw)
        regions = {r.part: r.text for r in extract_docx_text_regions(raw).regions}
        confirmation = context.get('confirmation')
        inventory = next((x for x in sources if x['role'] == 'inventory'), None)
        inventory_readable = False
        inventory_identities: set[tuple[str, str]] = set()
        if inventory is not None:
            try:
                inventory_text = originals[inventory['version_id']].decode('utf-8')
                inventory_identities = {('stuk' if r.label.startswith('stuk') else 'piece', r.number)
                                        for r in detect_exhibit_references(inventory_text, region='inventory')}
                inventory_readable = True
            except UnicodeError:
                inventory['parse_error'] = 'unreadable_utf8_inventory'
        if confirmation:
            supplied = confirmation['payload']['entries']
            supplied_identities = {(e['label'], e['number']) for e in supplied}
            # Never infer absence from an omitted confirmation row. Inventory
            # bytes, not client JSON, establish known inventory membership.
            normalized = [e for e in supplied if (e['label'], e['number']) in inventory_identities]
            normalized += [{'label': label, 'number': number, 'source_version_id': None, 'pages': []}
                           for label, number in sorted(inventory_identities - supplied_identities)]
            confirmation = {**confirmation, 'payload': {**confirmation['payload'], 'entries': normalized,
                'inventory_complete': bool(inventory_readable and confirmation['payload']['inventory_complete']
                                           and supplied_identities == inventory_identities)}}
        if confirmation:
            initial = build_findings(discovery, regions, sources, confirmation)
            # Only retrieve stored geometry for explicitly mapped physical pages.
            for source in sources:
                pages = {p['pdf_page'] for e in confirmation['payload']['entries']
                         if e.get('source_version_id') == source['version_id'] for p in e['pages']}
                # Resolve actual referenced physical pages independently of the
                # whole-file text status, including scanned pages in mixed PDFs.
                pages.update(f['pdf_page'] for f in initial['findings']
                             if f['version_id'] == source['version_id'] and f['pdf_page'] is not None)
                geometry = {}
                for page in sorted(pages):
                    try:
                        ref, payload = self.client.read_geometry(bearer, source['version_id'], page)
                    except AccessRejected as error:
                        if error.http_status == 503:
                            raise
                        continue
                    words = payload.get('words', [])
                    if ref.original_sha256 == source['sha256'] and isinstance(words, list) and words and isinstance(words[0], dict):
                        w = words[0]
                        geometry[str(page)] = {'crop': {'page_number': page,
                            **{k: w[k] for k in ('left', 'top', 'width', 'height')},
                            'geometry_sha256': ref.geometry_sha256}}
                source['geometry'] = geometry
        found = build_findings(discovery, regions, sources, confirmation)
        # Both text-layer PDFs and scans take the visual path. Inputs come only
        # from verified private originals; unavailable engines never count as pass.
        visual_pages: dict[tuple[str, int], dict[str, Any]] = {}
        visual_budget = 4
        for finding in found['findings']:
            version, page_number = finding['version_id'], finding['pdf_page']
            if version is None or page_number is None:
                finding['visual_assessment'] = select_visual_assessment(None, None)
                continue
            key = (version, page_number)
            if key not in visual_pages:
                source = next(s for s in sources if s['version_id'] == version)
                try:
                    if len(visual_pages) >= visual_budget:
                        raise OCRUnavailable('visual_page_budget_exceeded')
                    visual_pages[key] = getattr(self, "visual", PDFVisualFidelity()).inspect(originals[version],
                        original_sha256=source['sha256'], page_number=page_number)
                except OCRUnavailable as error:
                    visual_pages[key] = {'error': str(error)}
            region = regions.get(finding['region'], '')
            tail = region[finding['offsets']['end']:]
            import re

            # Only an explicitly delimited quotation immediately following the
            # page reference is linked. No inferred quote from nearby prose.
            quoted = re.match(r'^\s*[,;:]?\s*(?:(?:PDF|printed|gedrukte|imprimée|bundle|bundel|liasse)\s+)?(?:pp?|pages?)\.?\s*\d+\s*[,;:.]?\s*["“«]([^"”»]{1,1000})["”»]', tail, re.I)
            assessment = select_visual_assessment(visual_pages[key], quoted[1] if quoted else None)
            finding['visual_assessment'] = assessment
            if assessment['state'] != 'not_assessed':
                finding['fidelity'] = assessment['state']
            # Identity/pinpoint remain independently checked; visual conflict
            # never changes exhibit identity or claims human semantic support.
        found['coverage']['visual_pages_attempted'] = len(visual_pages)
        found['coverage']['visual_pages_completed'] = sum(not p.get('error') for p in visual_pages.values())
        found['coverage']['visual_findings_not_assessed'] = sum(
            f['visual_assessment']['state'] == 'not_assessed' for f in found['findings'])
        report = {'schema': 'caseproof-dossier-v1', 'case_id': case, 'brief_id': brief,
                  'bundle_signature': context['bundle_signature'],
                  'confirmation_id': confirmation['request_id'] if confirmation else None,
                  'inventory_confirmation': {k: confirmation.get(k) for k in ('request_id', 'reviewer_id', 'timestamp')} if confirmation else None,
                  'sources': sources, 'visual_pages': {v + ':' + str(p): data for (v,p),data in visual_pages.items()}, **found, 'professional_certificate': False, 'filing_status': 'not_assessed'}
        report['coverage']['unprocessed_sources'] = sum(bool(s.get('parse_error')) for s in sources)
        report['server_receipt'] = self.receipt(report)
        serialized = canonical(report)
        if len(serialized.encode()) > 1_900_000:
            raise HTTPException(422, 'visual snapshot budget exceeded; reduce assessed pages')
        report['snapshot_hash'] = hashlib.sha256(serialized.encode()).hexdigest()
        self.rpc(bearer, case, 'snapshot', {'serialized': serialized, 'snapshot_hash': report['snapshot_hash']})
        return report, raw


def create_dossier_router(store: DossierStore | None) -> APIRouter:
    router = APIRouter()
    base = '/v2/matters/{case_id}/briefs/{brief_id}/dossier'

    def active(header: str | None) -> tuple[DossierStore, str]:
        if store is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return store, _token(header)

    @router.get(base)
    def dossier(case_id: str, brief_id: str, snapshot_hash: str | None = None, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        s, bearer = active(authorization)
        return (s.reopen(bearer, case_id, brief_id, snapshot_hash) if snapshot_hash
                else s.load(bearer, case_id, brief_id))[0]

    @router.post(base + '/confirmation')
    def confirm(case_id: str, brief_id: str, body: InventoryConfirmation,
                authorization: str | None = Header(default=None)) -> dict[str, Any]:
        s, bearer = active(authorization)
        try:
            UUID(body.request_id)
            sources, originals = s.sources(bearer, case_id)
            inventory = [x for x in sources if x['role'] == 'inventory']
            if len(inventory) != 1:
                raise ValueError('missing inventory')
            refs = detect_exhibit_references(originals[inventory[0]['version_id']].decode('utf-8'), region='inventory')
            identities = {('stuk' if r.label.startswith('stuk') else 'piece', r.number) for r in refs}
            for entry in body.entries:
                if (entry.label, entry.number) not in identities:
                    raise ValueError('identity absent from preserved inventory')
                matches = [x for x in sources if x['version_id'] == entry.source_version_id and x['role'] == 'exhibit']
                if entry.source_version_id is not None and len(matches) != 1:
                    raise ValueError('source outside bundle')
                if entry.pages and (not matches or any(p.pdf_page > matches[0].get('page_count', 0) for p in entry.pages)):
                    raise ValueError('page outside preserved source')
        except (ValueError, UnicodeError):
            raise HTTPException(422, 'invalid inventory/source/page confirmation') from None
        if body.inventory_complete and {(e.label, e.number) for e in body.entries} != identities:
            raise HTTPException(422, 'complete inventory confirmation must include every discovered inventory identity')
        payload = body.model_dump(exclude={'bundle_signature', 'request_id'})
        return s.rpc(bearer, case_id, 'confirm', {'bundle_signature': body.bundle_signature,
                     'request_id': body.request_id, 'payload': payload})

    @router.post(base + '/reviews')
    def review(case_id: str, brief_id: str, body: VisualDecisionBody,
               authorization: str | None = Header(default=None)) -> dict[str, Any]:
        s, bearer = active(authorization)
        report, _ = s.reopen(bearer, case_id, brief_id, body.snapshot_hash)
        finding = next((f for f in report['findings'] if f['reference_id'] == body.reference_id), None)
        if report['snapshot_hash'] != body.snapshot_hash or finding is None:
            raise HTTPException(409, 'stale or unknown finding')
        if body.decision == 'CONFIRMED_SUPPORTED' and finding['technical_check'] != 'checked':
            raise HTTPException(409, 'resolve identity and pinpoint before confirming support')
        required = {r['region_id'] for r in finding.get('visual_assessment', {}).get('regions', [])}
        if required and set(body.reviewed_region_ids) != required:
            raise HTTPException(409, 'inspect and explicitly confirm every selected visual region')
        payload = body.model_dump(mode='json')
        return s.rpc(bearer, case_id, 'review', payload)

    @router.get(base + '/export')
    def export(case_id: str, brief_id: str, format: Literal['json', 'markdown', 'docx'] = 'json', snapshot_hash: str | None = None,
               authorization: str | None = Header(default=None)) -> Response:
        s, bearer = active(authorization)
        report, original = (s.reopen(bearer, case_id, brief_id, snapshot_hash) if snapshot_hash
                            else s.load(bearer, case_id, brief_id))
        report['human_decisions'] = s.rpc(bearer, case_id, 'decisions', {'snapshot_hash': report['snapshot_hash']})['decisions']
        headers = {'X-CaseProof-Snapshot': report['snapshot_hash'], 'Cache-Control': 'no-store'}
        if format == 'docx':
            try:
                data = annotated_docx(original, report)
            except ValueError:
                raise HTTPException(422, 'draft cannot be annotated') from None
            return Response(data, media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                            headers={**headers, 'Content-Disposition': 'attachment; filename=caseproof-annotated.docx'})
        if format == 'markdown':
            text = '# CaseProof scoped dossier report\n\n' + canonical(report['coverage']) + '\n\n'
            text += '\n'.join(f"- {f['reference_id']}: {f['literal']} — {f['identity']}; {f['page_mapping']}; {f['fidelity']}; {f['support']}"
                              for f in report['findings'])
            text += '\n\nVisual assessments\n' + canonical([{
                'reference_id': f['reference_id'], 'assessment': {
                    **f.get('visual_assessment', {}), 'regions': [{k: v for k, v in r.items()
                        if k != 'crop_base64'} for r in f.get('visual_assessment', {}).get('regions', [])]}}
                for f in report['findings']])
            text += '\n\nHuman decisions\n' + canonical(report['human_decisions'])
            return Response(text, media_type='text/markdown', headers=headers)
        return Response(canonical(report), media_type='application/json', headers=headers)

    @router.get(base + '/snapshots/{snapshot_hash}/regions/{region_id}/crop')
    def visual_crop(case_id: str, brief_id: str, snapshot_hash: str, region_id: str,
                    authorization: str | None = Header(default=None)) -> Response:
        s, bearer = active(authorization)
        report, _ = s.reopen(bearer, case_id, brief_id, snapshot_hash)
        matches = [r for page in report.get('visual_pages', {}).values()
                   for r in [*page.get('regions', []), *([page['page_context']] if page.get('page_context') else [])]
                   if r['region_id'] == region_id]
        if len(matches) != 1:
            raise HTTPException(404, 'visual region unavailable')
        region = matches[0]
        try:
            png = base64.b64decode(region['crop_base64'], validate=True)
        except (ValueError, KeyError):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        if hashlib.sha256(png).hexdigest() != region['crop_sha256']:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return Response(png, media_type='image/png', headers={'Cache-Control': 'no-store',
            'X-CaseProof-Crop-SHA256': region['crop_sha256'],
            'X-CaseProof-Original-SHA256': region['original_sha256'],
            'X-CaseProof-Snapshot': snapshot_hash, 'X-Content-Type-Options': 'nosniff'})

    @router.get(base + '/sources/{version_id}/original')
    def original(case_id: str, brief_id: str, version_id: str,
                 authorization: str | None = Header(default=None)) -> Response:
        s, bearer = active(authorization)
        sources, files = s.sources(bearer, case_id)
        if not any(x['role'] == 'draft' and x['version_id'] == brief_id for x in sources):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        source = next((x for x in sources if x['version_id'] == version_id), None)
        if source is None:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        return Response(files[version_id], media_type='application/octet-stream',
                        headers={'Content-Disposition': 'attachment; filename=caseproof-original',
                                 'X-CaseProof-Original-SHA256': source['sha256']})

    @router.get(base + '/sources/{version_id}/pages/{page_number}')
    def page(case_id: str, brief_id: str, version_id: str, page_number: int,
             authorization: str | None = Header(default=None)) -> Response:
        s, bearer = active(authorization)
        sources, files = s.sources(bearer, case_id)
        if not any(x['role'] == 'draft' and x['version_id'] == brief_id for x in sources):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        source = next((x for x in sources if x['version_id'] == version_id), None)
        if not source or not 1 <= page_number <= source.get('page_count', 0):
            raise HTTPException(404, 'source page unavailable')
        writer = PdfWriter()
        writer.add_page(PdfReader(io.BytesIO(files[version_id])).pages[page_number - 1])
        out = io.BytesIO()
        writer.write(out)
        return Response(out.getvalue(), media_type='application/pdf', headers={
            'X-CaseProof-Original-SHA256': source['sha256'], 'X-CaseProof-PDF-Page': str(page_number)})

    return router
