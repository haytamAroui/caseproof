"""Signed development page-job transport and HMAC-verified artifact readback."""
from __future__ import annotations

import hashlib
import hmac
import http.client
import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict

from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.dossier_journey import DossierStore, canonical
from apps.api.litigation_evidence_app import _token
from apps.api.litigation_live_journey import HOST


class PageJobRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID


class SignedPageJobs:
    def __init__(self, dossier: DossierStore, receipt_secret: str):
        if (type(receipt_secret) is not str or len(receipt_secret) < 32
                or receipt_secret.startswith(('sb_', 'eyJ'))):
            raise ValueError('dedicated worker receipt secret required')
        self.dossier = dossier
        self.receipt_key = hmac.digest(receipt_secret.encode(), b'caseproof:page-worker:v1', 'sha256')

    def call(self, bearer: str, case: str, request: str, action: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            UUID(case)
            UUID(request)
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(422, 'invalid matter or page job identifier') from None
        if action not in {'enqueue', 'status', 'claim', 'heartbeat', 'put', 'page', 'finish', 'yield', 'cancel'}:
            raise ValueError('closed page job operation required')
        conn = http.client.HTTPSConnection(HOST, timeout=30)
        try:
            conn.request('POST', '/rest/v1/rpc/caseproof_page_job',
                         canonical({'p_case': case, 'p_request': request, 'p_action': action, 'p_data': data or {}}).encode(),
                         {'apikey': self.dossier.key, 'Authorization': 'Bearer ' + bearer,
                          'Content-Type': 'application/json', 'Cache-Control': 'no-store'})
            res = conn.getresponse()
            status, raw = res.status, res.read(400001)
        except (OSError, TimeoutError, http.client.HTTPException):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        finally:
            conn.close()
        if status in (409,):
            raise HTTPException(409, 'page input, lease or state changed')
        if status in (400, 401, 403, 404):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        if status != 200 or len(raw) > 400000:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        if type(result) is not dict:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return result

    def seal(self, payload: dict[str, Any]) -> str:
        key = self.receipt_key
        if not key:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return hmac.new(key, b'page-artifact-v1\x00' + canonical(payload).encode(), hashlib.sha256).hexdigest()

    def read_page(self, bearer: str, case: str, request: str, page_key: str, job: dict[str, Any] | None = None) -> dict[str, Any]:
        # The page RPC independently reauthorizes every read. A caller may reuse
        # a previously authorized status snapshot for manifest binding.
        current = job if job is not None else self.call(bearer, case, request, 'status')
        row = self.call(bearer, case, request, 'page', {'page_key': page_key})
        try:
            serialized = row['serialized']
            if not isinstance(serialized, str) or hashlib.sha256(serialized.encode()).hexdigest() != row['artifact_hash']:
                raise ValueError('artifact hash')
            payload = json.loads(serialized)
            if type(payload) is not dict:
                raise ValueError('artifact must be an object')
            receipt = payload.pop('server_receipt')
            if not isinstance(receipt, str) or not hmac.compare_digest(self.seal(payload), receipt):
                raise ValueError('artifact receipt')
            manifest = json.loads(current['manifest'])
            if type(manifest) is not dict or type(manifest.get('pages')) is not list:
                raise ValueError('invalid manifest')
            expected = next(p for p in manifest['pages'] if p['version_id'] + ':' + str(p['pdf_page']) == page_key)
            if (payload['schema'] != 'caseproof-page-artifact-v1' or payload['case_id'] != case
                    or payload['request_id'] != request or payload['org_id'] != current['org_id']
                    or payload['actor_id'] != current['actor_id']
                    or payload['manifest_hash'] != current['manifest_hash']
                    or payload['engine_version'] != manifest['engine_version']
                    or payload['semantic_support'] != 'not_assessed'
                    or payload['state'] not in {'ocr_candidate', 'ocr_unavailable', 'text_extracted'}
                    or payload['needs_ocr'] != expected['needs_ocr']
                    or any(payload[k] != expected[k] for k in ('document_id', 'version_id', 'original_sha256', 'pdf_page'))):
                raise ValueError('artifact binding')
            return {**payload, 'server_receipt': receipt, 'artifact_hash': row['artifact_hash']}
        except (KeyError, ValueError, TypeError, StopIteration):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None


def create_page_job_router(jobs: SignedPageJobs | None) -> APIRouter:
    router = APIRouter()
    base = '/v2/matters/{case_id}/page-jobs'

    def active(header: str | None) -> tuple[SignedPageJobs, str]:
        if jobs is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return jobs, _token(header)

    @router.post(base)
    def enqueue(case_id: str, body: PageJobRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        from apps.worker.signed_page_worker import SignedPageWorker
        service, bearer = active(authorization)
        return SignedPageWorker(service).enqueue(bearer, case_id, str(body.request_id))

    @router.get(base + '/{request_id}')
    def status(case_id: str, request_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        service, bearer = active(authorization)
        row = service.call(bearer, case_id, request_id, 'status')
        # Status is execution progress, not a statement about evidence fidelity.
        return {k: v for k, v in row.items() if k not in {'lease_token'}} | {'semantic_support': 'not_assessed'}

    @router.post(base + '/{request_id}/cancel')
    def cancel(case_id: str, request_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        service, bearer = active(authorization)
        return service.call(bearer, case_id, request_id, 'cancel')

    @router.get(base + '/{request_id}/pages/{version_id}/{page_number}')
    def page(case_id: str, request_id: str, version_id: str, page_number: int,
             authorization: str | None = Header(default=None)) -> dict[str, Any]:
        service, bearer = active(authorization)
        return service.read_page(bearer, case_id, request_id, version_id + ':' + str(page_number))

    return router
