"""Stateless, read-only CaseProof hosted MCP resource-server composition.

No route is mounted into the existing development API. A deployment must inject
current signed-dossier storage, an OAuth verifier and a *live* host consent gate.
This adapter is not an authorization server and does not create consent grants.
2026-07-28 transport: no initialize handshake, GET stream or MCP sessions.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from application.litigation.content_release import ContentRelease
from apps.api.hosted_mcp_oauth_boundary import (
    OAuthBoundaryRejected,
    VerifiedOAuthClaims,
    authorize_verified_claims,
)
from apps.api.mcp_adapter_contract import McpContractError, call_canonical_tool, list_tools, validate_tool_call
from apps.api.dossier_journey import DossierStore
from apps.api.access_control import AccessRejected, IdentityServiceUnavailable, InvalidBearer

PROTOCOL = "2026-07-28"
SCOPE = "caseproof:reports:read"
MAX_REQUEST = 16_384
META_VERSION = "io.modelcontextprotocol/protocolVersion"
META_CAPABILITIES = "io.modelcontextprotocol/clientCapabilities"
DESTINATION = re.compile(r"^[a-zA-Z0-9_./:-]{1,128}$")


class OAuthBearerVerifier(Protocol):
    def verify(self, token: str) -> VerifiedOAuthClaims: ...


class HostContentGate(Protocol):
    def resolve(self, *, subject: str, bearer: str, destination: str,
                case_id: str, brief_id: str, snapshot_hash: str) -> ContentRelease | None:
        """Live, revocable, per-call decision from trusted host; no model consent."""


@dataclass(frozen=True, slots=True)
class HostedMcpSettings:
    resource: str
    issuer: str
    allowed_origins: frozenset[str]
    destination: str

    def __post_init__(self) -> None:
        for value in (self.resource, self.issuer):
            parsed = urlsplit(value)
            if (parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password
                    or parsed.query or parsed.fragment):
                raise ValueError("Pinned public HTTPS OAuth resource and issuer required")
        if not DESTINATION.fullmatch(self.destination):
            raise ValueError("Explicit, pinned MCP disclosure destination required")
        if not self.allowed_origins or any(
            urlsplit(o).scheme != "https" or not urlsplit(o).netloc or
            urlsplit(o).path not in ("", "/") or urlsplit(o).query or urlsplit(o).fragment
            for o in self.allowed_origins
        ):
            raise ValueError("Explicit HTTPS browser origin allowlist required")


def create_hosted_mcp_app(
    *, settings: HostedMcpSettings,
    verifier: OAuthBearerVerifier,
    releases: HostContentGate,
    store: DossierStore | None,
    clock: Callable[[], int],
) -> FastAPI:
    """Operational HTTP composition, fail-closed until real host policies exist.

    Neither the OAuth client identity nor its destination is inferred from
    model-controlled tool arguments or forwarded/proxy headers.
    """
    app = FastAPI(title="CaseProof read-only MCP", docs_url=None, redoc_url=None,
                  openapi_url=None)
    # The discovery URL must be rooted at the same externally pinned origin.
    url = urlsplit(settings.resource)
    resource_metadata = f"{url.scheme}://{url.netloc}/.well-known/oauth-protected-resource"
    challenge = f'Bearer resource_metadata="{resource_metadata}", scope="{SCOPE}"'

    def reply(data: dict[str, Any], status: int = 200,
              *, challenge_required: bool = False) -> JSONResponse:
        headers = {"Cache-Control": "no-store", "Pragma": "no-cache",
                   "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}
        if challenge_required:
            headers["WWW-Authenticate"] = challenge
        return JSONResponse(data, status_code=status, headers=headers)

    def fault(code: int, message: str, id_value: str | int | None = None,
              status: int = 400) -> JSONResponse:
        return reply({"jsonrpc": "2.0", "id": id_value,
                      "error": {"code": code, "message": message}}, status)

    @app.get("/.well-known/oauth-protected-resource")
    def metadata() -> JSONResponse:
        return reply({"resource": settings.resource, "authorization_servers": [settings.issuer],
                      "bearer_methods_supported": ["header"], "scopes_supported": [SCOPE],
                      "resource_name": "CaseProof frozen, reviewed dossier reports"})

    @app.get("/mcp")
    def no_get() -> Response:
        return Response(status_code=405, headers={"Allow": "POST", "Cache-Control": "no-store"})

    @app.post("/mcp")
    async def mcp(request: Request) -> JSONResponse:
        origin = request.headers.get("origin")
        if origin is not None and origin not in settings.allowed_origins:
            return fault(-32600, "Origin denied", status=403)
        if request.query_params or request.cookies or request.headers.get("mcp-session-id"):
            return fault(-32600, "Unsupported credentials or session", status=400)
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer ") or len(auth) > 8200:
            return reply({"error": "unauthorized"}, 401, challenge_required=True)
        token = auth[7:]
        if not token or token.strip() != token:
            return reply({"error": "unauthorized"}, 401, challenge_required=True)
        try:
            claims = verifier.verify(token)
            bearer = authorize_verified_claims(
                claims, expected_issuer=settings.issuer, resource_audience=settings.resource,
                now=clock(), required_scope=SCOPE)
            if bearer != token:
                raise OAuthBoundaryRejected("bearer identity mismatch")
        except (OAuthBoundaryRejected, InvalidBearer, IdentityServiceUnavailable,
                ValueError, TypeError, OSError):
            return reply({"error": "unauthorized"}, 401, challenge_required=True)
        # Access tokens are never echoed, added to telemetry, or accepted from JSON arguments.
        if "application/json" not in request.headers.get("content-type", "").split(";")[0]:
            return fault(-32600, "JSON required", status=415)
        accept = request.headers.get("accept", "")
        if "application/json" not in accept or "text/event-stream" not in accept:
            return fault(-32600, "Streamable HTTP accept required", status=406)
        if request.headers.get("content-length", "").isdigit() and int(request.headers["content-length"]) > MAX_REQUEST:
            return fault(-32600, "Request too large", status=413)
        raw = await request.body()
        if len(raw) > MAX_REQUEST:
            return fault(-32600, "Request too large", status=413)
        try:
            body = json.loads(raw)
        except (UnicodeError, ValueError):
            return fault(-32700, "Parse error")
        if type(body) is not dict or set(body) - {"jsonrpc", "id", "method", "params"}:
            return fault(-32600, "Single JSON-RPC request required")
        ident = body.get("id")
        if type(ident) not in (int, str) or type(ident) is str and len(ident) > 100:
            return fault(-32600, "Request ID required")
        if body.get("jsonrpc") != "2.0" or type(body.get("method")) is not str:
            return fault(-32600, "Invalid JSON-RPC", ident)
        params = body.get("params", {})
        if type(params) is not dict:
            return fault(-32602, "Invalid params", ident)
        meta = params.get("_meta")
        if type(meta) is not dict or meta.get(META_VERSION) != PROTOCOL or type(meta.get(META_CAPABILITIES)) is not dict:
            return fault(-32020, "HeaderMismatch: request metadata", ident)
        if request.headers.get("mcp-protocol-version") != PROTOCOL:
            return fault(-32022, "UnsupportedProtocolVersion: 2026-07-28", ident)
        method = body["method"]
        if request.headers.get("mcp-method") != method:
            return fault(-32020, "HeaderMismatch: method", ident)
        if method in ("tools/call",) and (type(params.get("name")) is not str or
                                          request.headers.get("mcp-name") != params["name"]):
            return fault(-32020, "HeaderMismatch: name", ident)
        if method != "tools/call" and request.headers.get("mcp-name") is not None:
            return fault(-32020, "HeaderMismatch: unexpected name", ident)
        if method == "server/discover":
            result: dict[str, Any] = {"resultType": "complete", "protocolVersions": [PROTOCOL],
                                     "serverInfo": {"name": "caseproof", "version": "1.0.0"},
                                     "capabilities": {"tools": {}}}
        elif method == "tools/list":
            result = {"resultType": "complete", "tools": list_tools(), "ttlMs": 0,
                      "cacheScope": "private"}
        elif method == "tools/call":
            # No client-supplied identity, release, consent, OAuth scope or destination.
            if set(params) - {"name", "arguments", "_meta"}:
                return fault(-32602, "Unknown tool parameters", ident)
            try:
                args = validate_tool_call(params["name"], params.get("arguments"))
                case = args["case_id"]
                brief = args["brief_id"]
                snapshot = args["snapshot_hash"]
                # The gate must perform an up-to-date revocation/approval check;
                # no blanket server-wide True option or stale long-lived grant.
                release = releases.resolve(subject=claims.subject, bearer=bearer,
                                           destination=settings.destination, case_id=case,
                                           brief_id=brief, snapshot_hash=snapshot)
                output = call_canonical_tool(store=store, bearer=bearer, name=params["name"],
                                             arguments=args, release=release,
                                             destination=settings.destination)
            except (McpContractError, KeyError, ValueError, TypeError):
                return fault(-32602, "Invalid tool arguments", ident)
            except (AccessRejected, OSError):
                output = {"isError": True, "error": "access_rejected"}
            if output.get("isError"):
                result = {"resultType": "complete", "isError": True,
                          "content": [{"type": "text", "text": str(output.get("error", "access_rejected"))}]}
            else:
                payload = output.get("structuredContent", output.get("content"))
                result = {"resultType": "complete", "isError": False,
                          "content": [{"type": "text", "text": (
                              payload if type(payload) is str else
                              json.dumps(payload, sort_keys=True, ensure_ascii=False))}]}
                if "structuredContent" in output:
                    result["structuredContent"] = output["structuredContent"]
        else:
            return fault(-32601, "Method not found", ident)
        return reply({"jsonrpc": "2.0", "id": ident, "result": result})

    return app
