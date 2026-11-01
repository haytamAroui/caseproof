"""Read-only authorized frozen-report navigation; never runs a check."""
from __future__ import annotations

import http.client
import json
from uuid import UUID

from fastapi import APIRouter, Header, Query
from pydantic import ValidationError

from application.litigation.workspace_contract import ReportCatalogView
from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.litigation_evidence_app import _token
from apps.api.workspace_auth import PROJECT


class WorkspaceReports:
    def __init__(self, key: str):
        self.key = key

    def read(self, bearer: str, case: str, after: str | None) -> ReportCatalogView:
        try:
            if str(UUID(case)) != case or UUID(case).int == 0:
                raise ValueError()
        except ValueError:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
        con = http.client.HTTPSConnection(PROJECT + '.supabase.co', timeout=15)
        try:
            con.request('POST', '/rest/v1/rpc/caseproof_workspace_reports',
                        json.dumps({'p_case': case, 'p_after': after}).encode(),
                        {'apikey': self.key, 'Authorization': 'Bearer ' + bearer,
                         'Content-Type': 'application/json', 'Cache-Control': 'no-store'})
            response = con.getresponse()
            status, raw = response.status, response.read(32769)
        except (OSError, TimeoutError, http.client.HTTPException):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        finally:
            con.close()
        if status in (401, 403, 404):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        if status != 200 or len(raw) > 32768:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            result = ReportCatalogView.model_validate_json(raw)
            hashes = [r.snapshot_hash for r in result.reports]
            if (result.case_id != case or hashes != sorted(set(hashes))
                    or (after is not None and any(h <= after for h in hashes))
                    or (result.next_cursor is not None and
                        (len(hashes) != 20 or result.next_cursor != hashes[-1]))):
                raise ValueError()
            return result
        except (ValueError, ValidationError):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None


def create_workspace_reports_router(reports: WorkspaceReports | None) -> APIRouter:
    router = APIRouter()

    @router.get('/v2/workspace/matters/{case_id}/reports', response_model=ReportCatalogView,
                response_model_by_alias=True)
    def read(case_id: str, after: str | None = Query(default=None, pattern='^[0-9a-f]{64}$'),
             authorization: str | None = Header(default=None)) -> ReportCatalogView:
        bearer = _token(authorization)
        if reports is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return reports.read(bearer, case_id, after)

    return router
