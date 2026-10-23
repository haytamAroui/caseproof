"""Persist actual text-source lineage/anchors and resolve after process restart.

Disposable fixture writer ONLY, against the existing S2-008a/009b proposals.
Not an application writer, installed migration, trusted parser or live Auth.
All fixtures are synthetic; real PostgreSQL/filesystem reads are mandatory.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from apps.api.disposable_text_evidence import (
    CONFIG_SHA256,
    TRANSFORM_NAME,
    TRANSFORM_VERSION,
    identity_text_layout,
    layout_digest,
    read_disposable_text_evidence,
)
from apps.api.evidence_locator_codec import (
    ExpectedEvidenceParent,
    StoredLocatorError,
    encode_anchor_projection,
)
from apps.api.evidence_vault_protocol import VaultMissing, VaultScope, VaultUnavailable
from apps.api.postgres_evidence_reader import EvidenceRowNotFound
from packages.evidence_kernel.domain.anchors import TEXT_BASIS, EvidenceAnchor, TextSpan
from packages.evidence_kernel.domain.fidelity import (
    CitationResolution,
    ContentFidelity,
    ExactQuote,
    FindingRevision,
)
from scripts.verify_vault_integration import Fixture, begin, connect, coordinator, seed, snapshot

TEXT = "Café — voorwaarde\r\nFactuur  1150 EUR\r\nCafe\u0301 — herhaling\r\nFactuur  1150 EUR\r\n"
QUOTE = "Factuur  1150 EUR"
DATA = TEXT.encode("utf-8")


def parent(f, *, representation_id="identity-1"):
    return ExpectedEvidenceParent(
        f.scope.org_id, f.scope.case_id, "source/text", "v1",
        representation_id, f.digest, f.digest,
    )


def anchor(expected, *, start=None, end=None, anchor_id="amount:second"):
    start = TEXT.rindex(QUOTE) if start is None else start
    return EvidenceAnchor(
        anchor_id, expected.document_id, expected.version_id, expected.source_sha256_hex,
        expected.representation_id, expected.representation_sha256_hex,
        TextSpan(start, start + len(QUOTE) if end is None else end),
    )


def persist_fixture(f, expected, item, *, transform_version=TRANSFORM_VERSION, audit_fault=False):
    """One audited fixture transaction using EXISTING proposal tables only.

    This is intentionally not a production/general-purpose metadata writer.
    Raw offsets or bad parser versions can be seeded to test hostile DB rows.
    No authoritative source/representation byte channel is created here.
    """
    projection = encode_anchor_projection(item, expected)
    layout = identity_text_layout(f.data)
    rep_pk, event = uuid4(), uuid4()
    with connect() as conn:
        physical = conn.execute(
            "select document_id from caseproof.document_versions "
            "where org_id=%s and id=%s", (f.scope.org_id, f.version),
        ).fetchone()[0]
        conn.execute(
            "select id from caseproof.cases where org_id=%s and id=%s for update",
            (f.scope.org_id, f.scope.case_id),
        )
        conn.execute(
            "update caseproof.cases set case_revision=case_revision+1 "
            "where org_id=%s and id=%s", (f.scope.org_id, f.scope.case_id),
        )
        conn.execute(
            "insert into caseproof.audit_events(id,org_id,case_id,actor_type,actor_user_id,"
            "action,event_schema_version,correlation_id,input_sha256_hex) "
            "values(%s,%s,%s,'human',%s,%s,%s,%s,%s)",
            (event, f.scope.org_id, f.scope.case_id, f.actor, "text_fixture_capture",
             "text-fixture-v1", uuid4(), "invalid" if audit_fault else layout_digest(projection)),
        )
        conn.execute(
            "insert into caseproof.s2_008a_source_logical_ids(org_id,case_id,document_pk,"
            "kernel_document_id,audit_event_id) values(%s,%s,%s,%s,%s) on conflict do nothing",
            (f.scope.org_id, f.scope.case_id, physical, expected.document_id, event),
        )
        conn.execute(
            "insert into caseproof.s2_008a_version_logical_ids(org_id,case_id,document_pk,"
            "version_pk,kernel_version_id,source_sha256_hex,audit_event_id) "
            "values(%s,%s,%s,%s,%s,%s,%s) on conflict do nothing",
            (f.scope.org_id, f.scope.case_id, physical, f.version,
             expected.version_id, f.digest, event),
        )
        conn.execute(
            "insert into caseproof.s2_008a_representations(representation_pk,org_id,case_id,"
            "document_pk,version_pk,kernel_version_id,kernel_representation_id,source_sha256_hex,"
            "representation_sha256_hex,media_type,transform_name,transform_version,"
            "transform_config_sha256,coordinate_convention,audit_event_id) "
            "values(%s,%s,%s,%s,%s,%s,%s,%s,%s,'text/plain',%s,%s,%s,%s,%s)",
            (rep_pk, f.scope.org_id, f.scope.case_id, physical, f.version,
             expected.version_id, expected.representation_id, f.digest, f.digest,
             TRANSFORM_NAME, transform_version, CONFIG_SHA256, TEXT_BASIS, event),
        )
        conn.execute(
            "insert into caseproof.s2_008a_layouts(org_id,case_id,representation_pk,layout_kind,"
            "layout_schema_version,layout_manifest,layout_sha256_hex,audit_event_id) "
            "values(%s,%s,%s,'text','krn102-layout-v1',%s,%s,%s)",
            (f.scope.org_id, f.scope.case_id, rep_pk, Jsonb(layout), layout_digest(layout), event),
        )
        conn.execute(
            "insert into caseproof.s2_008a_anchors(anchor_pk,org_id,case_id,kernel_anchor_id,"
            "document_pk,version_pk,representation_pk,source_sha256_hex,representation_sha256_hex,"
            "locator_kind,locator_schema_version,locator,audit_event_id) "
            "values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (uuid4(), f.scope.org_id, f.scope.case_id, item.anchor_id, physical, f.version, rep_pk,
             f.digest, f.digest, projection["locator_kind"], projection["locator_schema_version"],
             Jsonb(projection["locator"]), event),
        )


def read(root, f, expected, *, anchor_id="amount:second", quote=QUOTE, intent=None):
    with connect() as conn, conn.cursor(row_factory=dict_row) as cursor:
        return read_disposable_text_evidence(
            cursor, vault=coordinator(root, f), expected=expected,
            source_intent_id=f.intent if intent is None else intent,
            anchor_id=anchor_id, finding=FindingRevision("amount", "1"), quote=ExactQuote(quote),
        )


def restart(root, f, expected, *, anchor_id="amount:second"):
    manifest = root / "text-restart.json"
    manifest.write_text(json.dumps({
        "root": str(root), "actor": str(f.actor), "version": str(f.version),
        "intent": str(f.intent), "parent": asdict(expected), "anchor": anchor_id,
    }, default=str), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "scripts.verify_text_anchor_integration", "--recover", str(manifest)],
        text=True, capture_output=True, timeout=30, check=False,
    )
    if result.returncode != 0 or result.stdout.strip() != "TEXT_ANCHOR_RESTART_PASSED":
        raise AssertionError("Separate-process exact-anchor recovery failed: " + result.stderr[:1500])


class TextAnchorIntegrationTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory(prefix="caseproof-text-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.f = seed(data=DATA)
        self.expected = parent(self.f)
        vault = coordinator(self.root, self.f)
        self.intent = begin(vault, self.f)
        vault.upload(scope=self.f.scope, intent_id=self.f.intent, data=DATA)

    def persist(self, **kwargs):
        item = anchor(self.expected)
        persist_fixture(self.f, self.expected, item, **kwargs)
        return item

    def test_real_bytes_lineage_and_second_repeated_quote_survive_process_restart(self):
        item = self.persist()
        result = read(self.root, self.f, self.expected)
        self.assertEqual(result.source.content, DATA)
        self.assertEqual(result.representation.content, DATA)
        self.assertEqual(result.fidelity.anchor, item)
        self.assertEqual(result.fidelity.citation_resolution, CitationResolution.RESOLVED)
        self.assertEqual(result.fidelity.content_fidelity, ContentFidelity.MATCHED)
        self.assertEqual(result.fidelity.semantic_relation, "not_assessed")
        self.assertFalse(result.eligibility_established)
        self.assertGreater(item.locator.start, TEXT.index(QUOTE))
        before = snapshot(self.f)
        restart(self.root, self.f, self.expected)
        self.assertEqual(snapshot(self.f), before)

    def test_quote_mismatch_is_resolved_but_not_faithful(self):
        self.persist()
        result = read(self.root, self.f, self.expected, quote="Factuur 1150 EUR")
        self.assertEqual(result.fidelity.citation_resolution, CitationResolution.RESOLVED)
        self.assertEqual(result.fidelity.content_fidelity, ContentFidelity.MISMATCHED)
        self.assertFalse(result.eligibility_established)

    def test_stale_identity_and_foreign_case_do_not_relocate_matching_text(self):
        self.persist()
        other = seed(data=DATA)
        foreign = parent(other)
        vault = coordinator(self.root, other)
        begin(vault, other)
        vault.upload(scope=other.scope, intent_id=other.intent, data=DATA)
        persist_fixture(other, foreign, anchor(foreign))
        self.assertEqual(read(self.root, other, foreign).fidelity.content_fidelity, ContentFidelity.MATCHED)
        before = snapshot(self.f)
        for changed in (
            replace(self.expected, org_id=other.scope.org_id),
            replace(self.expected, case_id=other.scope.case_id),
            replace(self.expected, version_id="v2"),
            replace(self.expected, representation_id="absent"),
            replace(self.expected, source_sha256_hex="f" * 64),
            replace(self.expected, representation_sha256_hex="f" * 64),
        ):
            with self.subTest(parent=changed), self.assertRaises(EvidenceRowNotFound):
                read(self.root, self.f, changed)
        # Equal bytes in another source cannot substitute the independently
        # selected physical version. Both originals are individually available.
        with self.assertRaises((EvidenceRowNotFound, VaultMissing, VaultUnavailable)):
            read(self.root, other, self.expected, intent=other.intent)
        # Same case and digest, DIFFERENT physical document/version: scope and
        # hashes alone must not authorize swapping the selected source intent.
        sibling = replace(self.f, version=uuid4(), intent=uuid4())
        document = uuid4()
        with connect() as conn:
            conn.execute(
                "insert into caseproof.documents(id,org_id,case_id,source_label) values(%s,%s,%s,%s)",
                (document, sibling.scope.org_id, sibling.scope.case_id, "same-bytes-different-source"),
            )
            conn.execute(
                "insert into caseproof.document_versions(id,org_id,document_id,version_number,"
                "original_sha256_hex,byte_length,media_type) values(%s,%s,%s,1,%s,%s,'text/plain')",
                (sibling.version, sibling.scope.org_id, document, sibling.digest, len(DATA)),
            )
        sibling_vault = coordinator(self.root, sibling)
        begin(sibling_vault, sibling)
        sibling_vault.upload(scope=sibling.scope, intent_id=sibling.intent, data=DATA)
        after_sibling = snapshot(self.f)
        with self.assertRaises(EvidenceRowNotFound):
            read(self.root, self.f, self.expected, intent=sibling.intent)
        self.assertEqual(snapshot(self.f), after_sibling)
        self.assertEqual(after_sibling, tuple(a + b for a, b in zip(
            before, (2, 2, 2, 1, 1), strict=True,
        )))

    def test_equal_byte_representations_keep_distinct_identity(self):
        self.persist()
        second = replace(self.expected, representation_id="identity-2")
        persist_fixture(self.f, second, anchor(second, anchor_id="amount:other-representation"))
        self.assertEqual(read(self.root, self.f, self.expected).fidelity.content_fidelity, ContentFidelity.MATCHED)
        restart(self.root, self.f, second, anchor_id="amount:other-representation")
        with self.assertRaises(EvidenceRowNotFound):
            read(self.root, self.f, second)  # Original anchor belongs to identity-1.

    def test_tampered_or_missing_original_denies_resolution_and_audits_loss(self):
        self.persist()
        (self.root / self.intent.object_key).write_bytes(b"x" * len(DATA))
        before = snapshot(self.f)
        with self.assertRaises(VaultUnavailable):
            read(self.root, self.f, self.expected)
        self.assertEqual(snapshot(self.f), tuple(a + b for a, b in zip(
            before, (1, 1, 1, 1, 0), strict=True,
        )))
        # Restoring bytes cannot silently re-enable an unavailable source.
        (self.root / self.intent.object_key).write_bytes(DATA)
        with self.assertRaises(VaultUnavailable):
            read(self.root, self.f, self.expected)

    def test_unknown_parser_version_is_not_reconstructed_as_identity(self):
        self.persist(transform_version="unknown-parser")
        with self.assertRaises(StoredLocatorError):
            read(self.root, self.f, self.expected)

    def test_out_of_bounds_locator_is_not_fuzzy_repaired(self):
        persist_fixture(self.f, self.expected, anchor(self.expected, end=len(TEXT) + 1))
        with self.assertRaises(StoredLocatorError):
            read(self.root, self.f, self.expected)

    def test_metadata_audit_failure_rolls_back_graph_and_case_revision(self):
        before = snapshot(self.f)
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.persist(audit_fault=True)
        self.assertEqual(snapshot(self.f), before)
        with self.assertRaises(EvidenceRowNotFound):
            read(self.root, self.f, self.expected)
        self.persist()  # Fresh transaction can publish the exact fixture once.
        self.assertEqual(read(self.root, self.f, self.expected).fidelity.content_fidelity, ContentFidelity.MATCHED)

    def test_duplicate_anchor_rolls_back_new_representation_and_audit(self):
        self.persist()
        before = snapshot(self.f)
        second = replace(self.expected, representation_id="must-rollback")
        with self.assertRaises(psycopg.errors.UniqueViolation):
            persist_fixture(self.f, second, anchor(second))
        self.assertEqual(snapshot(self.f), before)
        with connect() as conn:
            count = conn.execute(
                "select count(*) from caseproof.s2_008a_representations "
                "where org_id=%s and case_id=%s and kernel_representation_id=%s",
                (self.f.scope.org_id, self.f.scope.case_id, second.representation_id),
            ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_bound_representation_cannot_be_rewritten_or_read_by_client_role(self):
        self.persist()
        with self.assertRaises(psycopg.Error), connect() as conn:
            conn.execute(
                "update caseproof.s2_008a_representations set transform_version='forged' "
                "where org_id=%s and case_id=%s", (self.f.scope.org_id, self.f.scope.case_id),
            )
        with self.assertRaises(psycopg.errors.InsufficientPrivilege), connect() as conn:
            conn.execute("set local role authenticated")
            conn.execute("select representation_pk from caseproof.s2_008a_representations limit 1")
        self.assertEqual(read(self.root, self.f, self.expected).fidelity.content_fidelity, ContentFidelity.MATCHED)


def recover(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    fields = payload["parent"]
    fields["org_id"], fields["case_id"] = UUID(fields["org_id"]), UUID(fields["case_id"])
    expected = ExpectedEvidenceParent(**fields)
    fixture = Fixture(
        VaultScope(expected.org_id, expected.case_id), UUID(payload["actor"]),
        UUID(payload["version"]), UUID(payload["intent"]), DATA,
    )
    result = read(Path(payload["root"]), fixture, expected, anchor_id=payload["anchor"])
    if (result.source.content != DATA or result.representation.content != DATA
            or result.fidelity.content_fidelity != ContentFidelity.MATCHED
            or result.fidelity.anchor.locator != TextSpan(TEXT.rindex(QUOTE), TEXT.rindex(QUOTE) + len(QUOTE))
            or result.eligibility_established):
        raise AssertionError("Restart did not preserve exact versioned evidence")
    print("TEXT_ANCHOR_RESTART_PASSED")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--recover":
        recover(sys.argv[2])
    else:
        unittest.main(verbosity=2)
