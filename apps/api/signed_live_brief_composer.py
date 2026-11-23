"""Verified-readback publish composition for the live signed path.

The workbench route and the disposable backend share one six-argument
``publish_uploaded`` contract. This adapter provides the same contract on
the live path: every artifact is derived service-side from verified bytes
and signed reads, then delegated to the RPC adapter. The publish RPC
re-validates everything server-side; nothing here ever trusts the client.

Derivation, fail-closed at every step:

1. verified byte readback through :class:`SignedSourceLibrary` (digest and
   revocation-drift re-check), restricted to ``text/plain`` originals in
   strict UTF-8, matching the trusted-registry parser ``strict-utf8-txt-v1``;
2. the confirmed exhibit register via ``caseproof_signed_exhibit_register``;
3. citation references extracted from the representation
   (« citation » (label)) whose label names a confirmed exhibit or one of
   its aliases — the same citation grammar as the demo workbench;
4. a graph preimage with the same canonical fields as the disposable graph
   identity, minus the vault intent, which the publish RPC resolves
   server-side and stores on the version row;
5. a post-publish head read (``caseproof_signed_brief_head``) compared
   with the RPC outcome: any mismatch is an unknown outcome, never a
   silent success.

Assertions stay empty: the journey checks citations, and a richer fact
extractor is a product decision the owner has not made. The RPC already
enforces the full assertion contract for any future extractor.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from application.extraction.contracts import ExtractionError
from application.litigation.fact_extraction import extract_fact_assertions
from apps.api.signed_document_parse import parse_verified_original, resolve_quote_page
from apps.api.signed_supabase_brief_publisher import (
    LiveSignedBriefPublisher,
    SignedPublishOutcome,
    _int,
    _uuid,
    _working_brief_id,
)
from apps.api.signed_supabase_originals import (
    API_KEY,
    PrivateStorageFailure,
    PrivateStorageOutcomeUnknown,
)
from apps.api.signed_supabase_source_library import SignedSourceLibrary

PARSER_ID = "strict-utf8-txt-v1"
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
# The only DOCX warning compatible with publishing: layout page numbers stay
# unverified and references carry pdf_page=None (never inferred). Any other
# warning marks a real coverage gap (images, fields, headers) and refuses.
_DOCX_PUBLISHABLE_WARNINGS = frozenset({"docx_layout_page_numbers_unverified"})
_PDF_MIME = "application/pdf"
# Text-native PDF publishes only on a COMPLETE parse: zero warnings. Any
# warning (annotation, image/XObject, page without a text layer) marks real
# uncovered content and refuses. Scanned/OCR PDFs never publish: no OCR is
# claimed and no page is guessed.
_PDF_PUBLISHABLE_WARNINGS: frozenset[str] = frozenset()
_MAX_REPRESENTATION_BYTES = 480_000
_MAX_REFERENCES = 512
_MAX_QUOTE = 4000
_MAX_LABEL = 160
_MAX_GRAPH_TEXT = 200_000

# Citation grammar of the demo workbench: « citation exacte » (label).
_QUOTE_RE = re.compile(r"«\s*(?P<quote>[^«»]{4,600}?)\s*»\s*\((?P<label>[^)]{4,120})\)")


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class ComposedSignedBriefPublisher:
    """Six-argument live publish: derive service-side, then delegate."""

    library: SignedSourceLibrary
    publisher: LiveSignedBriefPublisher
    publishable_key: str = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.publishable_key, str) or not API_KEY.fullmatch(
            self.publishable_key
        ):
            raise ValueError("Use a Supabase publishable key, never a service key")

    # The dev app's signed port is ONE object: document listing, source
    # registration and exhibit confirmation are plain signed-RPC passthroughs;
    # only publish_uploaded adds the verified-readback derivation below.
    def list_documents(self, *, bearer: str, case_id: str) -> Any:
        return self.publisher.list_documents(bearer=bearer, case_id=case_id)

    def register_source_version(self, **kwargs: Any) -> Any:
        return self.publisher.register_source_version(**kwargs)

    def confirm_exhibit(self, **kwargs: Any) -> Any:
        return self.publisher.confirm_exhibit(**kwargs)

    def _confirmed_labels(
        self, bearer: str, case_id: str, version_id: str
    ) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
        """Confirmed register labels (lowercase → display) and, per display
        label, the cited source identity with whether the register entry
        carries a real physical page inventory (PDF manifest pages)."""
        result = self.publisher._call(
            bearer,
            "caseproof_signed_exhibit_register",
            {"p_case": _uuid(case_id, "case_id"), "p_version": _uuid(version_id, "version_id")},
        )
        revision = result.get("register_revision")
        payload = result.get("payload")
        if payload is None:
            if revision != 0:
                raise PrivateStorageFailure("RPC result outside the signed contract")
            return {}, {}
        if not isinstance(payload, dict):
            raise PrivateStorageFailure("RPC result outside the signed contract")
        entries_raw = payload.get("entries")
        if not isinstance(entries_raw, list) or len(entries_raw) > 512:
            raise PrivateStorageFailure("RPC result outside the signed contract")
        labels: dict[str, str] = {}
        sources: dict[str, dict[str, Any]] = {}
        for entry in entries_raw:
            if not isinstance(entry, dict) or entry.get("confirmed") is not True:
                continue
            display = entry.get("display_label")
            if type(display) is not str or not 0 < len(display.strip()) <= _MAX_LABEL:
                raise PrivateStorageFailure("RPC result outside the signed contract")
            display = display.strip()
            labels.setdefault(display.lower(), display)
            aliases = entry.get("aliases")
            if aliases is None:
                aliases = []
            if not isinstance(aliases, list) or len(aliases) > 64:
                raise PrivateStorageFailure("RPC result outside the signed contract")
            for alias in aliases:
                if type(alias) is not str or not 0 < len(alias.strip()) <= _MAX_LABEL:
                    raise PrivateStorageFailure("RPC result outside the signed contract")
                labels.setdefault(alias.strip().lower(), display)
            if display in sources:
                continue
            pages = entry.get("pages")
            if (
                not isinstance(pages, list)
                or not 1 <= len(pages) <= 512
                or any(not isinstance(page, dict) for page in pages)
            ):
                raise PrivateStorageFailure("RPC result outside the signed contract")
            first = pages[0]
            source_id, source_version = first.get("source_id"), first.get("version_id")
            if type(source_id) is not str or type(source_version) is not str:
                raise PrivateStorageFailure("RPC result outside the signed contract")
            paginated = all(
                type(page.get("pdf_page")) is int
                or (
                    type(page.get("pdf_page")) is float
                    and float(page.get("pdf_page")).is_integer()
                )
                for page in pages
            )
            sources[display] = {
                "document_id": source_id,
                "version_id": source_version,
                "paginated": paginated,
            }
        return labels, sources

    def _extract_references(
        self, text: str, labels: dict[str, str]
    ) -> tuple[list[dict[str, Any]], list[tuple[str, int]]]:
        references: list[dict[str, Any]] = []
        citations: list[tuple[str, int]] = []
        for match in _QUOTE_RE.finditer(text):
            display = labels.get(match.group("label").strip().lower())
            if display is None:
                continue
            quote = match.group("quote").strip()
            if not quote or len(quote) > _MAX_QUOTE:
                continue
            reference_id = f"ref-{len(references) + 1:02d}"
            references.append(
                {
                    "reference_id": reference_id,
                    "exhibit_label": display,
                    "exact_quote": quote,
                    "pdf_page": None,
                }
            )
            citations.append((reference_id, match.end()))
            if len(references) > _MAX_REFERENCES:
                raise PrivateStorageFailure("brief citations outside the signed contract")
        return references, citations

    def _resolve_quote_page(
        self,
        *,
        bearer: str,
        case_key: str,
        document_id: str,
        version_id: str,
        quote: str,
    ) -> int | None:
        """Physical PDF page of an exact quote, only when unambiguous.

        Re-derived from the exhibit's verified bytes with the bounded
        parser — never from a stored manifest. The page is resolved only
        when every occurrence of the quote lies entirely inside exactly
        one physical page's blocks; any ambiguity, read/parse failure or
        non-PDF source abstains to None (displayed « not mapped »).
        """
        try:
            ref, _length = self.library.source(
                bearer=bearer, case_id=case_key,
                document_id=_uuid(document_id, "document_id"),
                version_id=_uuid(version_id, "version_id"),
            )
            if ref.content_type != _PDF_MIME:
                return None
            data = self.library.read(
                bearer=bearer, case_id=case_key,
                document_id=_uuid(document_id, "document_id"),
                version_id=_uuid(version_id, "version_id"),
            )
            text, manifest = parse_verified_original(
                document_id=document_id, version_id=version_id,
                data=data, media_type=ref.content_type,
            )
        except (ExtractionError, PrivateStorageFailure, ValueError):
            # Abstention, jamais de mapping inventé : la page reste nulle.
            return None
        blocks = manifest.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            return None
        return resolve_quote_page(text, blocks, quote)

    @staticmethod
    def _parse_verified_text(
        *, document_id: str, version_id: str, data: bytes, media_type: str
    ) -> tuple[str, str]:
        """Verified bytes -> (representation, parser_id), fail-closed.

        text/plain decodes as strict UTF-8 under the trusted-registry
        parser identity; DOCX goes through the bounded fail-closed parser
        and publishes only when every block maps the text contiguously and
        no warning beyond unverified layout page numbers remains (page
        numbers are never inferred: references keep pdf_page=None).
        Text-native PDF publishes only on a complete zero-warning parse;
        any annotation, visual object or page without a text layer is a
        coverage gap that refuses. Scanned/OCR PDFs never publish.
        """
        if media_type == "text/plain":
            try:
                return data.decode("utf-8", "strict"), PARSER_ID
            except UnicodeDecodeError:
                raise PrivateStorageFailure(
                    "original outside the trusted UTF-8 parser"
                ) from None
        if media_type == _DOCX_MIME:
            try:
                text, manifest = parse_verified_original(
                    document_id=document_id, version_id=version_id,
                    data=data, media_type=media_type,
                )
            except ExtractionError:
                raise PrivateStorageFailure(
                    "original outside the trusted DOCX parser"
                ) from None
            warnings = manifest.get("warnings")
            if (
                not isinstance(warnings, list)
                or set(warnings) - _DOCX_PUBLISHABLE_WARNINGS
                or not manifest.get("blocks")
            ):
                raise PrivateStorageFailure("DOCX coverage gap never publishes")
            parser_id = manifest.get("parser_id")
            if type(parser_id) is not str or not 0 < len(parser_id) <= 256:
                raise PrivateStorageFailure("trusted DOCX parser identity missing")
            return text, parser_id
        if media_type == _PDF_MIME:
            try:
                text, manifest = parse_verified_original(
                    document_id=document_id, version_id=version_id,
                    data=data, media_type=media_type,
                )
            except ExtractionError:
                raise PrivateStorageFailure(
                    "original outside the trusted PDF parser"
                ) from None
            warnings = manifest.get("warnings")
            if (
                not isinstance(warnings, list)
                or set(warnings) - _PDF_PUBLISHABLE_WARNINGS
                or not manifest.get("blocks")
            ):
                raise PrivateStorageFailure("PDF coverage gap never publishes")
            parser_id = manifest.get("parser_id")
            if type(parser_id) is not str or not 0 < len(parser_id) <= 256:
                raise PrivateStorageFailure("trusted PDF parser identity missing")
            return text, parser_id
        raise PrivateStorageFailure("original media outside the trusted parsers")

    def publish_uploaded(
        self,
        *,
        bearer: str,
        case_id: str,
        document_id: str,
        version_id: str,
        document_role: str,
        expected_revision: int,
    ) -> SignedPublishOutcome:
        """Derive every artifact from verified reads, then publish via the RPC."""
        if document_role not in {"own_draft", "opponent_brief"}:
            raise ValueError("invalid document role")
        case_key = _uuid(case_id, "case_id")
        document_key = _uuid(document_id, "document_id")
        version_key = _uuid(version_id, "version_id")
        _int(expected_revision, "expected_revision", low=0, high=1_000_000)

        ref, _length = self.library.source(
            bearer=bearer, case_id=case_key, document_id=document_key,
            version_id=version_key,
        )
        data = self.library.read(
            bearer=bearer, case_id=case_key, document_id=document_key,
            version_id=version_key,
        )
        text, parser_id = self._parse_verified_text(
            document_id=document_key, version_id=version_key,
            data=data, media_type=ref.content_type,
        )
        if not 0 < len(text.encode("utf-8")) <= _MAX_REPRESENTATION_BYTES:
            raise PrivateStorageFailure("representation outside the signed contract")

        labels, sources = self._confirmed_labels(bearer, case_key, version_key)
        references, citations = self._extract_references(text, labels)
        for reference in references:
            source = sources.get(reference["exhibit_label"])
            if source is None or source["paginated"] is not True:
                continue
            page = self._resolve_quote_page(
                bearer=bearer, case_key=case_key,
                document_id=source["document_id"],
                version_id=source["version_id"],
                quote=reference["exact_quote"],
            )
            if page is not None:
                reference["pdf_page"] = page
        assertions = [
            {
                "claim_id": assertion.claim_id,
                "reference_id": assertion.reference_id,
                "text_start": assertion.text_start,
                "text_end": assertion.text_end,
                "assertion_text": assertion.text,
                "kind": assertion.kind.value,
                "fact_role": assertion.role.value,
                "language": assertion.language,
                "source_language": assertion.source_language,
            }
            for assertion in extract_fact_assertions(text, tuple(citations))
        ]
        representation_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        brief_version_id = str(uuid4())
        brief_id = _working_brief_id(case_key, document_role)
        preimage = {
            "brief_id": brief_id,
            "case": case_key,
            "version_id": brief_version_id,
            "original_sha256": ref.sha256_hex,
            "representation_sha256": representation_sha,
            "parser_id": parser_id,
            "document_id": document_key,
            "source_version": version_key,
            "role": document_role,
            "references": references,
            "assertions": assertions,
        }
        graph_text = _canonical(preimage)
        if len(graph_text) > _MAX_GRAPH_TEXT:
            raise PrivateStorageFailure("graph outside the signed contract")
        graph_sha = hashlib.sha256(graph_text.encode("utf-8")).hexdigest()

        outcome = self.publisher.publish_uploaded(
            bearer=bearer,
            case_id=case_key,
            document_id=document_key,
            version_id=version_key,
            document_role=document_role,
            expected_revision=expected_revision,
            brief_version_id=brief_version_id,
            request_id=str(uuid4()),
            representation=text,
            representation_sha256=representation_sha,
            parser_id=parser_id,
            references=references,
            assertions=assertions,
            graph_text=graph_text,
            graph_sha256=graph_sha,
        )

        # Verified read-back: the stored head must be exactly what the RPC
        # reported, otherwise the outcome is unknown, never a silent success.
        head = self.publisher._call(
            bearer,
            "caseproof_signed_brief_head",
            {"p_case": case_key, "p_role": document_role},
        )
        if (
            head.get("brief_id") != outcome.brief_id
            or head.get("version_id") != outcome.brief_version_id
            or head.get("revision") != outcome.published_revision
        ):
            raise PrivateStorageOutcomeUnknown("publish outcome unverifiable")
        return outcome


__all__ = ["ComposedSignedBriefPublisher", "PARSER_ID"]
