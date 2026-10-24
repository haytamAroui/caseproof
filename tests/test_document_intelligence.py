"""Real parser fixtures, exact source mapping and fail-closed orchestration tests."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from decimal import Decimal

import pytest
from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, TextStringObject

from application.documents.contracts import restore
from application.documents.finance import compare_ubl_accounting_evidence, compare_ubl_evidence, observe_ubl
from application.documents.intake import CapturedDocument, DocumentIntelligence, EntityAssignment
from application.documents.structured import resolve_xml_citation, xml_citation
from application.extraction.contracts import ClaimSlot, ExtractionConfig, ExtractionError
from application.extraction.journal import MemoryJournal
from domains.finance.extraction_rules import FinanceEvidencePolicy
from evals.document_corpus import CASES
from evals.document_extraction import evaluate
from infrastructure.parsers.limited import LimitedDocumentParser
from packages.evidence_kernel.domain.source_versions import SourceVersion
from scripts.extraction_fixtures import NOW, SCOPE, ScriptedProvider, envelope

FIXTURES = Path(__file__).parent / "fixtures/documents"


def captured(raw: bytes, media: str = "text/plain", identity: str = "document") -> CapturedDocument:
    return CapturedDocument(identity, SourceVersion(identity, "v1", sha256(raw).hexdigest(), raw, NOW, media))


def parse(document):
    artifact = LimitedDocumentParser().parse(document.source)
    return restore(document.source_id, document.source, artifact, NOW)


def test_pdf_preserves_original_and_page_text_mapping():
    document = CASES[0].captured()
    parsed = parse(document)
    assert parsed.evidence.source.content == document.source.content
    assert parsed.evidence.complete
    assert parsed.evidence.source.sha256_hex != parsed.evidence.representation.sha256_hex
    assert [b.page_index for b in parsed.blocks] == [0, 1]
    quote = "Net amount: EUR 1250.00"
    start = parsed.evidence.content.index(quote)
    location = parsed.locations(start, start + len(quote))
    assert len(location) == 1 and location[0].page_index == 0
    second = parsed.blocks[1]
    assert parsed.locations(second.start, second.end)[0].page_index == 1
    assert not hasattr(location[0], "bounding_box")


def test_xml_namespace_and_repeated_sibling_paths_stay_distinct():
    doc = captured(b'<r xmlns="urn:test"><x n="1">First</x><x n="2">Second</x></r>', "application/xml")
    parsed = parse(doc)
    values = dict(parsed.fields)
    assert values["/{urn:test}r[1]/{urn:test}x[1]"] == "First"
    path = "/{urn:test}r[1]/{urn:test}x[2]"
    assert values[path] == "Second"
    citation = xml_citation(parsed, path)
    assert citation.anchor.locator.path == ("fields", path)
    assert resolve_xml_citation(SCOPE.namespace, parsed, citation) == "Second"
    with pytest.raises(ExtractionError):
        resolve_xml_citation(SCOPE.namespace, parsed, replace(citation, value="First"))


def test_email_decoded_body_and_header_locations_are_not_sender_authentication():
    parsed = parse(CASES[2].captured())
    assert parsed.evidence.complete
    body = next(b for b in parsed.blocks if b.kind == "email_body")
    assert body.locator == "mime:0"
    assert "We dispute invoice" in parsed.evidence.content[body.start : body.end]
    assert len([b for b in parsed.blocks if b.kind == "email_header"]) == 4
    assert "example.invalid" in parsed.evidence.content


@pytest.mark.parametrize(
    "payload,media",
    [
        (b'<!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]><r>&x;</r>', "application/xml"),
        (b'<!DOCTYPE r [<!ENTITY x "EXPAND">]><r>&x;</r>', "application/xml"),
        (b"<r>", "application/xml"),
        ("<r>value</r>".encode("utf-16"), "application/xml"),
        (b'<?xml version="1.0" encoding="iso-8859-1"?><r>x</r>', "application/xml"),
        (b"%PDF-1.7\ntruncated", "application/pdf"),
        (b"not a pdf", "application/pdf"),
        (b"PK\x03\x04fake", "application/zip"),
        (b"\xff", "text/plain"),
        (b"a" * (5 * 1024 * 1024 + 1), "text/plain"),
        (b"<r>" * 40 + b"x" + b"</r>" * 40, "application/xml"),
    ],
)
def test_untrusted_parser_input_is_rejected_without_raw_error_disclosure(payload, media):
    with pytest.raises(ExtractionError) as exc:
        parse(captured(payload, media))
    assert "file:///etc/passwd" not in str(exc.value) and "EXPAND" not in str(exc.value)


def pdf_bytes(writer):
    import io

    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


def test_blank_scan_like_page_does_not_mean_no_evidence():
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    parsed = parse(captured(pdf_bytes(writer), "application/pdf"))
    assert not parsed.evidence.complete
    assert "pdf_page_needs_ocr_or_review" in parsed.warnings
    assert "no_extractable_text" in parsed.warnings


@pytest.mark.parametrize("active", ["javascript", "attachment", "encrypted", "form"])
def test_active_or_encrypted_pdf_is_not_processed(active):
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    if active == "javascript":
        writer.add_open_action(
            DictionaryObject(
                {
                    NameObject("/S"): NameObject("/JavaScript"),
                    NameObject("/JS"): TextStringObject("synthetic"),
                }
            )
        )
    elif active == "attachment":
        writer.add_attachment("payload.txt", b"synthetic")
    elif active == "encrypted":
        writer.encrypt("synthetic-test-password")
    else:
        writer.root_object[NameObject("/AcroForm")] = DictionaryObject({NameObject("/Fields"): ArrayObject()})
    with pytest.raises(ExtractionError):
        parse(captured(pdf_bytes(writer), "application/pdf"))


def test_many_pages_and_long_text_are_bounded():
    writer = PdfWriter()
    for _ in range(65):
        writer.add_blank_page(width=100, height=100)
    with pytest.raises(ExtractionError):
        parse(captured(pdf_bytes(writer), "application/pdf"))
    with pytest.raises(ExtractionError):
        parse(captured(b"x" * 120_001))


@pytest.mark.parametrize(
    "body,reason",
    [
        (
            b'From: a@example.invalid\r\nMIME-Version: 1.0\r\nContent-Type: text/html\r\n\r\n<img src="https://attacker.invalid">',
            "email_nontext_part_unprocessed",
        ),
        (
            b'From: a@example.invalid\r\nContent-Type: text/plain\r\nContent-Disposition: attachment; filename="../../secret"\r\n\r\nAttachment',
            "email_attachment_unprocessed",
        ),
        (
            b"From: a@example.invalid\r\nFrom: b@example.invalid\r\nContent-Type: text/plain\r\n\r\nBody",
            "email_ambiguous_headers",
        ),
        (b"Content-Type: text/plain; charset=unknown-charset\r\n\r\nBody", "email_charset_unresolved"),
    ],
)
def test_email_unsupported_content_is_explicitly_incomplete(body, reason):
    parsed = parse(captured(body, "message/rfc822"))
    assert not parsed.evidence.complete and reason in parsed.warnings


def test_mime_html_alternative_and_attachments_are_not_silently_excluded():
    from email.message import EmailMessage

    message = EmailMessage()
    message["From"] = "supplier@example.invalid"
    message.set_content("Invoice 1250.00")
    message.add_alternative("<p>Different amount 1050.00</p>", subtype="html")
    parsed = parse(captured(message.as_bytes(), "message/rfc822"))
    assert not parsed.evidence.complete
    assert "email_nontext_part_unprocessed" in parsed.warnings


def test_unicode_text_preserves_exact_codepoint_ranges():
    doc = captured("Factuur café — bedrag €1250.00\r\n".encode())
    parsed = parse(doc)
    assert parsed.evidence.content == doc.source.content.decode()
    assert parsed.blocks[0].end == len(parsed.evidence.content)
    assert parse(doc).artifact() == parsed.artifact()


def test_case_workflow_and_restart_reuse_parsed_representations():
    document = CASES[0].captured()
    case = CASES[0]
    reply = envelope(
        [
            {
                "entity_id": "E1",
                "source_id": case.case_id,
                "quote": case.quote,
                "statement": "Invoice amount proposal",
                "slot": case.signal,
                "signal": case.signal,
                "value": case.value,
                "polarity": "affirmative",
                "relation": "supports",
            }
        ]
    )
    journal, provider = MemoryJournal(), ScriptedProvider(reply)
    kwargs = dict(
        scope=SCOPE,
        run_id="case",
        documents=(document,),
        assignments=(case.assignment,),
        slots=(case.slot,),
        config=ExtractionConfig(repair_passes=0),
    )
    result = DocumentIntelligence(LimitedDocumentParser(), provider, journal, FinanceEvidencePolicy()).run(
        **kwargs
    )
    assert result.status == "review_required" and result.extraction.atoms[0].state == "validated"

    class NoParse(LimitedDocumentParser):
        def parse(self, source):
            raise AssertionError("saved representation must replay")

    replay = DocumentIntelligence(NoParse(), provider, journal, FinanceEvidencePolicy()).run(**kwargs)
    assert replay.extraction.to_json() == result.extraction.to_json() and len(provider.calls) == 2
    assert replay.documents[0].evidence.representation == result.documents[0].evidence.representation


def test_incomplete_required_source_blocks_provider_calls():
    provider = ScriptedProvider()
    document = captured(b"Content-Type: text/html\r\n\r\n<p>Invoice 1250.00</p>", "message/rfc822")
    result = DocumentIntelligence(
        LimitedDocumentParser(), provider, MemoryJournal(), FinanceEvidencePolicy()
    ).run(
        scope=SCOPE,
        run_id="incomplete",
        documents=(document,),
        assignments=(EntityAssignment("E1", "invoice", "document", confirmed=True),),
        slots=(ClaimSlot("E1", "invoice_issued", ("document",)),),
    )
    assert result.status == "blocked" and not provider.calls and result.extraction is None
    assert result.failures == ({"source_id": "document", "reason": "normalization_incomplete"},)


def test_missing_invalid_required_document_is_not_dropped():
    provider = ScriptedProvider()
    case = CASES[0]
    result = DocumentIntelligence(
        LimitedDocumentParser(), provider, MemoryJournal(), FinanceEvidencePolicy()
    ).run(
        scope=SCOPE,
        run_id="bad",
        documents=(case.captured(), captured(b"broken", "application/xml", "bad")),
        assignments=(case.assignment, EntityAssignment("E2", "invoice", "bad")),
        slots=(case.slot, ClaimSlot("E2", "invoice_issued", ("bad",))),
    )
    assert len(result.documents) == 1 and result.failures[0]["source_id"] == "bad"
    assert not provider.calls


def test_changed_parser_or_original_manifest_cannot_reuse_old_results():
    case = CASES[0]
    kwargs = dict(
        scope=SCOPE,
        run_id="immutable",
        documents=(case.captured(),),
        assignments=(case.assignment,),
        slots=(case.slot,),
    )
    journal = MemoryJournal()
    service = DocumentIntelligence(
        LimitedDocumentParser(), ScriptedProvider(envelope([])), journal, FinanceEvidencePolicy()
    )
    service.run(**kwargs)
    with pytest.raises(ExtractionError, match="input changed"):
        service.run(**{**kwargs, "documents": (captured(b"changed", identity=case.case_id),)})


def test_real_ubl_comparison_has_native_exact_scalar_citations():
    invoice = captured(
        (Path(__file__).parent / "fixtures/finance/synthetic_invoice_mismatch_ubl21.xml").read_bytes(),
        "application/xml",
        "invoice",
    )
    order = CASES[1].captured()
    inv, po = parse(invoice), parse(order)
    comparison = compare_ubl_evidence(inv, po, scope=SCOPE.namespace)
    assert comparison.delta == "100.00" and comparison.currency == "EUR"
    assert comparison.requires_authorized_human_review and comparison.requires_evidence_verification
    observation = observe_ubl(inv, kind="invoice", scope=SCOPE.namespace)
    assert resolve_xml_citation(SCOPE.namespace, inv, observation.citation) == "1250.00"



def test_detailed_ubl_reconciliation_retains_original_exact_citations_and_missing_basis():
    invoice = captured(
        (Path(__file__).parent / "fixtures/finance/synthetic_invoice_mismatch_ubl21.xml").read_bytes(),
        "application/xml",
        "invoice",
    )
    inv, po = parse(invoice), parse(CASES[1].captured())
    assessment = compare_ubl_accounting_evidence(inv, po, scope=SCOPE.namespace)
    assert assessment.status == "candidate_requires_review"
    assert assessment.differences[0].code == "NET_INVOICE_ORDER_DIFFERENCE"
    assert assessment.differences[0].delta.amount == Decimal("100.00")
    assert "vat_component_incomplete" in assessment.unresolved
    assert "delivery_and_quantity_basis_unassessed" in assessment.unresolved
    assert assessment.approved is False
    assert len(assessment.evidence_claim_ids) >= 2

def test_duplicate_ubl_monetary_field_does_not_first_win():
    raw = CASES[1].captured().source.content
    raw = raw.replace(
        b"</cac:AnticipatedMonetaryTotal>",
        b'<cbc:LineExtensionAmount currencyID="EUR">1050.00</cbc:LineExtensionAmount></cac:AnticipatedMonetaryTotal>',
    )
    parsed = parse(captured(raw, "application/xml"))
    with pytest.raises(ExtractionError, match="duplicate"):
        observe_ubl(parsed, kind="purchase_order", scope=SCOPE.namespace)


def test_scripted_evaluation_never_claims_live_quality_or_cost():
    report = evaluate()
    assert report["mode"] == "scripted_safety_only" and not report["live_quality_measured"]
    assert len(report["rows"]) == 4
    assert all(r["approval_count"] == 0 and r["reported_cost"] is None for r in report["rows"])
    assert report["rows"][-1]["negative_false_validation"] == 0
    assert all(r["exact_labeled_matches"] == 1 for r in report["rows"])
    with pytest.raises(ExtractionError, match="durable"):
        evaluate(live=True)


def test_parser_timeout_and_clean_environment(monkeypatch):
    import subprocess

    def timeout(*args, **kwargs):
        assert "REQUESTY_API_KEY" not in kwargs["env"]
        assert "PYTHONPATH" not in kwargs["env"]
        assert kwargs["close_fds"] and kwargs["timeout"] == 8
        raise subprocess.TimeoutExpired(args[0], 8)

    monkeypatch.setattr("infrastructure.parsers.limited.subprocess.run", timeout)
    with pytest.raises(ExtractionError, match="timeout"):
        parse(captured(b"synthetic"))


def test_unmapped_material_cannot_hide_inside_representation_mapping():
    document = captured(b"Invoice 1250.00")
    artifact = LimitedDocumentParser().parse(document.source)
    artifact["text"] = "UNMAPPED " + artifact["text"]
    artifact["blocks"][0]["start"] += len("UNMAPPED ")
    artifact["blocks"][0]["end"] += len("UNMAPPED ")
    with pytest.raises(ExtractionError, match="mapping"):
        restore(document.source_id, document.source, artifact, NOW)


def test_failed_normalization_is_durable_and_not_reparsed_on_retry():
    provider, journal = ScriptedProvider(), MemoryJournal()
    document = captured(b"broken XML", "application/xml")
    kwargs = dict(
        scope=SCOPE,
        run_id="failed-source",
        documents=(document,),
        assignments=(EntityAssignment("E1", "invoice", "document"),),
        slots=(ClaimSlot("E1", "invoice_issued", ("document",)),),
    )
    first = DocumentIntelligence(LimitedDocumentParser(), provider, journal, FinanceEvidencePolicy()).run(
        **kwargs
    )

    class NoParse(LimitedDocumentParser):
        def parse(self, source):
            raise AssertionError("failure must be preserved")

    second = DocumentIntelligence(NoParse(), provider, journal, FinanceEvidencePolicy()).run(**kwargs)
    assert first.failures == second.failures and first.status == "blocked" and not provider.calls


def test_empty_xml_attribute_is_preserved_without_assuming_missing_zero():
    parsed = parse(captured(b'<r code=""><x>0</x></r>', "application/xml"))
    assert dict(parsed.fields)["/r[1]/@code"] == ""
    assert dict(parsed.fields)["/r[1]/x[1]"] == "0"


def test_source_capture_provenance_change_requires_new_intake():
    from datetime import timedelta

    case = CASES[0]
    document = case.captured()
    journal = MemoryJournal()
    service = DocumentIntelligence(
        LimitedDocumentParser(), ScriptedProvider(envelope([])), journal, FinanceEvidencePolicy()
    )
    kwargs = dict(
        scope=SCOPE,
        run_id="capture",
        documents=(document,),
        assignments=(case.assignment,),
        slots=(case.slot,),
    )
    service.run(**kwargs)
    changed = replace(document, source=replace(document.source, ingested_at=NOW + timedelta(seconds=1)))
    with pytest.raises(ExtractionError, match="input changed"):
        service.run(**{**kwargs, "documents": (changed,)})
