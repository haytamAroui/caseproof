"""Read-only MCP adapter contract: closed tools, no identity arguments, no writes."""
import io
import json
from functools import lru_cache

import pytest
from docx import Document

from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.mcp_adapter_contract import McpContractError, call_tool, list_tools


@lru_cache(maxsize=1)
def _docx() -> bytes:
    document = Document()
    document.add_paragraph("Zie Stuk 1 voor de betaling.")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


class FakeStore:
    def __init__(self, *, deny: bool = False) -> None:
        self.deny = deny
        self.bearers: list[str] = []

    def _gate(self, bearer: str) -> None:
        self.bearers.append(bearer)
        if self.deny:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)

    def reopen(self, bearer, case_id, brief_id, snapshot):
        self._gate(bearer)
        return ({"schema": "caseproof-dossier-v1", "snapshot_hash": "a" * 64, "findings": []}, b"")

    def rpc(self, bearer, case_id, action, data):
        self._gate(bearer)
        return {"decisions": []}

    def original_docx(self, *, bearer, case_id, brief_id):
        self._gate(bearer)
        return _docx()

    def manifest(self, *, bearer, case_id):
        self._gate(bearer)
        return []

    def record(self, **kwargs):
        raise AssertionError("the MCP adapter must never record decisions")

    def decisions(self, *, bearer, case_id, brief_id, snapshot_hash):
        self._gate(bearer)
        return [{"reference_id": "ref-0000", "decision": "CONFIRMED_QUALIFIED",
                 "rationale": "checked"}]


ARGS = {"snapshot_hash": "a" * 64, "case_id": "case-a", "brief_id": "brief-1"}


def test_only_two_read_only_tools_without_identity_or_write_surface():
    tools = list_tools()
    assert {t["name"] for t in tools} == {
        "caseproof_discover_references", "caseproof_export_report"}
    for tool in tools:
        schema = tool["inputSchema"]
        assert schema["additionalProperties"] is False
        assert tool["annotations"]["readOnlyHint"] is True
        assert not {"bearer", "token", "tenant_id", "organization_id", "user_id",
                    "decision", "rationale"} & set(schema["properties"])


@pytest.mark.parametrize("extra", ["bearer", "tenant_id", "organization_id", "decision"])
def test_identity_or_write_arguments_are_rejected_before_any_access(extra):
    store = FakeStore()
    with pytest.raises(McpContractError):
        call_tool(allow_document_content=True, release=release(), destination="synthetic-test-host", store=store, bearer="host-token",
                  name="caseproof_discover_references", arguments={**ARGS, extra: "x"})
    assert store.bearers == []


@pytest.mark.parametrize("name", [
    "caseproof_record_review_decision", "record", "", "caseproof_delete_matter"])
def test_unknown_or_write_tool_names_are_rejected(name):
    with pytest.raises(McpContractError):
        call_tool(allow_document_content=True, release=release(), destination="synthetic-test-host", store=FakeStore(), bearer="host-token", name=name, arguments=ARGS)


@pytest.mark.parametrize("arguments", [
    None, [], {}, {"case_id": "case-a"}, {"case_id": "../x", "brief_id": "b"},
    {"case_id": 1, "brief_id": "b"}, {"case_id": "a" * 101, "brief_id": "b"},
])
def test_malformed_arguments_are_rejected(arguments):
    with pytest.raises(McpContractError):
        call_tool(allow_document_content=True, release=release(), destination="synthetic-test-host", store=FakeStore(), bearer="host-token",
                  name="caseproof_discover_references", arguments=arguments)


def test_blank_host_bearer_is_rejected():
    with pytest.raises(McpContractError):
        call_tool(allow_document_content=True, release=release(), destination="synthetic-test-host", store=FakeStore(), bearer="  ",
                  name="caseproof_discover_references", arguments=ARGS)


def test_discovery_uses_canonical_signed_dossier():
    from unittest.mock import Mock
    store = Mock()
    report = {"schema": "caseproof-dossier-v1", "snapshot_hash": "a" * 64,
              "findings": [{"identity": "not_assessed", "page_mapping": "page_unmapped"}]}
    store.reopen.return_value = (report, b"")
    result = call_tool(allow_document_content=True, release=release(), destination="synthetic-test-host", store=store, bearer="host-token",
                       name="caseproof_discover_references", arguments=ARGS)
    assert result["structuredContent"] == report
    assert result["canonical_verification"] is True
    store.reopen.assert_called_once_with("host-token", "case-a", "brief-1", "a" * 64)


