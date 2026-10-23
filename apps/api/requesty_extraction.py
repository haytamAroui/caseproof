"""Requesty-only HTTP adapter. No SDK, tools, redirects, retries or fallback."""

from __future__ import annotations

import os
import re
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from application.extraction.contracts import (
    MAX_RESPONSE_BYTES,
    ExtractionError,
    OutcomeUnknown,
    ProviderRejected,
    ProviderReply,
    canonical,
    decode,
    text,
)

ENDPOINT = "https://router.eu.requesty.ai/v1/chat/completions"


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        raise ProviderRejected("Requesty redirect refused")


class RequestyProvider:
    identity = "requesty-eu-http-v1"

    def __init__(self, *, api_key: str, model: str, timeout: int = 60) -> None:
        self.model = text(model, limit=200)
        # Concrete routing only. No dynamic policies or alternate provider clients.
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.:@/-]+", model) or model.startswith("policy/"):
            raise ExtractionError("explicit concrete Requesty model required")
        if model.split("/", 1)[0].lower() == "vertex":
            raise ExtractionError("unsupported Requesty model route")
        if not api_key or any(c.isspace() for c in api_key):
            raise ExtractionError("Requesty API key required")
        if type(timeout) is not int or not 1 <= timeout <= 120:
            raise ExtractionError("bounded timeout required")
        self._api_key = api_key
        self._timeout = timeout

    @classmethod
    def from_environment(cls) -> RequestyProvider:
        return cls(
            api_key=os.environ.get("CASEPROOF_REQUESTY_API_KEY", os.environ.get("REQUESTY_API_KEY", "")),
            model=os.environ.get("CASEPROOF_EXTRACTION_MODEL", os.environ.get("REQUESTY_MODEL_PAID", "")),
        )

    def complete(self, system: str, payload: str, *, request_id: str, max_tokens: int) -> ProviderReply:
        if not re.fullmatch(r"[a-f0-9]{64}", request_id):
            raise ExtractionError("opaque request fingerprint required")
        if type(max_tokens) is not int or not 1 <= max_tokens <= 8192:
            raise ExtractionError("bounded output budget required")
        body = canonical(
            {
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": payload}],
                "max_tokens": max_tokens,
                "stream": False,
                "response_format": {"type": "json_object"},
            }
        ).encode()
        req = Request(
            ENDPOINT,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "X-Title": "CaseProof Evidence Intelligence",
                "X-Request-ID": request_id,
            },
        )
        try:
            # Ignore ambient proxy settings; never forward bearer credentials on redirects.
            from urllib.request import ProxyHandler

            with build_opener(ProxyHandler({}), _NoRedirect()).open(req, timeout=self._timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            if 400 <= exc.code < 500:
                raise ProviderRejected("Requesty rejected the request") from None
            raise OutcomeUnknown("Requesty response outcome requires reconciliation") from None
        except (URLError, TimeoutError, OSError):
            raise OutcomeUnknown("Requesty transport outcome unknown; do not retry automatically") from None
        try:
            result = decode(raw.decode("utf-8"))
            choices = result["choices"]
            if not isinstance(choices, list) or len(choices) != 1 or choices[0]["finish_reason"] != "stop":
                raise ExtractionError("incomplete Requesty completion")
            if result.get("model") != self.model:
                raise ExtractionError("unexpected Requesty model identity")
            message = choices[0]["message"]
            if message.get("tool_calls") or message.get("function_call") or message.get("refusal"):
                raise ExtractionError("non-extraction response")
            content = text(message["content"], limit=MAX_RESPONSE_BYTES)
            usage = result.get("usage", {})
            counts = [usage.get(k) for k in ("prompt_tokens", "completion_tokens")]
            if any(v is not None and (type(v) is not int or v < 0) for v in counts):
                raise ExtractionError("invalid token telemetry")
            if counts[1] is not None and counts[1] > max_tokens:
                raise ExtractionError("provider output budget exceeded")
            cost = usage.get("cost")
            amount = Decimal(str(cost)) if cost is not None else None
            if amount is not None and (not amount.is_finite() or amount < 0):
                raise ExtractionError("invalid cost telemetry")
            return ProviderReply(
                content,
                self.identity,
                self.model,
                counts[0],
                counts[1],
                str(amount) if amount is not None else None,
            )
        except (KeyError, TypeError, IndexError, UnicodeError, InvalidOperation) as exc:
            raise ExtractionError("invalid Requesty response envelope") from exc
