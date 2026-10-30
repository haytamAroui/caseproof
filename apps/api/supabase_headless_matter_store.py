"""Signed, source-version-pinned DOCX and bundle reader for headless verification.

All source reads use the caller's JWT, the existing invoker-view metadata,
private Storage and the signed Phase 3 bundle manifest. No service key.
Review writes are deliberately unavailable until the reviewed DB RPC is installed.
"""
from __future__ import annotations

import http.client
import json
import re
from typing import Any
from uuid import UUID

from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.litigation_live_journey import HOST, JourneyClient
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
        sources = self._bundle(bearer=bearer, case_id=case_id)
        inventories = [s for s in sources if s["role"] == "inventory"]
        exhibits = [s for s in sources if s["role"] == "exhibit"]
        if len(inventories) != 1 or len(exhibits) != 2:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        inventory = inventories[0]
        try:
            original = self.client.library.read(
                bearer=bearer, case_id=case_id,
                document_id=inventory["document_id"], version_id=inventory["version_id"],
            )
            text = original.decode("utf-8", errors="strict")
        except (PrivateStorageFailure, UnicodeError):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
        # Inventory is authoritative for numbering, but filename matching
        # cannot be trusted as legal identity. Keep ambiguous sources unresolved.
        mentions = re.findall(
            r"(?i)\\b(stuk|pi[eè]ce)\\s+(\\d{1,4})\\s+([^;\\n]+)", text,
        )
        results: list[dict[str, Any]] = []
        for label, number, description in mentions:
            candidates = [
                s for s in exhibits
                if all(token in s["filename"].casefold() for token in
                       (("stuk" if label.casefold() == "stuk" else "piece"), number))
            ]
            item: dict[str, Any] = {
                "label": label.casefold(), "number": number,
                "inventory_description": description.strip(),
            }
            if len(candidates) == 1:
                source = candidates[0]
                item.update({
                    "source_id": source["document_id"], "version_id": source["version_id"],
                    "source_sha256": source["sha256"],
                })
                # Only use persisted, integrity-verified OCR geometry; a missing
                # sidecar never creates fabricated coordinates.
                if label.casefold() != "stuk":
                    try:
                        _, geometry = self.client.read_geometry(
                            bearer, source["version_id"], 1,
                        )
                        words = geometry["words"]
                        expected = {"piece", "pièce", number, *re.findall(r"[a-z]{4,}", description.casefold())}
                        matches = [
                            w for w in words if isinstance(w, dict)
                            and str(w.get("text", "")).casefold().strip(".,:") in expected
                        ]
                        if matches:
                            w = matches[0]
                            if all(type(w.get(k)) is int for k in
                                   ("left", "top", "width", "height")):
                                item["ocr_crop"] = {
                                    "page_number": 1,
                                    "left": w["left"], "top": w["top"],
                                    "width": w["width"], "height": w["height"],
                                    "coordinate_basis": geometry["coordinate_basis"],
                                    "geometry_sha256": self.client.read_geometry(
                                        bearer, source["version_id"], 1,
                                    )[0].geometry_sha256,
                                }
                                item["ocr_uncertainty"] = "requires_human_confirmation"
                    except AccessRejected:
                        pass
            results.append(item)
        return results

    def _review_rpc(self, bearer: str, case_id: str, brief_id: str,
                    snapshot_hash: str, action: str, **fields: object) -> dict[str, Any]:
        if action not in ("record", "list"):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        # The SQL RPC derives actor identity from auth.uid() and verifies
        # current organization membership, matter grant and draft identity.
        body = {"p_case": case_id, "p_brief": brief_id,
                "p_snapshot": snapshot_hash, "p_action": action, **fields}
        con = http.client.HTTPSConnection(HOST, timeout=15)
        try:
            con.request(
                "POST", "/rest/v1/rpc/caseproof_phase4_review",
                json.dumps(body, separators=(",", ":")).encode("utf-8"),
                {"apikey": self.client._key, "Authorization": "Bearer " + bearer,
                 "Content-Type": "application/json", "Cache-Control": "no-store"},
            )
            response = con.getresponse()
            status, raw = response.status, response.read(262145)
        except (OSError, TimeoutError, http.client.HTTPException):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        finally:
            con.close()
        if status in (400, 401, 403, 404, 409, 422):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        if status != 200 or len(raw) > 262144:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        if not isinstance(result, dict):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return result

    def record(self, *, bearer: str, case_id: str, brief_id: str,
               reference_id: str, snapshot_hash: str, request_id: UUID,
               decision: str, rationale: str) -> dict[str, Any]:
        return self._review_rpc(
            bearer, case_id, brief_id, snapshot_hash, "record",
            p_reference=reference_id, p_request=str(request_id),
            p_decision=decision, p_rationale=rationale,
        )

    def decisions(self, *, bearer: str, case_id: str, brief_id: str,
                  snapshot_hash: str) -> list[dict[str, Any]]:
        response = self._review_rpc(bearer, case_id, brief_id, snapshot_hash, "list")
        rows = response.get("decisions")
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return rows
