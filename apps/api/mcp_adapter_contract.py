"""Read-only MCP adapter contract over the headless verification ports.

Defines tool schemas and a dispatcher only: it starts no server, adds no
dependency and mounts no route. A future MCP host supplies the signed user's
bearer out of band; it is never a tool argument, so a model cannot choose a
tenant, matter grant or identity. Authorization stays in the matter store.

Human review decisions are deliberately not exposed. Recording
CONFIRMED_SUPPORTED, CONFIRMED_QUALIFIED or CONFIRMED_CONTRADICTED is an
authorized human act and must not be reachable from a model.
"""
from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from apps.api.access_control import AccessRejected
from apps.api.dossier_journey import DossierStore

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


_ID_PROPERTY = {"type": "string", "pattern": _ID_PATTERN}

TOOLS: tuple[McpTool, ...] = (
    McpTool(
        "caseproof_discover_references",
        "Canonical signed dossier verification report. "
        "Do not treat inventory absence, fidelity, translation, or page mapping as verified.",
        {"case_id": _ID_PROPERTY, "brief_id": _ID_PROPERTY},
        ("case_id", "brief_id"),
    ),
    McpTool(
        "caseproof_export_report",
        "Export the current verification report with recorded human decisions. "
        "It is not a filing, a legal certificate or proof that any fact is true.",
        {"case_id": _ID_PROPERTY, "brief_id": _ID_PROPERTY,
         "format": {"type": "string", "enum": list(_FORMATS)}},
        ("case_id", "brief_id"),
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
    if "format" in arguments and arguments["format"] not in _FORMATS:
        raise McpContractError("invalid format")
    return dict(arguments)


def call_tool(*, store: DossierStore | None, bearer: str,
                        name: str, arguments: object,
                        allow_document_content: bool = False) -> dict[str, Any]:
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
    if not allow_document_content:
        return {"isError": True, "error": "content_release_not_authorized"}
    if store is None:
        return {"isError": True, "error": "access_rejected"}
    try:
        report, _ = store.load(bearer, args["case_id"], args["brief_id"])
        if report.get("schema") != "caseproof-dossier-v1" or not report.get("snapshot_hash"):
            return {"isError": True, "error": "canonical_report_unavailable"}
        if tool.name == "caseproof_discover_references":
            return {"isError": False, "structuredContent": report,
                    "canonical_verification": True}
        decisions = store.rpc(bearer, args["case_id"], "decisions",
                              {"snapshot_hash": report["snapshot_hash"]})
        if not isinstance(decisions.get("decisions"), list):
            return {"isError": True, "error": "canonical_report_unavailable"}
        exported = {**report, "human_decisions": decisions["decisions"]}
        if args.get("format", "json") == "json":
            import json
            return {"isError": False, "mediaType": "application/json",
                    "content": json.dumps(exported, sort_keys=True, ensure_ascii=False),
                    "canonical_verification": True}
        from apps.api.dossier_journey import canonical
        lines = ["# CaseProof scoped dossier report", "",
                 "Verification contract", canonical(exported.get("verification_contract", {})), "",
                 "Coverage", canonical(exported.get("coverage", {})), "",
                 "Findings", canonical(exported.get("findings", [])), "",
                 "Human decisions", canonical(exported["human_decisions"])]
        return {"isError": False, "mediaType": "text/markdown",
                "content": "\\n".join(lines) + "\\n",
                "canonical_verification": True}
    except AccessRejected:
        return {"isError": True, "error": "access_rejected"}

# Backwards-compatible name; the only supported dispatch is canonical.
call_canonical_tool = call_tool