def test_export_json_uses_canonical_report_and_decisions():
    from unittest.mock import Mock
    store = Mock()
    report = {"schema": "caseproof-dossier-v1", "snapshot_hash": "a" * 64, "findings": []}
    store.reopen.return_value = (report, b"")
    store.rpc.return_value = {"decisions": []}
    result = call_tool(allow_document_content=True, release=release(), destination="synthetic-test-host", store=store, bearer="host-token",
                       name="caseproof_export_report", arguments=ARGS)
    assert json.loads(result["content"]) == {**report, "human_decisions": []}


def test_invalid_format_is_rejected():
    with pytest.raises(McpContractError):
        call_tool(allow_document_content=True, release=release(), destination="synthetic-test-host", store=FakeStore(), bearer="host-token",
                  name="caseproof_export_report", arguments={**ARGS, "format": "docx"})


def test_access_failure_returns_an_opaque_error_without_details():
    for name in ("caseproof_discover_references", "caseproof_export_report"):
        result = call_tool(allow_document_content=True, release=release(), destination="synthetic-test-host", store=FakeStore(deny=True), bearer="host-token",
                           name=name, arguments=ARGS)
        assert result == {"isError": True, "error": "access_rejected"}


def test_missing_store_fails_closed():
    result = call_tool(allow_document_content=True, release=release(), destination="synthetic-test-host", store=None, bearer="host-token",
                       name="caseproof_discover_references", arguments=ARGS)
    assert result == {"isError": True, "error": "access_rejected"}


@pytest.mark.parametrize("name", ["caseproof_discover_references", "caseproof_export_report"])
def test_content_release_defaults_denied_before_store_access(name):
    store = FakeStore()
    result = call_tool(store=store, bearer="host-token", name=name, arguments=ARGS)
    assert result == {"isError": True, "error": "content_release_not_authorized"}
    assert store.bearers == []


def test_model_cannot_authorize_content_release():
    store = FakeStore()
    with pytest.raises(McpContractError):
        call_tool(store=store, bearer="host-token", name="caseproof_discover_references",
                  arguments={**ARGS, "allow_document_content": True})
    assert store.bearers == []


def test_content_release_is_a_strict_host_boolean():
    with pytest.raises(McpContractError):
        call_tool(store=FakeStore(), bearer="host-token", name="caseproof_discover_references",
                  arguments=ARGS, allow_document_content="yes")


def test_tool_listing_cannot_mutate_closed_dispatch_contract():
    listing = list_tools()
    listing[0]["inputSchema"]["properties"]["bearer"] = {"type": "string"}
    listing[0]["inputSchema"]["properties"]["case_id"]["pattern"] = ".*"
    fresh = list_tools()[0]["inputSchema"]["properties"]
    assert "bearer" not in fresh
    assert fresh["case_id"]["pattern"] != ".*"
    with pytest.raises(McpContractError):
        call_tool(store=FakeStore(), bearer="host-token", name="caseproof_discover_references",
                  arguments={**ARGS, "bearer": "model-token"}, allow_document_content=True, release=release(), destination="synthetic-test-host")


def test_signed_store_parity_for_discovery_and_export():
    store = FakeStore()
    expected, _ = store.reopen("host-token", "case-a", "brief-1", "a" * 64)
    discovery = call_tool(store=store, bearer="host-token",
                          name="caseproof_discover_references", arguments=ARGS,
                          allow_document_content=True, release=release(), destination="synthetic-test-host")
    assert discovery["structuredContent"] == expected
    exported = call_tool(store=store, bearer="host-token",
                         name="caseproof_export_report", arguments=ARGS,
                         allow_document_content=True, release=release(), destination="synthetic-test-host")
    assert json.loads(exported["content"])["findings"] == expected["findings"]


def test_legacy_mcp_tools_are_not_advertised_as_canonical():
    tools = list_tools()
    discovery = next(tool for tool in tools if tool["name"] == "caseproof_discover_references")
    assert "canonical" in discovery["description"].lower()


def release():
    from datetime import UTC, datetime, timedelta
    from hashlib import sha256

    from application.litigation.content_release import ContentRelease
    return ContentRelease(ARGS["case_id"], ARGS["brief_id"], ARGS["snapshot_hash"],
                          "synthetic-test-host", sha256(BEARER.encode()).hexdigest(),
                          datetime.now(UTC) + timedelta(seconds=60))

BEARER = 'host-token'
