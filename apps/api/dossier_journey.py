"""Signed dossier orchestration; original bytes and current grants on every request."""
from __future__ import annotations

import hashlib
import http.client
import io
import json
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

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


class DossierStore:
    def __init__(self, key: str):
        self.key = key
        self.client = JourneyClient(key)

    def rpc(self, bearer: str, case: str, action: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        con = http.client.HTTPSConnection(HOST, timeout=30)
        try:
            con.request('POST', '/rest/v1/rpc/caseproof_dossier',
                        canonical({'p_case': case, 'p_action': action, 'p_data': data or {}}).encode(),
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
                    row['image_only'] = not any((p.extract_text() or '').strip() for p in reader.pages)
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
            # Only retrieve stored geometry for explicitly mapped physical pages.
            for source in sources:
                pages = {p['pdf_page'] for e in confirmation['payload']['entries']
                         if e.get('source_version_id') == source['version_id'] for p in e['pages']}
                # Explicit physical PDF references can target any bounded page.
                if source.get('image_only'):
                    pages.update(range(1, source.get('page_count', 0) + 1))
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
        raw = originals[brief]
        found = build_findings(discover_docx_references(raw),
                               {r.part: r.text for r in extract_docx_text_regions(raw).regions}, sources, confirmation)
        report = {'schema': 'caseproof-dossier-v1', 'case_id': case, 'brief_id': brief,
                  'bundle_signature': context['bundle_signature'],
                  'confirmation_id': confirmation['request_id'] if confirmation else None,
                  'sources': sources, **found, 'professional_certificate': False, 'filing_status': 'not_assessed'}
        report['coverage']['unprocessed_sources'] = sum(bool(s.get('parse_error')) for s in sources)
        serialized = canonical(report)
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
    def dossier(case_id: str, brief_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        s, bearer = active(authorization)
        return s.load(bearer, case_id, brief_id)[0]

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
    def review(case_id: str, brief_id: str, body: DecisionBody,
               authorization: str | None = Header(default=None)) -> dict[str, Any]:
        s, bearer = active(authorization)
        report, _ = s.load(bearer, case_id, brief_id)
        finding = next((f for f in report['findings'] if f['reference_id'] == body.reference_id), None)
        if report['snapshot_hash'] != body.snapshot_hash or finding is None:
            raise HTTPException(409, 'stale or unknown finding')
        if body.decision == 'CONFIRMED_SUPPORTED' and finding['technical_check'] != 'checked':
            raise HTTPException(409, 'resolve identity and pinpoint before confirming support')
        return s.rpc(bearer, case_id, 'review', body.model_dump(mode='json'))

    @router.get(base + '/export')
    def export(case_id: str, brief_id: str, format: Literal['json', 'markdown', 'docx'] = 'json',
               authorization: str | None = Header(default=None)) -> Response:
        s, bearer = active(authorization)
        report, original = s.load(bearer, case_id, brief_id)
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
            text += '\n\nHuman decisions\n' + canonical(report['human_decisions'])
            return Response(text, media_type='text/markdown', headers=headers)
        return Response(canonical(report), media_type='application/json', headers=headers)

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
