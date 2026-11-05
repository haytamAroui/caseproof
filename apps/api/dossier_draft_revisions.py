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


def stale_snapshot_conflict(raw: bytes) -> bool:
    try:
        error = json.loads(raw)
    except (ValueError, UnicodeError):
        return False
    return (
        isinstance(error, dict)
        and error.get("code") == "23505"
        and error.get("message") in ("stale snapshot", "stale parent")
    )


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
            if stale_snapshot_conflict(raw):
                raise HTTPException(412, "snapshot is stale")
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

    def recovery(self, bearer: str, case: str, parent: str, snapshot: str, reference: str) -> dict[str, Any]:
        return self._rpc('caseproof_dossier_draft_recovery',
                         {'p_case': case, 'p_parent': parent, 'p_snapshot': snapshot, 'p_reference': reference},
                         key=self.key, bearer=bearer)

    def editor_review(
        self, bearer: str, case: str, parent: str, snapshot: str,
        review_request: str, values: dict[str, Any],
    ) -> dict[str, Any]:
        """Separate actor-scoped whole-DOCX review, never a synthetic finding."""
        return self._rpc(
            'caseproof_dossier_document_edit_review',
            {
                'p_case': case, 'p_parent': parent, 'p_snapshot': snapshot,
                'p_request': review_request, 'p_data': values,
            },
            key=self.key, bearer=bearer,
        )

    def editor_reserve(
        self, bearer: str, case: str, parent: str, snapshot: str,
        request: str, review_request: str, values: dict[str, Any],
    ) -> dict[str, Any]:
        """Atomically require a separately saved, actor-bound review receipt."""
        return self._rpc(
            'caseproof_dossier_document_edit_reserve',
            {
                'p_case': case, 'p_parent': parent, 'p_snapshot': snapshot,
                'p_request': request, 'p_review': review_request,
                'p_data': values,
            },
            key=self.key, bearer=bearer,
        )

    def editor_status(
        self, bearer: str, case: str, request: str, review_request: str,
        fingerprint: str,
    ) -> dict[str, Any]:
        """Always recheck fresh draft:edit scope even for an active operation."""
        return self._rpc(
            "caseproof_dossier_document_edit_status",
            {
                "p_case": case, "p_request": request,
                "p_review": review_request, "p_command": fingerprint,
            }, key=self.key, bearer=bearer,
        )

    def editor_activate(
        self, bearer: str, case: str, request: str,
        review_request: str, digest: str, size: int,
    ) -> dict[str, Any]:
        """Recheck fresh document-edit scope in a separate trusted activation RPC."""
        key = self.trusted_key
        if not key:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            actor = self.verifier.verify_bearer(bearer)
        except InvalidBearer:
            raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED) from None
        except IdentityServiceUnavailable:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        return self._rpc(
            "caseproof_dossier_document_edit_activate",
            {
                "p_actor": actor.subject_id, "p_case": case,
                "p_request": request, "p_review": review_request,
                "p_sha256": digest, "p_length": size,
            },
            key=key, bearer=key if key.startswith("eyJ") else None,
        )

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
