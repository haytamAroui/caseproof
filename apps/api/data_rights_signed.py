"""Signed, read-only PostgREST projection for rights shadow observation.

Only sanitized decision inputs are returned. No service key, direct private table
grants, bearer logging or policy mutation. Call after existing source authorization.
"""
from __future__ import annotations

import http.client
import json
from dataclasses import dataclass
from uuid import UUID

from application.data_rights import RightsPolicy
from apps.api.signed_supabase_source_library import PROJECT_HOST

MAX_RESPONSE = 4096


class ShadowLookupUnavailable(Exception):
    """Observation was unavailable; must never affect the original response."""


def _canonical_uuid(value: str) -> str:
    try:
        if str(UUID(value)) != value or UUID(value).int == 0:
            raise ValueError
    except (TypeError, ValueError, AttributeError) as exc:
        raise ShadowLookupUnavailable("Invalid source identifier") from exc
    return value


@dataclass(frozen=True, slots=True)
class SignedRightsPolicyReader:
    publishable_key: str
    timeout_seconds: float = 3.0

    def __post_init__(self) -> None:
        if not self.publishable_key.startswith("sb_publishable_") or not 0.1 <= self.timeout_seconds <= 10:
            raise ValueError("Invalid rights shadow transport")

    def read(
        self, *, bearer: str, case_id: str, document_id: str, version_id: str,
    ) -> RightsPolicy | None:
        if not isinstance(bearer, str) or not 0 < len(bearer) <= 8192 or "\r" in bearer or "\n" in bearer:
            raise ShadowLookupUnavailable("Invalid signed identity")
        body = json.dumps(
            {"p_case": _canonical_uuid(case_id), "p_document": _canonical_uuid(document_id),
             "p_version": _canonical_uuid(version_id)},
            separators=(",", ":"),
        ).encode("utf-8")
        conn = http.client.HTTPSConnection(PROJECT_HOST, timeout=self.timeout_seconds)
        try:
            conn.request(
                "POST", "/rest/v1/rpc/caseproof_rights_current", body=body,
                headers={
                    "apikey": self.publishable_key,
                    "Authorization": "Bearer " + bearer,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Cache-Control": "no-store",
                },
            )
            response = conn.getresponse()
            status, raw = response.status, response.read(MAX_RESPONSE + 1)
        except (OSError, TimeoutError, http.client.HTTPException) as exc:
            raise ShadowLookupUnavailable("Policy lookup unavailable") from exc
        finally:
            conn.close()
        if status != 200 or len(raw) > MAX_RESPONSE:
            raise ShadowLookupUnavailable("Policy lookup not confirmed")
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise ShadowLookupUnavailable("Malformed shadow projection") from exc
        if not isinstance(data, dict):
            raise ShadowLookupUnavailable("Malformed shadow projection")
        if data.get("policy_status") == "missing" and set(data) == {"policy_status"}:
            return None
        if data.get("policy_status") != "present":
            raise ShadowLookupUnavailable("Unknown shadow policy state")
        version = data.get("policy_version")
        if type(version) is not int or version < 1:
            raise ShadowLookupUnavailable("Malformed policy version")
        if data.get("origin") != "CLIENT_UPLOAD" or data.get("classification") != "CLIENT_CONFIDENTIAL":
            raise ShadowLookupUnavailable("Unsupported classification")
        authorization_present = data.get("authorization_reference_present")
        if type(authorization_present) is not bool:
            raise ShadowLookupUnavailable("Malformed authorization flag")
        permissions = {}
        for field in ("process", "indexForSearch", "useAcrossMatters", "export"):
            value = data.get(field)
            if type(value) is not bool:
                raise ShadowLookupUnavailable("Malformed permission")
            permissions[field] = value
        return RightsPolicy(
            version=version,
            authorization_reference="recorded" if authorization_present else None,
            permissions=permissions,
            classification=data["classification"],
            origin=data["origin"],
        )
