"""Canonical MCP parity and release authorization regression tests."""
import json
from unittest.mock import Mock

from apps.api.mcp_adapter_contract import call_canonical_tool

ARGS = {"case_id": "case-a", "brief_id": "brief-a"}


def report():
    return {
        "schema": "caseproof-dossier-v1",
        "snapshot_hash": "a" * 64,
        "verification_contract": {"fidelity_rules_version": "v2"},
        "coverage": {"visual_findings_not_assessed": 1},
        "findings": [{
            "reference_id": "ref-0000",
            "identity": "not_assessed",
            "inventory_status": "unconfirmed",
            "translation_review_required": True,
            "visual_coverage": "not_assessed",
            "pdf_page": 3,
            "printed_page": 8,
            "bundle_page": 14,
        }],
    }


def test_canonical_discovery_matches_signed_dossier_report_without_reinterpretation():
    store = Mock()
    expected = report()
    store.load.return_value = (expected, b"")
    result = call_canonical_tool(store=store, bearer="signed-user",
                                 name="caseproof_discover_references",
                                 arguments=ARGS, allow_document_content=True)
    assert result["structuredContent"] == expected
    assert result["canonical_verification"] is True
    store.load.assert_called_once_with("signed-user", "case-a", "brief-a")


def test_canonical_export_preserves_report_and_human_decisions():
    store = Mock()
    store.load.return_value = (report(), b"")
    store.rpc.return_value = {"decisions": [{"reference_id": "ref-0000", "decision": "CONFIRMED_QUALIFIED"}]}
    result = call_canonical_tool(store=store, bearer="signed-user",
                                 name="caseproof_export_report",
                                 arguments={**ARGS, "format": "json"}, allow_document_content=True)
    exported = json.loads(result["content"])
    assert exported["findings"] == report()["findings"]
    assert exported["human_decisions"] == store.rpc.return_value["decisions"]


def test_release_denial_never_accesses_store():
    store = Mock()
    result = call_canonical_tool(store=store, bearer="signed-user",
                                 name="caseproof_discover_references", arguments=ARGS)
    assert result == {"isError": True, "error": "content_release_not_authorized"}
    store.assert_not_called()
    store.load.assert_not_called()


def test_unavailable_canonical_report_never_falls_back_to_legacy():
    store = Mock()
    store.load.return_value = ({"schema": "caseproof-headless-discovery-v1"}, b"")
    result = call_canonical_tool(store=store, bearer="signed-user",
                                 name="caseproof_discover_references", arguments=ARGS,
                                 allow_document_content=True)
    assert result == {"isError": True, "error": "canonical_report_unavailable"}
