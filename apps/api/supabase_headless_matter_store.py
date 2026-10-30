"""Signed, source-version-pinned DOCX and bundle reader for headless verification.

All source reads use the caller's JWT, the existing invoker-view metadata,
private Storage and the signed Phase 3 bundle manifest. No service key.
Review writes are deliberately unavailable until the reviewed DB RPC is installed.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.litigation_live_journey import JourneyClient
from apps.api.signed_supabase_originals import PrivateStorageFailure


class SupabaseHeadlessMatterStore:
    def __init__(self, publishable_key: str):
        self.client = JourneyClient(publishable_key)

    def _bundle(self, *, bearer: str, case_id: str) -> list[dict[str, Any]]:
        try:
            UUID(case_id)
            data = self.client.bundle_manifest(bearer, case_id)
            sources = data["sources"]
            if len(sources) != 4 or not all(
                isinstance(item, dict) and item.get("role") in {"draft", "inventory", "exhibit"}
                for item in sources
            ):
                raise ValueError("incomplete bundle")
            return sources
        except (ValueError, KeyError, TypeError):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None

    def original_docx(self, *, bearer: str, case_id: str, brief_id: str) -> bytes:
        sources = self._bundle(bearer=bearer, case_id=case_id)
        drafts = [s for s in sources if s["role"] == "draft" and s["version_id"] == brief_id
                  and s["media_type"] ==
                  "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
        if len(drafts) != 1:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        draft = drafts[0]
        try:
            return self.client.library.read(
                bearer=bearer, case_id=case_id,
                document_id=draft["document_id"], version_id=draft["version_id"],
            )
        except PrivateStorageFailure:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None

    def manifest(self, *, bearer: str, case_id: str) -> list[dict[str, Any]]:
        # Phase 3 manifests identify source versions, not exhibit numbers.
        # Do not infer legal exhibit identity from filenames or upload order.
        return [
            {"role": s["role"], "source_id": s["document_id"],
             "version_id": s["version_id"], "filename": s["filename"]}
            for s in self._bundle(bearer=bearer, case_id=case_id)
        ]

    def record(self, *, bearer: str, case_id: str, brief_id: str,
               reference_id: str, snapshot_hash: str, request_id: UUID,
               decision: str, rationale: str) -> dict[str, Any]:
        # Never claim a decision was persisted without a signed durable RPC.
        raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)

    def decisions(self, *, bearer: str, case_id: str, brief_id: str,
                  snapshot_hash: str) -> list[dict[str, Any]]:
        raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
