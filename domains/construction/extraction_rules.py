"""Versioned experimental construction vocabulary: proposals only."""

from domains.evidence_signals import SignalDefinition, validate_observation


class ConstructionEvidencePolicy:
    namespace = "construction"
    version = "construction-observations-v2"
    definitions: dict[str, SignalDefinition] = {
        "variation_instruction_issued": SignalDefinition(
            r"\b(instructed|instruction)\b", frozenset({"variation", "instruction", "notice"})
        ),
        "variation_work_performed": SignalDefinition(
            r"\b(performed|completed)\b", frozenset({"variation", "instruction", "notice"})
        ),
        "scope_changed": SignalDefinition(r"\b(change[ds]?|variation)\b", frozenset({"variation", "instruction", "notice"})),
        "notice_sent": SignalDefinition(r"\bnotice\b", frozenset({"variation", "instruction", "notice"})),
        "price_agreed": SignalDefinition(r"\bagreed\b", frozenset({"variation", "instruction", "notice"}), "money"),
        "approval_denied": SignalDefinition(r"\b(denied|refused)\b", frozenset({"variation", "instruction", "notice"})),
        "delay_asserted": SignalDefinition(r"\bdelay\b", frozenset({"variation", "instruction", "notice"})),
        "supporting_record_missing": SignalDefinition(r"\bmissing\b", frozenset({"variation", "instruction", "notice"})),
    }
    signals: tuple[str, ...] = tuple(definitions)

    def validate(self, signal: str, slot: str, quote: str, value: str, kind: str) -> tuple[str, str]:
        return validate_observation(
            signal=signal, slot=slot, quote=quote, value=value, kind=kind,
            definitions=self.definitions,
        )
