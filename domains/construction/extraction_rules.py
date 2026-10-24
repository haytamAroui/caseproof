"""Thin experimental vocabulary; legal entitlement and causation stay unassessed."""

import re


class ConstructionEvidencePolicy:
    namespace = "construction"
    version = "construction-observations-v1"
    signals = (
        "variation_instruction_issued",
        "variation_work_performed",
        "scope_changed",
        "notice_sent",
        "price_agreed",
        "approval_denied",
        "delay_asserted",
        "supporting_record_missing",
    )
    _phrases = {
        "variation_instruction_issued": r"\b(instructed|instruction)\b",
        "variation_work_performed": r"\b(performed|completed)\b",
        "scope_changed": r"\b(change[ds]?|variation)\b",
        "notice_sent": r"\bnotice\b",
        "price_agreed": r"\bagreed\b",
        "approval_denied": r"\b(denied|refused)\b",
        "delay_asserted": r"\bdelay\b",
        "supporting_record_missing": r"\bmissing\b",
    }

    def validate(self, signal: str, slot: str, quote: str, value: str, kind: str) -> tuple[str, str]:
        if signal not in self.signals:
            return "needs_review", "unregistered_signal"
        if signal != slot or kind not in {"variation", "instruction", "notice"}:
            return "rejected", "signal_consumer_mismatch"
        if not re.search(self._phrases[signal], quote, re.IGNORECASE):
            return "needs_review", "signal_semantics_unresolved"
        if not re.search(r"(?<![\w+-])(?<!\d[.,])" + re.escape(value) + r"(?!\w|[.,]\d)", quote):
            return "rejected", "value_not_in_quote"
        return "validated", "proposal_lexically_consistent"
