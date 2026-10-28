"""Read existing private matters through the signed Supabase invoker view.

The bearer is passed to PostgREST; the database derives the actor and applies
the existing matter RLS. This adapter never creates matters or grants.
"""
from __future__ import annotations

import http.client
import json
from uuid import UUID

from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.signed_supabase_source_library import PROJECT_HOST


class SignedMatterCatalog:
    def __init__(self, publishable_key: str) -> None:
        if (not publishable_key.startswith("sb_publishable_") or len(publishable_key) > 512
                or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
                       for c in publishable_key)):
            raise ValueError("A development publishable key is required")
        self._key = publishable_key

    def list_matters(self, bearer: str) -> list[dict[str, object]]:
        if (not isinstance(bearer, str) or not 0 < len(bearer) <= 8192
                or any(not 33 <= ord(char) <= 126 for char in bearer)):
            raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED)
        conn = http.client.HTTPSConnection(PROJECT_HOST, timeout=12)
        try:
            path = ("/rest/v1/caseproof_private_matters?"
                    "select=case_id,case_revision,state&order=case_id&limit=101")
            conn.request("GET", path, headers={
                "apikey": self._key, "Authorization": "Bearer " + bearer,
                "Accept": "application/json", "Cache-Control": "no-store",
            })
            response = conn.getresponse()
            status, raw = response.status, response.read(65537)
        except (OSError, TimeoutError, http.client.HTTPException):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        finally:
            conn.close()
        if status in (401, 403):
            raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED)
        if status != 200 or len(raw) > 65_536:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            rows = json.loads(raw)
            if not isinstance(rows, list) or len(rows) > 100:
                raise ValueError("too many matters")
            result = []
            for row in rows:
                case_id, revision, state = row["case_id"], row["case_revision"], row["state"]
                if (not isinstance(case_id, str) or str(UUID(case_id)) != case_id
                        or UUID(case_id).int == 0 or type(revision) is not int or revision < 1
                        or not isinstance(state, str) or len(state) > 64):
                    raise ValueError("invalid matter")
                result.append({"case_id": case_id, "case_revision": revision, "state": state})
            return result
        except (ValueError, TypeError, KeyError):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
