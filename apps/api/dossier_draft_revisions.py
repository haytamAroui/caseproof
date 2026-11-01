"""Two-phase development draft revision transport; no client-supplied actor."""
from __future__ import annotations

import http.client
import json
from typing import Any

from fastapi import HTTPException

from apps.api.access_control import AccessFailure, AccessRejected, IdentityServiceUnavailable, InvalidBearer
from apps.api.supabase_auth_verifier import (
    HttpsSupabaseUserLookup,
    SupabaseAuthUserVerifier,
)

HOST = 'ldwmocpxwskvhoojndrd.supabase.co'


class DraftRevisionClient:
    def __init__(self, key: str, trusted_key: str | None):
        self.key = key
        self.trusted_key = trusted_key
        self.verifier = SupabaseAuthUserVerifier('ldwmocpxwskvhoojndrd',
                                                HttpsSupabaseUserLookup('ldwmocpxwskvhoojndrd', key))

    def _rpc(self, name: str, payload: dict[str, Any], *, key: str, bearer: str | None) -> dict[str, Any]:
        headers = {'apikey': key, 'Content-Type': 'application/json', 'Cache-Control': 'no-store'}
        if bearer:
            headers['Authorization'] = 'Bearer ' + bearer
        connection = http.client.HTTPSConnection(HOST, timeout=20)
        try:
            connection.request('POST', '/rest/v1/rpc/' + name, json.dumps(payload).encode(), headers)
            response = connection.getresponse()
            status, raw = response.status, response.read(65537)
        except (OSError, http.client.HTTPException):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        finally:
            connection.close()
        if status == 409:
            raise HTTPException(409, 'stale draft or correction command')
        if status in (400, 401, 403, 404):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        if status != 200 or len(raw) > 65536:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError('envelope')
            return result
        except (ValueError, UnicodeError):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None

    def reserve(self, bearer: str, case: str, request: str, action: str,
                values: dict[str, Any]) -> dict[str, Any]:
        return self._rpc('caseproof_dossier_draft_reserve',
                         {'p_case': case, 'p_request': request, 'p_action': action, 'p_data': values},
                         key=self.key, bearer=bearer)

    def activate(self, bearer: str, case: str, request: str, digest: str, size: int) -> dict[str, Any]:
        key = self.trusted_key
        if not key:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            actor = self.verifier.verify_bearer(bearer)
        except InvalidBearer:
            raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED) from None
        except IdentityServiceUnavailable:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        return self._rpc('caseproof_dossier_draft_activate',
                         {'p_actor': actor.subject_id, 'p_case': case, 'p_request': request,
                          'p_sha256': digest, 'p_length': size},
                         key=key, bearer=key if key.startswith('eyJ') else None)
