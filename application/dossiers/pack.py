"""Bounded draft ZIP pack and offline consistency verifier; no legal/authenticity claim."""

from __future__ import annotations

import html
import io
import re
from dataclasses import asdict
from datetime import datetime
from hashlib import sha256
from typing import Any
from zipfile import ZIP_STORED, BadZipFile, ZipFile, ZipInfo

from application.documents.contracts import ParsedDocument, restore
from application.extraction.contracts import ExtractionError, canonical, decode, digest
from application.review.contracts import (
    REVIEW_SCHEMA,
    ZERO_HASH,
    ReviewCommand,
    ReviewKind,
    ReviewSnapshot,
    event_digest,
    validate_command,
)
from packages.evidence_kernel.domain.source_versions import SourceVersion

MAX_PACK_BYTES = 40 * 1024 * 1024
_ALLOWED = re.compile(
    r"(?:case\.json|reviews\.json|report\.html|README\.txt|sources/[0-9]{3}/(?:original\.bin|text\.txt|normalization\.json))\Z"
)


def _hash(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _json(raw: bytes) -> dict[str, Any]:
    try:
        return decode(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise ExtractionError("pack JSON rejected") from None


def _report(snapshot: ReviewSnapshot, state: dict[str, Any]) -> bytes:
    data = snapshot.data

    def esc(value: object) -> str:
        return html.escape(str(value), quote=True)

    parts = [
        "<!doctype html><html lang='en'><meta charset='utf-8'>",
        "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'\">",
        "<title>Draft evidence and review pack</title>",
        "<style>body{font:16px/1.6 system-ui;max-width:900px;margin:40px auto;padding:20px;color:#172d38}"
        "article{border-top:1px solid #ccd6db;padding:20px 0}blockquote{white-space:pre-wrap;overflow-wrap:anywhere}"
        "code{overflow-wrap:anywhere}h1,h2{line-height:1.2}@media print{body{margin:0}article{break-inside:avoid}}</style>",
        f"<h1>{esc(data['title'])}</h1><p><strong>Draft · recommendations only · no approved conclusion</strong></p>",
        "<p>Integrity checks establish consistency with captured files, not source authenticity, legal validity, "
        "human authorization or a qualified signature. Conflicts and missing evidence remain unresolved.</p>",
        f"<p>Snapshot <code>{snapshot.snapshot_hash}</code></p><h2>Evidence and uncertainty</h2>",
    ]
    for atom in data["extraction"]["atoms"]:
        parts.append(
            f"<article><h3>{esc(atom['statement'])}</h3><p>{esc(atom['state'])} · {esc(atom['reason'])}</p>"
            f"<blockquote>{esc(atom['quote'])}</blockquote><p>Source {esc(atom['source_id'])}, "
            f"span {esc(atom['start'])}–{esc(atom['end'])}, entity {esc(atom['entity_id'])}</p></article>"
        )
    parts.append("<h2>Required claim slots</h2><ul>")
    for slot in data["extraction"]["slots"]:
        parts.append(f"<li>{esc(slot['entity_id'])}: {esc(slot['slot'])} — {esc(slot['state'])}</li>")
    parts.append("</ul><h2>Review recommendations</h2>")
    for event in state["events"]:
        c = event["command"]
        parts.append(
            f"<article><h3>Revision {event['revision']} · {esc(c['kind'])}</h3>"
            f"<p>{esc(event['actor_id'])} · {esc(event['recorded_at'])}</p><p>{esc(c['note'])}</p>"
            f"<p>{esc(c.get('correction') or '')}</p><p>Input snapshot <code>{esc(c['snapshot_hash'])}</code></p></article>"
        )
    parts.append(
        "<p>Earlier-snapshot review entries are historical recommendations; their former evidence is not expanded in this pack.</p></html>"
    )
    return "".join(parts).encode()


def build_pack(
    snapshot: ReviewSnapshot, documents: tuple[ParsedDocument, ...], state: dict[str, Any]
) -> tuple[bytes, str]:
    if state["snapshot_hash"] != snapshot.snapshot_hash or state["snapshot"] != snapshot.data:
        raise ExtractionError("export snapshot changed")
    if state.get("approved") is not False or snapshot.data.get("approved") is not False:
        raise ExtractionError("approved export is not supported")
    sources = snapshot.data["sources"]
    if {p.evidence.source_id for p in documents} != {s["source_id"] for s in sources}:
        raise ExtractionError("export source inventory mismatch")
    files = {
        "case.json": snapshot.payload_json.encode(),
        "reviews.json": canonical(state).encode(),
        "report.html": _report(snapshot, state),
        "README.txt": b"DRAFT EVIDENCE / REVIEW PACK\nNo approved conclusion or authenticity certification.\n"
        b"Verify with trusted repository code: python -m scripts.verify_resolution_pack FILE --expected-manifest SHA256\n"
        b"Keep SHA256 separately from this ZIP. Never run code or extract unknown paths from untrusted packs.\n",
    }
    file_sources = []
    for i, descriptor in enumerate(sources):
        parsed = next(p for p in documents if p.evidence.source_id == descriptor["source_id"])
        if (
            parsed.evidence.source.sha256_hex != descriptor["sha256"]
            or digest(parsed.artifact()) != descriptor["artifact_sha256"]
        ):
            raise ExtractionError("export source/representation changed")
        prefix = f"sources/{i:03d}"
        files[prefix + "/original.bin"] = parsed.evidence.source.content
        files[prefix + "/text.txt"] = parsed.evidence.representation.content
        files[prefix + "/normalization.json"] = canonical(parsed.artifact()).encode()
        file_sources.append({"source_id": descriptor["source_id"], "prefix": prefix})
    manifest = {
        "schema": "caseproof-draft-pack-v1",
        "snapshot_hash": snapshot.snapshot_hash,
        "scope": snapshot.scope.namespace,
        "audit_head": state["audit_head"],
        "sources": file_sources,
        "approved": False,
        "files": {name: {"sha256": _hash(raw), "bytes": len(raw)} for name, raw in sorted(files.items())},
    }
    manifest_raw = canonical(manifest).encode()
    files["manifest.json"] = manifest_raw
    if sum(map(len, files.values())) > MAX_PACK_BYTES - 100_000:
        raise ExtractionError("draft pack byte limit exceeded")
    output = io.BytesIO()
    with ZipFile(output, "w", compression=ZIP_STORED) as archive:
        for name, raw in sorted(files.items()):
            info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_STORED
            info.external_attr = 0o600 << 16
            archive.writestr(info, raw)
    data = output.getvalue()
    verify_pack(data, expected_manifest=_hash(manifest_raw))
    return data, _hash(manifest_raw)


def verify_pack(raw: bytes, *, expected_manifest: str | None = None) -> dict[str, Any]:
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_PACK_BYTES:
        raise ExtractionError("pack input byte limit")
    try:
        with ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            if not 1 <= len(infos) <= 128 or len({i.filename for i in infos}) != len(infos):
                raise ExtractionError("invalid pack inventory")
            if any(
                i.compress_type != ZIP_STORED
                or i.flag_bits & 1
                or i.file_size > 10 * 1024 * 1024
                or (i.filename != "manifest.json" and _ALLOWED.fullmatch(i.filename) is None)
                for i in infos
            ):
                raise ExtractionError("unsafe pack entry")
            if sum(i.file_size for i in infos) > MAX_PACK_BYTES:
                raise ExtractionError("pack expanded byte limit")
            files = {i.filename: archive.read(i) for i in infos}
    except (BadZipFile, RuntimeError, KeyError, OSError):
        raise ExtractionError("pack archive rejected") from None
    if "manifest.json" not in files:
        raise ExtractionError("pack manifest missing")
    manifest_raw = files.pop("manifest.json")
    manifest_hash = _hash(manifest_raw)
    if expected_manifest is not None and expected_manifest != manifest_hash:
        raise ExtractionError("external manifest checkpoint mismatch")
    manifest = _json(manifest_raw)
    if manifest.get("schema") != "caseproof-draft-pack-v1" or manifest.get("approved") is not False:
        raise ExtractionError("unsupported pack authority/schema")
    if set(manifest["files"]) != set(files):
        raise ExtractionError("pack files missing or undeclared")
    for name, metadata in manifest["files"].items():
        if metadata != {"sha256": _hash(files[name]), "bytes": len(files[name])}:
            raise ExtractionError("pack file integrity mismatch")
    case, state = _json(files["case.json"]), _json(files["reviews.json"])
    if (
        case.get("schema") != REVIEW_SCHEMA
        or digest(case) != manifest["snapshot_hash"]
        or state["snapshot_hash"] != manifest["snapshot_hash"]
        or state["snapshot"] != case
        or case["scope"] != manifest["scope"]
        or case["approved"] is not False
        or state["approved"] is not False
        or case["extraction"]["approved"] is not False
    ):
        raise ExtractionError("pack snapshot/authority mismatch")
    extraction = case["extraction"]
    if (
        digest(extraction["manifest"]) != extraction["manifest_hash"]
        or extraction["manifest"]["scope"] != case["scope"]
    ):
        raise ExtractionError("extraction provenance mismatch")
    descriptors = case["sources"]
    if len(descriptors) != len(manifest["sources"]) or len({s["source_id"] for s in descriptors}) != len(
        descriptors
    ):
        raise ExtractionError("source identity inventory mismatch")
    documents = {}
    declared_paths = {"case.json", "reviews.json", "report.html", "README.txt"}
    for descriptor, location in zip(descriptors, manifest["sources"], strict=True):
        if descriptor["source_id"] != location["source_id"] or not re.fullmatch(
            r"sources/[0-9]{3}", location["prefix"]
        ):
            raise ExtractionError("source location mismatch")
        prefix = location["prefix"]
        paths = [prefix + suffix for suffix in ("/original.bin", "/text.txt", "/normalization.json")]
        declared_paths.update(paths)
        original, text_raw, artifact_raw = (files[p] for p in paths)
        source = SourceVersion(
            descriptor["document_id"],
            descriptor["version_id"],
            descriptor["sha256"],
            original,
            datetime.fromisoformat(descriptor["ingested_at"]),
            descriptor["media_type"],
        )
        artifact = _json(artifact_raw)
        parsed = restore(
            descriptor["source_id"],
            source,
            artifact,
            datetime.fromisoformat(descriptor["representation_created_at"]),
        )
        if (
            digest(artifact),
            parsed.evidence.representation.representation_id,
            parsed.evidence.representation.sha256_hex,
            parsed.evidence.representation.content,
        ) != (
            descriptor["artifact_sha256"],
            descriptor["representation_id"],
            descriptor["representation_sha256"],
            text_raw,
        ):
            raise ExtractionError("representation lineage mismatch")
        documents[descriptor["source_id"]] = parsed
    if declared_paths != set(files):
        raise ExtractionError("source file inventory not exact")
    resolved = 0
    for atom in extraction["atoms"]:
        if atom["state"] == "rejected" or atom["start"] is None:
            continue
        linked_document = documents.get(atom["source_id"])
        start, end = atom["start"], atom["end"]
        if (
            linked_document is None
            or type(start) is not int
            or type(end) is not int
            or not 0 <= start < end <= len(linked_document.evidence.content)
            or linked_document.evidence.content[start:end] != atom["quote"]
        ):
            raise ExtractionError("source citation mismatch")
        if [asdict(b) for b in linked_document.locations(start, end)] != case["locations"][
            atom["candidate_id"]
        ]:
            raise ExtractionError("source location mapping changed")
        resolved += 1
    # Independently reconstruct the proposed entity citations from preserved bytes.
    for discovery in extraction["discoveries"]:
        if discovery.get("category") != "entities" or discovery.get("state") != "proposed":
            continue
        proposal = discovery["proposal"]
        src = documents.get(proposal["source_id"])
        start = discovery["start"]
        if (
            src is None
            or type(start) is not int
            or start < 0
            or src.evidence.content[start : start + len(proposal["quote"])] != proposal["quote"]
            or digest(proposal) != discovery["id"]
        ):
            raise ExtractionError("unverifiable boundary proposal in pack")
    from uuid import UUID

    from application.extraction.contracts import Scope

    org, case_id = case["scope"].split(":")
    snapshot = ReviewSnapshot(Scope(UUID(org), UUID(case_id)), manifest["snapshot_hash"], canonical(case))
    previous = ZERO_HASH
    events = state["events"]
    if len(events) > 1000:
        raise ExtractionError("audit history limit")
    request_ids = set()
    for revision, event in enumerate(events, 1):
        c = event["command"]
        command = ReviewCommand(
            UUID(c["request_id"]),
            c["snapshot_hash"],
            c["expected_revision"],
            c["item_id"],
            ReviewKind(c["kind"]),
            c["note"],
            c["correction"],
        )
        if command.snapshot_hash == snapshot.snapshot_hash:
            validate_command(snapshot, command)
        if (
            event["revision"] != revision
            or c["expected_revision"] != revision - 1
            or event["scope"] != case["scope"]
            or event["previous_hash"] != previous
            or event_digest(event) != event["audit_hash"]
            or event["authority"] != "recommendation_only"
            or c["request_id"] in request_ids
        ):
            raise ExtractionError("review audit chain mismatch")
        request_ids.add(c["request_id"])
        previous = event["audit_hash"]
    if (
        state["revision"] != len(events)
        or previous != state["audit_head"]
        or previous != manifest["audit_head"]
    ):
        raise ExtractionError("audit head mismatch")
    return {
        "integrity": "consistent",
        "external_checkpoint_matched": expected_manifest is not None,
        "manifest_sha256": manifest_hash,
        "resolved_citations": resolved,
        "review_events": len(events),
        "approved": False,
        "authenticity_established": False,
    }
