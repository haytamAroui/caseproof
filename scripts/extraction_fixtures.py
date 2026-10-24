"""Consent-safe synthetic corpus and scripted provider; NOT a model benchmark."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import UUID

from application.extraction.contracts import (
    ClaimSlot,
    EntityScope,
    ExtractionConfig,
    ExtractionRequest,
    ExtractionSource,
    ProviderReply,
    Scope,
    canonical,
    decode,
)
from packages.evidence_kernel.domain.source_versions import DerivedRepresentation, SourceVersion

NOW = datetime(2026, 10, 23, tzinfo=UTC)
SCOPE = Scope(UUID(int=101), UUID(int=201))


def source(source_id: str, content: str, *, complete: bool = True) -> ExtractionSource:
    data = content.encode()
    sha = sha256(data).hexdigest()
    original = SourceVersion(source_id, source_id + ":v1", sha, data, NOW, "text/plain")
    representation = DerivedRepresentation(
        source_id + ":r1",
        original.document_id,
        original.version_id,
        sha,
        sha,
        data,
        "text/plain",
        "synthetic-text-identity",
        "v1",
        sha256(b"{}").hexdigest(),
        "unicode_codepoint_zero_based_half_open",
        NOW,
    )
    return ExtractionSource(source_id, original, representation, complete)


def request(
    *,
    construction: bool = False,
    topology: str = "global_first",
    content: str | None = None,
    scope: Scope = SCOPE,
) -> ExtractionRequest:
    body = content or (
        "Variation V1: price agreed EUR 150.00." if construction else "Invoice I1: net EUR 1150.00."
    )
    src = source("synthetic", body)
    signal = "price_agreed" if construction else "invoice_issued"
    return ExtractionRequest(
        scope,
        "synthetic-run-v1",
        (src,),
        (EntityScope("E1", "variation" if construction else "invoice", src.source_id, 0, len(body), True),),
        (ClaimSlot("E1", signal, (src.source_id,)),),
        ExtractionConfig(topology=topology, repair_passes=0),
    )


def atom(req: ExtractionRequest, **overrides: Any) -> dict[str, Any]:
    entity, src, slot = req.entities[0], req.sources[0], req.slots[0]
    value = "150.00" if entity.kind == "variation" else "1150.00"
    return {
        "entity_id": entity.entity_id,
        "source_id": src.source_id,
        "quote": src.content,
        "statement": "The source states the proposed amount",
        "signal": slot.slot_id,
        "slot": slot.slot_id,
        "value": value,
        "polarity": "affirmative",
        "relation": "supports",
        **overrides,
    }


def envelope(
    atoms: list[Any], *, entities: list[Any] | None = None, relationships: list[Any] | None = None
) -> str:
    return canonical({"entities": entities or [], "relationships": relationships or [], "atoms": atoms})


class ScriptedProvider:
    identity = "synthetic-scripted-provider-v1"
    model = "synthetic/no-inference"

    def __init__(self, response: str | None = None) -> None:
        self.response = response
        self.calls: list[str] = []

    def complete(self, system: str, payload: str, *, request_id: str, max_tokens: int) -> ProviderReply:
        self.calls.append(request_id)
        if self.response is not None:
            return ProviderReply(self.response, self.identity, self.model)
        data = decode(payload)
        signal = data["claim_slots"][0]["slot_id"]
        src = data["sources"][0]
        response = envelope(
            [
                {
                    "entity_id": data["authorized_boundaries"][0]["entity_id"],
                    "source_id": src["id"],
                    "quote": src["text"],
                    "statement": "Synthetic proposed amount",
                    "signal": signal,
                    "slot": signal,
                    "value": "150.00" if signal == "price_agreed" else "1150.00",
                    "polarity": "affirmative",
                    "relation": "supports",
                }
            ]
        )
        return ProviderReply(response, self.identity, self.model)


def scoped(req: ExtractionRequest, scope: Scope) -> ExtractionRequest:
    return replace(req, scope=scope)
