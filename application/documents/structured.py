"""Kernel-native exact scalar citations to the XML parser's immutable representation."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from application.documents.contracts import ParsedDocument
from application.extraction.contracts import ExtractionError, canonical, digest
from packages.evidence_kernel.domain.anchors import (
    JSON_BASIS,
    AnchorResolver,
    EvidenceAnchor,
    LayoutManifest,
    StructuredField,
    StructuredLayout,
)
from packages.evidence_kernel.domain.source_versions import DerivedRepresentation, InMemorySourceRegistry

SCHEMA_ID = "caseproof.xml-expanded-paths.v1"


@dataclass(frozen=True)
class StructuredCitation:
    representation: DerivedRepresentation
    anchor: EvidenceAnchor
    value: str


def xml_citation(parsed: ParsedDocument, path: str) -> StructuredCitation:
    values = dict(parsed.fields)
    if path not in values or parsed.evidence.source.media_type not in {"text/xml", "application/xml"}:
        raise ExtractionError("exact XML field not available")
    raw = canonical({"schema": SCHEMA_ID, "fields": values}).encode()
    source, text_rep = parsed.evidence.source, parsed.evidence.representation
    rep = DerivedRepresentation(
        "xml:" + digest({"text_rep": text_rep.representation_id, "sha": sha256(raw).hexdigest()}),
        source.document_id,
        source.version_id,
        source.sha256_hex,
        sha256(raw).hexdigest(),
        raw,
        "application/json",
        "xml_field_projection",
        parsed.parser_id,
        text_rep.transform_config_sha256,
        JSON_BASIS,
        text_rep.created_at,
    )
    anchor = EvidenceAnchor(
        "xml-field:" + digest({"rep": rep.representation_id, "path": path}),
        source.document_id,
        source.version_id,
        source.sha256_hex,
        rep.representation_id,
        rep.sha256_hex,
        StructuredField(SCHEMA_ID, ("fields", path)),
    )
    return StructuredCitation(rep, anchor, values[path])


def resolve_xml_citation(scope: str, parsed: ParsedDocument, citation: StructuredCitation) -> str:
    # Reconstruct instead of trusting a persisted successful resolution or a warm cache.
    expected = xml_citation(
        parsed,
        str(citation.anchor.locator.path[-1]) if isinstance(citation.anchor.locator, StructuredField) else "",
    )
    if citation != expected:
        raise ExtractionError("stale or inconsistent XML citation")
    registry = InMemorySourceRegistry()
    registry.register_source(scope, parsed.evidence.source)
    registry.register_representation(scope, citation.representation)
    resolver = AnchorResolver(registry)
    r = citation.representation
    resolver.register_layout(
        scope,
        LayoutManifest(
            r.document_id, r.version_id, r.representation_id, r.sha256_hex, StructuredLayout(SCHEMA_ID)
        ),
    )
    value = resolver.resolve(scope, citation.anchor).value
    if type(value) is not str or value != citation.value:
        raise ExtractionError("XML scalar resolution mismatch")
    return value
