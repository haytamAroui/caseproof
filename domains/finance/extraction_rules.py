"""Conservative, versioned proposal validation, never payment authorization."""

import re


class FinanceEvidencePolicy:
    namespace = "finance"
    version = "finance-observations-v1"
    signals = (
        "invoice_issued",
        "purchase_order_issued",
        "amount_disputed",
        "payment_asserted",
        "credit_note_issued",
        "goods_received",
        "supplier_response_received",
    )
    _phrases = {
        "invoice_issued": r"\binvoice\b",
        "purchase_order_issued": r"\bpurchase order\b",
        "amount_disputed": r"\b(dispute[ds]?|discrepancy)\b",
        "payment_asserted": r"\b(paid|payment)\b",
        "credit_note_issued": r"\bcredit note\b",
        "goods_received": r"\b(received|delivered)\b",
        "supplier_response_received": r"\b(replied|response)\b",
    }

    def validate(self, signal: str, slot: str, quote: str, value: str, kind: str) -> tuple[str, str]:
        if signal not in self.signals:
            return "needs_review", "unregistered_signal"
        if signal != slot or kind not in {"invoice", "transaction", "purchase_order", "payment"}:
            return "rejected", "signal_consumer_mismatch"
        if not re.search(self._phrases[signal], quote, re.IGNORECASE):
            return "needs_review", "signal_semantics_unresolved"
        if not re.search(r"(?<![\w+-])(?<!\d[.,])" + re.escape(value) + r"(?!\w|[.,]\d)", quote):
            return "rejected", "value_not_in_quote"
        return "validated", "proposal_lexically_consistent"
