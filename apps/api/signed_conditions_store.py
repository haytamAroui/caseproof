"""Conditions store over two proposed signed RPCs (migration NOT applied, not run against PostgREST).

Targets db/proposals/SIGNED_matter_conditions.sql: public.caseproof_append_conditions (security definer,
re-hashes, compare-and-swap) and public.caseproof_read_conditions (security invoker, RLS decides visibility).
Every response is validated here as untrusted: shape, revision type, hash of the returned text. A conflict is
data returned by the RPC; a denial or malformed answer is an error, never an empty result.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from typing import Any

from apps.api.signed_workbench_routes import ConflictError

__all__ = ["SupabaseConditionsStore"]

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_MAX_TEXT = 200_000
_STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")


class SupabaseConditionsStore:
    """Process-wide, stateless: the verified bearer is passed on every call and nothing is cached."""

    def __init__(self, *, call_rpc: Callable[..., Any], publishable_key: str) -> None:
        if not callable(call_rpc) or not isinstance(publishable_key, str) or not publishable_key:
            raise ValueError("invalid conditions store composition")
        self._rpc = call_rpc
        self._key = publishable_key

    def _call(self, name: str, args: dict[str, Any], bearer: str) -> dict[str, Any]:
        result = self._rpc(publishable_key=self._key, bearer=bearer, name=name, args=args)
        if not isinstance(result, dict):
            raise ValueError("untrusted conditions response")
        return result

    @staticmethod
    def _revision(value: object) -> int:
        if type(value) is not int or not 0 <= value <= 100_000:
            raise ValueError("untrusted conditions revision")
        return value

    def read(self, bearer: str, case_id: str) -> dict[str, Any] | None:
        if not _UUID.fullmatch(case_id):
            raise ValueError("invalid matter id")
        got = self._call("caseproof_read_conditions", {"p_case": case_id}, bearer)
        revision = self._revision(got.get("revision"))
        if revision == 0:
            return None
        text, sha = got.get("spec_text"), got.get("spec_sha256")
        if (type(text) is not str or not 2 <= len(text) <= _MAX_TEXT or type(sha) is not str
                or not _SHA.fullmatch(sha) or hashlib.sha256(text.encode()).hexdigest() != sha):
            raise ValueError("untrusted conditions text")
        return {"revision": revision, "spec_text": text, "spec_sha256": sha,
                "events": self._events(got.get("history"), revision, sha)}

    @staticmethod
    def _events(history: object, revision: int, head_sha: str) -> list[dict[str, Any]] | None:
        """Recorded who/when per revision. Absent (older RPC) is None = unavailable, never invented."""
        if history is None:
            return None
        if not isinstance(history, list) or len(history) != revision:
            raise ValueError("untrusted conditions history")
        out = []
        for n, h in enumerate(history, start=1):
            if (not isinstance(h, dict) or set(h) != {"revision", "spec_sha256", "actor_id", "recorded_at"}
                    or h["revision"] != n or type(h["revision"]) is not int
                    or type(h["spec_sha256"]) is not str or not _SHA.fullmatch(h["spec_sha256"])
                    or type(h["actor_id"]) is not str or not _UUID.fullmatch(h["actor_id"])
                    or type(h["recorded_at"]) is not str or not _STAMP.fullmatch(h["recorded_at"])):
                raise ValueError("untrusted conditions history")
            out.append(dict(h))
        if out[-1]["spec_sha256"] != head_sha:
            raise ValueError("untrusted conditions history")
        return out

    def append(self, bearer: str, case_id: str, expected: int, text: str, sha: str) -> int:
        if not _UUID.fullmatch(case_id) or not _SHA.fullmatch(sha) or type(expected) is not int:
            raise ValueError("invalid conditions append")
        if hashlib.sha256(text.encode()).hexdigest() != sha:
            raise ValueError("spec hash does not match its text")
        got = self._call("caseproof_append_conditions", {
            "p_case": case_id, "p_expected": expected, "p_spec_text": text, "p_sha": sha}, bearer)
        if got.get("conflict") is True:
            raise ConflictError
        revision = self._revision(got.get("revision"))
        if revision != expected + 1 or got.get("spec_sha256") != sha:
            raise ValueError("untrusted conditions append receipt")
        return revision
