"""Repository-owned synthetic material; no provider calls or customer source input."""

from __future__ import annotations

from hashlib import sha256
from uuid import UUID

from application.documents.contracts import ParsedDocument
from application.documents.intake import CapturedDocument, DocumentIntelligence, EntityAssignment
from application.extraction.contracts import (
    ClaimSlot,
    ExtractionConfig,
    ProviderReply,
    Scope,
    StepJournal,
    decode,
)
from application.extraction.journal import MemoryJournal
from application.review.contracts import ReviewSnapshot, freeze_review
from domains.finance.extraction_rules import FinanceEvidencePolicy
from evals.document_corpus import CASES
from infrastructure.parsers.limited import LimitedDocumentParser
from packages.evidence_kernel.domain.source_versions import SourceVersion
from scripts.extraction_fixtures import NOW, SCOPE, ScriptedProvider, envelope

ACTOR = UUID(int=301)


class DemoProvider(ScriptedProvider):
    def __init__(self, *, boundary_review: bool = False) -> None:
        super().__init__()
        self.boundary_review = boundary_review

    def complete(self, system: str, payload: str, *, request_id: str, max_tokens: int) -> ProviderReply:
        data = decode(payload)
        atoms = []
        for src in data["sources"]:
            if src["id"] == "response":
                quote, signal, value = src["text"], "invoice_issued", "1150.00"
            else:
                case = next(c for c in CASES if c.case_id == src["id"])
                quote, signal, value = case.quote, case.signal, case.value
            atoms.append(
                {
                    "entity_id": "E1",
                    "source_id": src["id"],
                    "quote": quote,
                    "statement": f"Proposed {signal.replace('_', ' ')}: EUR {value}",
                    "signal": signal,
                    "slot": signal,
                    "value": value,
                    "polarity": "affirmative",
                    "relation": "supports",
                }
            )
        suggested = []
        if self.boundary_review and data["purpose"].startswith("case-wide"):
            response = next((s for s in data["sources"] if s["id"] == "response"), None)
            if response is not None:
                suggested = [
                    {
                        "entity_id": "E1",
                        "kind": "invoice",
                        "source_id": "response",
                        "quote": response["text"],
                    }
                ]
        return ProviderReply(envelope(atoms, entities=suggested), self.identity, self.model)


def demo_material(
    *,
    scope: Scope = SCOPE,
    documents: tuple[CapturedDocument, ...] | None = None,
    source_intents: dict[str, UUID] | None = None,
    case_revision: int = 1,
    policy_version: str = "synthetic-review-policy-v1",
    journal: StepJournal | None = None,
    boundary_review: bool = False,
) -> tuple[ReviewSnapshot, tuple[ParsedDocument, ...]]:
    if documents is None:
        response = b"Invoice INV-2026-001: revised amount EUR 1150.00."
        documents = (
            *tuple(c.captured() for c in CASES[:3]),
            CapturedDocument(
                "response",
                SourceVersion(
                    "response", "synthetic-v1", sha256(response).hexdigest(), response, NOW, "text/plain"
                ),
            ),
        )
    assignments = tuple(
        EntityAssignment(
            "E1", "purchase_order" if d.source_id == "order" else "invoice", d.source_id,
            confirmed=not (boundary_review and d.source_id == "response")
        )
        for d in documents
    )
    available = {d.source_id for d in documents}
    slots = []
    for signal, ids in (
        ("invoice_issued", ("invoice", "response")),
        ("purchase_order_issued", ("order",)),
        ("amount_disputed", ("supplier",)),
        ("goods_received", ("invoice",)),
    ):
        used = tuple(s for s in ids if s in available)
        if used:
            slots.append(ClaimSlot("E1", signal, used))
    result = DocumentIntelligence(
        LimitedDocumentParser(),
        DemoProvider(boundary_review=boundary_review),
        journal if journal is not None else MemoryJournal(),
        FinanceEvidencePolicy(),
    ).run(
        scope=scope,
        run_id="synthetic-review-material",
        documents=documents,
        assignments=assignments,
        slots=tuple(slots),
        config=ExtractionConfig(repair_passes=0),
    )
    snapshot = freeze_review(
        result,
        scope=scope,
        title="Invoice INV-2026-001",
        case_revision=case_revision,
        policy_version=policy_version,
        source_intents=source_intents,
    )
    return snapshot, result.documents
