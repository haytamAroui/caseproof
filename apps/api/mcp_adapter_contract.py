"""Read-only MCP adapter contract over frozen canonical dossier reports.

Defines tool schemas and a dispatcher only: it starts no server, adds no
dependency and mounts no route. A future MCP host supplies the signed user's
bearer out of band; it is never a tool argument, so a model cannot choose a
tenant, matter grant or identity. Authorization stays in the matter store.

Human review decisions are deliberately not exposed. Recording
CONFIRMED_SUPPORTED, CONFIRMED_QUALIFIED or CONFIRMED_CONTRADICTED is an
authorized human act and must not be reachable from a model.
"""
from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException

from application.litigation.content_release import ContentRelease, utc_now
from application.litigation.report_projection import render_dossier_export
from apps.api.access_control import AccessRejected
from apps.api.dossier_journey import DossierStore, read_dossier_report

_ID_PATTERN = r"^[A-Za-z0-9_.-]{1,100}$"
_ID_RE = re.compile(_ID_PATTERN)
_FORMATS = ("json", "markdown")


class McpContractError(ValueError):
    """Tool name or arguments violate the closed adapter contract."""


@dataclass(frozen=True, slots=True)
class McpTool:
    name: str
    description: str
    properties: dict[str, dict[str, Any]]
    required: tuple[str, ...]

    def as_listing(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": deepcopy(self.properties),
                "required": list(self.required),
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True, "destructiveHint": False},
        }


_SNAPSHOT_PROPERTY = {"type": "string", "pattern": r"^[0-9a-f]{64}$"}

_ID_PROPERTY = {"type": "string", "pattern": _ID_PATTERN}

TOOLS: tuple[McpTool, ...] = (
    McpTool(
        "caseproof_discover_references",
        "Canonical signed dossier verification report. "
        "Do not treat inventory absence, fidelity, translation, or page mapping as verified.",
        {"case_id": _ID_PROPERTY, "brief_id": _ID_PROPERTY, "snapshot_hash": _SNAPSHOT_PROPERTY},
        ("case_id", "brief_id", "snapshot_hash"),
    ),
    McpTool(
        "caseproof_export_report",
        "Export the current verification report with recorded human decisions. "
        "It is not a filing, a legal certificate or proof that any fact is true.",
        {"case_id": _ID_PROPERTY, "brief_id": _ID_PROPERTY, "snapshot_hash": _SNAPSHOT_PROPERTY,
         "format": {"type": "string", "enum": list(_FORMATS)}},
        ("case_id", "brief_id", "snapshot_hash"),
    ),
)
_BY_NAME = {tool.name: tool for tool in TOOLS}


def list_tools() -> list[dict[str, Any]]:
    return [tool.as_listing() for tool in TOOLS]


def _validated(tool: McpTool, arguments: object) -> dict[str, Any]:
    if type(arguments) is not dict:
        raise McpContractError("arguments must be an object")
    unknown = set(arguments) - set(tool.properties)
    if unknown:
        raise McpContractError("unexpected arguments")
    missing = [name for name in tool.required if name not in arguments]
    if missing:
        raise McpContractError("missing required arguments")
    for name in ("case_id", "brief_id"):
        value = arguments[name]
        if type(value) is not str or not _ID_RE.fullmatch(value):
            raise McpContractError("invalid identifier")
    if type(arguments["snapshot_hash"]) is not str or not re.fullmatch(r"[0-9a-f]{64}", arguments["snapshot_hash"]):
        raise McpContractError("invalid snapshot hash")
    if "format" in arguments and arguments["format"] not in _FORMATS:
        raise McpContractError("invalid format")
    return dict(arguments)


def _dispatch_tool(*, store: DossierStore | None, bearer: str,
                        name: str, arguments: object,
                        allow_document_content: bool = False,
              release: ContentRelease | None = None, destination: str | None = None) -> dict[str, Any]:
    """Read the same signed, hash-bound dossier report used by the REST dossier.

    No headless-v1 fallback is permitted. The host owns identity and release
    consent; tool arguments cannot select either. Review writes are absent.
    """
    tool = _BY_NAME.get(name) if type(name) is str else None
    if tool is None:
        raise McpContractError("unknown tool")
    args = _validated(tool, arguments)
    if type(bearer) is not str or not bearer.strip():
        raise McpContractError("host-authenticated bearer required")
    if type(allow_document_content) is not bool:
        raise McpContractError("typed host content-release decision required")
    if not isinstance(release, ContentRelease) or not release.permits(
            bearer=bearer, case_id=args["case_id"], brief_id=args["brief_id"],
            snapshot_hash=args["snapshot_hash"], destination=destination, now=utc_now()):
        return {"isError": True, "error": "content_release_not_authorized"}
    if store is None:
        return {"isError": True, "error": "access_rejected"}
    try:
        report, _ = read_dossier_report(store, bearer, args["case_id"], args["brief_id"],
                                        args["snapshot_hash"],
                                        decisions=tool.name == "caseproof_export_report")
        if not release.permits(bearer=bearer, case_id=args["case_id"], brief_id=args["brief_id"],
                               snapshot_hash=args["snapshot_hash"], destination=destination, now=utc_now()):
            return {"isError": True, "error": "content_release_not_authorized"}
        if tool.name == "caseproof_discover_references":
            return {"isError": False, "structuredContent": report,
                    "canonical_verification": True}
        fmt = args.get("format", "json")
        content = render_dossier_export(report, fmt)
        if not release.permits(bearer=bearer, case_id=args["case_id"], brief_id=args["brief_id"],
                               snapshot_hash=args["snapshot_hash"], destination=destination, now=utc_now()):
            return {"isError": True, "error": "content_release_not_authorized"}
        return {"isError": False,
                "mediaType": "application/json" if fmt == "json" else "text/markdown",
                "content": content,
                "exportSha256": hashlib.sha256(content.encode()).hexdigest(),
                "canonical_verification": True}
    except HTTPException:
        return {"isError": True, "error": "canonical_report_unavailable"}
    except AccessRejected:
        return {"isError": True, "error": "access_rejected"}

def call_tool(*, store: DossierStore | None, bearer: str, name: str, arguments: object,
              allow_document_content: bool = False, release: ContentRelease | None = None,
              destination: str | None = None) -> dict[str, Any]:
    from infrastructure.telemetry.operations import observe_tool

    return observe_tool(name, lambda: _dispatch_tool(
        store=store, bearer=bearer, name=name, arguments=arguments,
        allow_document_content=allow_document_content, release=release, destination=destination))


# Backwards-compatible name; the only supported dispatch is canonical.
call_canonical_tool = call_tool
