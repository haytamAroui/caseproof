"""Read-only MCP adapter contract: closed tools, no identity arguments, no writes."""
import io
import json

import pytest
from docx import Document

from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.litigation_headless_verification import export_report, load_snapshot
from apps.api.mcp_adapter_contract import McpContractError, call_tool, list_tools


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


ARGS = {"case_id": "case-a", "brief_id": "brief-1"}


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
        call_tool(store=store, bearer="host-token",
                  name="caseproof_discover_references", arguments={**ARGS, extra: "x"})
    assert store.bearers == []


@pytest.mark.parametrize("name", [
    "caseproof_record_review_decision", "record", "", "caseproof_delete_matter"])
def test_unknown_or_write_tool_names_are_rejected(name):
    with pytest.raises(McpContractError):
        call_tool(store=FakeStore(), bearer="host-token", name=name, arguments=ARGS)


@pytest.mark.parametrize("arguments", [
    None, [], {}, {"case_id": "case-a"}, {"case_id": "../x", "brief_id": "b"},
    {"case_id": 1, "brief_id": "b"}, {"case_id": "a" * 101, "brief_id": "b"},
])
def test_malformed_arguments_are_rejected(arguments):
    with pytest.raises(McpContractError):
        call_tool(store=FakeStore(), bearer="host-token",
                  name="caseproof_discover_references", arguments=arguments)


def test_blank_host_bearer_is_rejected():
    with pytest.raises(McpContractError):
        call_tool(store=FakeStore(), bearer="  ",
                  name="caseproof_discover_references", arguments=ARGS)


def test_discovery_matches_the_shared_snapshot_and_uses_the_host_bearer():
    store = FakeStore()
    result = call_tool(store=store, bearer="host-token",
                       name="caseproof_discover_references", arguments=ARGS)
    assert result["isError"] is False
    assert result["structuredContent"] == load_snapshot(
        FakeStore(), "host-token", "case-a", "brief-1")
    assert set(store.bearers) == {"host-token"}
    assert result["structuredContent"]["schema"] == "caseproof-headless-discovery-v1"


def test_export_json_and_markdown_match_the_shared_report():
    for fmt in ("json", "markdown"):
        result = call_tool(store=FakeStore(), bearer="host-token",
                           name="caseproof_export_report",
                           arguments={**ARGS, "format": fmt})
        media_type, body = export_report(FakeStore(), "host-token", "case-a", "brief-1", fmt)
        assert result == {"isError": False, "mediaType": media_type, "content": body}
    report = json.loads(call_tool(store=FakeStore(), bearer="host-token",
                                  name="caseproof_export_report", arguments=ARGS)["content"])
    assert report["filing_status"] == "not_assessed"
    assert report["professional_certificate"] is False
    assert report["human_decisions"][0]["decision"] == "CONFIRMED_QUALIFIED"


def test_invalid_format_is_rejected():
    with pytest.raises(McpContractError):
        call_tool(store=FakeStore(), bearer="host-token",
                  name="caseproof_export_report", arguments={**ARGS, "format": "docx"})


def test_access_failure_returns_an_opaque_error_without_details():
    for name in ("caseproof_discover_references", "caseproof_export_report"):
        result = call_tool(store=FakeStore(deny=True), bearer="host-token",
                           name=name, arguments=ARGS)
        assert result == {"isError": True, "error": "access_rejected"}


def test_missing_store_fails_closed():
    result = call_tool(store=None, bearer="host-token",
                       name="caseproof_discover_references", arguments=ARGS)
    assert result == {"isError": True, "error": "access_rejected"}
