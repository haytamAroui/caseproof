"""Versioned typed finance observation candidates; no authorization or semantic promotion."""

from domains.evidence_signals import SignalDefinition, validate_observation


class FinanceEvidencePolicy:
    namespace = "finance"
    version = "finance-observations-v2"
    definitions: dict[str, SignalDefinition] = {
        "invoice_issued": SignalDefinition(r"\binvoice\b", frozenset({"invoice", "transaction", "purchase_order", "payment"})),
        "purchase_order_issued": SignalDefinition(r"\bpurchase order\b", frozenset({"invoice", "transaction", "purchase_order", "payment"})),
        "amount_disputed": SignalDefinition(
            r"\b(dispute[ds]?|discrepancy)\b", frozenset({"invoice", "transaction", "purchase_order", "payment"}), "money"
        ),
        "payment_asserted": SignalDefinition(r"\b(paid|payment)\b", frozenset({"invoice", "transaction", "purchase_order", "payment"})),
        "credit_note_issued": SignalDefinition(r"\bcredit note\b", frozenset({"invoice", "transaction", "purchase_order", "payment"})),
        "goods_received": SignalDefinition(r"\b(received|delivered)\b", frozenset({"invoice", "transaction", "purchase_order", "payment"})),
        "supplier_response_received": SignalDefinition(r"\b(replied|response)\b", frozenset({"invoice", "transaction", "purchase_order", "payment"})),
    }
    signals: tuple[str, ...] = tuple(definitions)

    def validate(self, signal: str, slot: str, quote: str, value: str, kind: str) -> tuple[str, str]:
        return validate_observation(
            signal=signal, slot=slot, quote=quote, value=value, kind=kind,
            definitions=self.definitions,
        )
