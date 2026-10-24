"""Repository-owned synthetic inputs with explicit extraction labels."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from application.documents.intake import CapturedDocument, EntityAssignment
from application.extraction.contracts import ClaimSlot
from packages.evidence_kernel.domain.source_versions import SourceVersion
from scripts.extraction_fixtures import NOW

ROOT = Path(__file__).resolve().parents[1] / "tests/fixtures/documents"


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    filename: str
    media_type: str
    entity_kind: str
    signal: str
    value: str
    quote: str
    polarity: str = "affirmative"

    def captured(self) -> CapturedDocument:
        raw = (ROOT / self.filename).read_bytes()
        return CapturedDocument(
            self.case_id,
            SourceVersion(self.case_id, "synthetic-v1", sha256(raw).hexdigest(), raw, NOW, self.media_type),
        )

    @property
    def assignment(self) -> EntityAssignment:
        return EntityAssignment("E1", self.entity_kind, self.case_id, confirmed=True)

    @property
    def slot(self) -> ClaimSlot:
        return ClaimSlot("E1", self.signal, (self.case_id,))


CASES = (
    EvaluationCase(
        "invoice",
        "synthetic_invoice.pdf",
        "application/pdf",
        "invoice",
        "invoice_issued",
        "1250.00",
        "INVOICE INV-2026-001\nSynthetic supplier - evaluation company\nPurchase order: PO-2026-001\nNet amount: EUR 1250.00\n",
    ),
    EvaluationCase(
        "order",
        "synthetic_order.xml",
        "application/xml",
        "purchase_order",
        "purchase_order_issued",
        "1150.00",
        "/{urn:oasis:names:specification:ubl:schema:xsd:Order-2}Order[1]/{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}AnticipatedMonetaryTotal[1]/{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}LineExtensionAmount[1] = 1150.00",
    ),
    EvaluationCase(
        "supplier",
        "synthetic_supplier.eml",
        "message/rfc822",
        "invoice",
        "amount_disputed",
        "1250.00",
        "We dispute invoice INV-2026-001 amount EUR 1250.00.",
    ),
    EvaluationCase(
        "negative",
        "synthetic_negative.txt",
        "text/plain",
        "variation",
        "price_agreed",
        "150.00",
        "Variation V1: no price agreed for EUR 150.00.",
        "negative",
    ),
)
