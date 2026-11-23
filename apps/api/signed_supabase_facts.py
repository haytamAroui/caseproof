"""Lawyer fact confirmations over the proposed masked fact RPCs.

Per-request adapter bound to one verified bearer. The RPCs own authorization,
the actor (the verified caller), source custody and the source hash. The
record states who entered which value against which source version. It is not
proof that the fact is true and never a legal conclusion.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any
from uuid import UUID

__all__ = ["FactRefused", "LiveMatterFacts"]


class FactRefused(Exception):
    """The fact ledger refused or is unavailable (fail closed)."""


def _uuid(value: object) -> str:
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        raise FactRefused("uuid required") from None
    if parsed.int == 0:
        raise FactRefused("non-nil uuid required")
    return str(parsed)


class LiveMatterFacts:
    def __init__(self, *, call_rpc: Callable[..., Any], publishable_key: str,
                 bearer: str) -> None:
        self._rpc, self._key, self._bearer = call_rpc, publishable_key, bearer

    def _call(self, name: str, args: dict[str, Any]) -> Any:
        try:
            return self._rpc(publishable_key=self._key, bearer=self._bearer,
                             name=name, args=args)
        except Exception:
            raise FactRefused("fact ledger unavailable") from None

    def confirm(self, *, case_id: str, request_id: str, name: str, value: object,
                confirmed: bool, source_document_id: str, source_version_id: str,
                locator: str) -> bool:
        """Append one confirmation; returns True when newly recorded."""
        import json
        if (type(value) not in (bool, int, float, str) or type(confirmed) is not bool
                or (isinstance(value, float) and not math.isfinite(value))):
            raise FactRefused("a fact value is a finite string, number or boolean")
        fact = json.dumps({
            "name": name, "value": value, "confirmed": confirmed,
            "source_document_id": _uuid(source_document_id),
            "source_version_id": _uuid(source_version_id), "locator": locator,
        }, sort_keys=True, ensure_ascii=False)
        result = self._call("caseproof_signed_fact_confirm", {
            "p_case": _uuid(case_id), "p_request": _uuid(request_id), "p_fact": fact})
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise FactRefused("fact ledger refused")
        return result.get("replay") is False

    def list(self, *, case_id: str) -> tuple[dict[str, Any], ...]:
        result = self._call("caseproof_signed_fact_list", {"p_case": _uuid(case_id)})
        if not isinstance(result, list) or len(result) > 512:
            raise FactRefused("malformed fact list")
        rows: list[dict[str, Any]] = []
        for row in result:
            if (not isinstance(row, dict)
                    or not all(k in row for k in (
                        "name", "value", "confirmed", "source_document_id",
                        "source_version_id", "source_sha256", "locator", "actor_id",
                        "recorded_at"))):
                raise FactRefused("malformed fact row")
            rows.append(row)
        return tuple(rows)
