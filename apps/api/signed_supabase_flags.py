"""Append-only human-reported passage flags, no automatic discovery claim."""
from __future__ import annotations

import json
from typing import Any

from apps.api.signed_supabase_facts import FactRefused, LiveMatterFacts, _uuid


class LivePassageFlags(LiveMatterFacts):
    def record(self, *, case_id: str, request_id: str, flag: dict[str, Any]) -> bool:
        result = self._call("caseproof_signed_passage_flag", {
            "p_case": _uuid(case_id), "p_request": _uuid(request_id),
            "p_flag": json.dumps(flag, ensure_ascii=False, sort_keys=True)})
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise FactRefused("passage flag refused")
        return result.get("replay") is False

    def list(self, *, case_id: str) -> tuple[dict[str, Any], ...]:
        result = self._call("caseproof_signed_passage_flags", {"p_case": _uuid(case_id)})
        if not isinstance(result, list) or len(result) > 512:
            raise FactRefused("malformed flag list")
        if any(not isinstance(r, dict) or not all(k in r for k in (
            "id", "actor_id", "brief_version_id", "source_document_id", "source_version_id",
            "source_sha256", "draft_passage", "source_passage", "source_start", "rationale", "recorded_at")) for r in result):
            raise FactRefused("malformed passage flag")
        return tuple(result)
