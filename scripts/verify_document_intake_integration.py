"""Real private bytes + disposable PostgreSQL + real parsers, SCRIPTED inference.

Run after verify_extraction_integration. Synthetic identity is not genuine Auth
or production DB role binding. No Requesty call, customer document or live DDL.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID, uuid4

from application.documents.intake import DocumentIntelligence
from application.extraction.contracts import (
    ExtractionConfig,
    ExtractionError,
    ProviderReply,
    Scope,
    decode,
    digest,
)
from apps.api.access_control import AccessRejected, CaseAccessService, InvalidBearer, VerifiedSubject
from apps.api.authenticated_document_intelligence import AuthenticatedDocumentIntelligence, StoredDocument
from apps.api.disposable_extraction_journal import DisposablePostgresJournal
from apps.api.evidence_vault_protocol import VaultUnavailable
from apps.api.postgres_case_repository import PostgresCaseAccessRepository
from domains.finance.extraction_rules import FinanceEvidencePolicy
from evals.document_corpus import CASES
from infrastructure.parsers.limited import LimitedDocumentParser
from packages.evidence_kernel.domain.source_versions import SourceVersion
from scripts.extraction_fixtures import NOW, ScriptedProvider, envelope
from scripts.verify_vault_integration import Fixture, begin, connect, coordinator, seed


class SyntheticVerifier:
    def __init__(self, actor):
        self.actor = actor

    def verify_bearer(self, token):
        if token != "synthetic-fixture-only":
            raise InvalidBearer("invalid fixture token")
        return VerifiedSubject(
            str(self.actor), "synthetic-issuer", "authenticated", NOW, NOW + timedelta(hours=1), False
        )


class Catalog:
    def __init__(self, fixtures, cases):
        self.fixtures, self.cases = fixtures, cases

    def list_sources(self, authorized):
        result = []
        with connect() as conn:
            for f, case in zip(self.fixtures, self.cases, strict=True):
                row = conn.execute(
                    "select v.document_id,v.original_sha256_hex,v.ingested_at,v.media_type "
                    "from caseproof.document_versions v join caseproof.documents d "
                    "on d.org_id=v.org_id and d.id=v.document_id "
                    "join caseproof._s2_009b_vault_intents i on i.org_id=d.org_id and i.case_id=d.case_id "
                    "and i.document_id=d.id and i.document_version_id=v.id "
                    "where d.org_id=%s and d.case_id=%s and v.id=%s and i.intent_id=%s and i.state='verified'",
                    (authorized.org_id, authorized.case_id, f.version, f.intent),
                ).fetchone()
                if row is None:
                    raise ExtractionError("scoped fixture source unavailable")
                result.append(
                    StoredDocument(
                        case.case_id,
                        SourceVersion(str(row[0]), str(f.version), row[1], f.data, row[2], row[3]),
                        f.intent,
                    )
                )
        return tuple(result)


class CorpusProvider(ScriptedProvider):
    def complete(self, system, payload, *, request_id, max_tokens):
        self.calls.append(request_id)
        data = decode(payload)
        atoms = []
        for src in data["sources"]:
            case = next(c for c in CASES if c.case_id == src["id"])
            atoms.append(
                {
                    "entity_id": "E1",
                    "source_id": case.case_id,
                    "quote": case.quote,
                    "statement": "Synthetic observed text proposal",
                    "slot": case.signal,
                    "signal": case.signal,
                    "value": case.value,
                    "polarity": case.polarity,
                    "relation": "supports",
                }
            )
        return ProviderReply(envelope(atoms), self.identity, self.model)


def provision(root, case=CASES[0]):
    f = seed(data=case.captured().source.content, media_type=case.media_type)
    with connect() as conn:
        conn.execute(
            "update caseproof.organization_members set actions=array['case:read','evidence:read','finding:write'] "
            "where org_id=%s and user_id=%s",
            (f.scope.org_id, f.actor),
        )
    vault = coordinator(root, f)
    begin(vault, f)
    vault.upload(scope=f.scope, intent_id=f.intent, data=f.data)
    return f


def extra_source(root, base, case):
    raw = case.captured().source.content
    f = Fixture(base.scope, base.actor, uuid4(), uuid4(), raw, case.media_type)
    document = uuid4()
    with connect() as conn:
        conn.execute(
            "insert into caseproof.documents(id,org_id,case_id,source_label) values(%s,%s,%s,%s)",
            (document, f.scope.org_id, f.scope.case_id, "synthetic-multisource"),
        )
        conn.execute(
            "insert into caseproof.document_versions(id,org_id,document_id,version_number,original_sha256_hex,"
            "byte_length,media_type) values(%s,%s,%s,1,%s,%s,%s)",
            (f.version, f.scope.org_id, document, sha256(raw).hexdigest(), len(raw), f.media_type),
        )
    vault = coordinator(root, f)
    begin(vault, f)
    vault.upload(scope=f.scope, intent_id=f.intent, data=f.data)
    return f


def adapter(root, fixtures, cases, *, provider=None, parser=None, actor=None):
    first = fixtures[0]
    acting = actor or first.actor
    access = CaseAccessService(
        SyntheticVerifier(acting),
        PostgresCaseAccessRepository(connect),
        "synthetic-issuer",
        "authenticated",
        lambda: NOW,
    )
    provider = provider or CorpusProvider()
    return AuthenticatedDocumentIntelligence(
        access,
        Catalog(fixtures, cases),
        lambda _: coordinator(root, first),
        lambda _: DocumentIntelligence(
            parser or LimitedDocumentParser(),
            provider,
            DisposablePostgresJournal(connect, actor_id=acting),
            FinanceEvidencePolicy(),
        ),
    )


def run(service, fixture, cases=(CASES[0],)):
    return service.run(
        bearer="synthetic-fixture-only",
        case_id=str(fixture.scope.case_id),
        run_id="document-integration-v1",
        assignments=tuple(c.assignment for c in cases),
        slots=tuple(c.slot for c in cases),
        config=ExtractionConfig(repair_passes=0),
    )


class Integration(unittest.TestCase):
    def test_three_formats_share_one_preserved_case_and_extraction_runtime(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            cases = CASES[:3]
            f = provision(root, cases[0])
            fixtures = (f, *(extra_source(root, f, c) for c in cases[1:]))
            provider = CorpusProvider()
            result = run(adapter(root, fixtures, cases, provider=provider), f, cases)
            self.assertEqual(result.status, "review_required")
            self.assertEqual(len(result.documents), 3)
            self.assertEqual(len(provider.calls), 4)
            self.assertFalse(result.approved)
            self.assertEqual(
                {d.evidence.source.media_type for d in result.documents},
                {"application/pdf", "application/xml", "message/rfc822"},
            )
            for record, parsed in zip(fixtures, result.documents, strict=True):
                self.assertEqual(
                    coordinator(root, record).read(scope=record.scope, intent_id=record.intent),
                    parsed.evidence.source.content,
                )

    def test_full_document_flow_replays_after_separate_process_restart(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            f = provision(root)
            result = run(adapter(root, (f,), (CASES[0],)), f)
            manifest = root / "synthetic-recovery.json"
            manifest.write_text(
                json.dumps(
                    {
                        "org": str(f.scope.org_id),
                        "case": str(f.scope.case_id),
                        "actor": str(f.actor),
                        "version": str(f.version),
                        "intent": str(f.intent),
                    }
                )
            )
            child = subprocess.run(
                [sys.executable, "-m", "scripts.verify_document_intake_integration", "--recover", str(root)],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            self.assertEqual(child.stdout.strip(), digest(json.loads(result.extraction.to_json())))

    def test_foreign_actor_and_revoked_membership_fail_before_parser_or_model(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            f, other = provision(root), seed()
            provider = CorpusProvider()
            with self.assertRaises(AccessRejected):
                run(adapter(root, (f,), (CASES[0],), actor=other.actor, provider=provider), f)
            with connect() as conn:
                conn.execute(
                    "update caseproof.organization_members set active=false where org_id=%s and user_id=%s",
                    (f.scope.org_id, f.actor),
                )
            with self.assertRaises(AccessRejected):
                run(adapter(root, (f,), (CASES[0],), provider=provider), f)
            self.assertEqual(provider.calls, [])

    def test_corrupt_original_denies_cached_normalization_and_extraction(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            f = provision(root)
            provider = CorpusProvider()
            service = adapter(root, (f,), (CASES[0],), provider=provider)
            run(service, f)
            intent = begin(coordinator(root, f), f)
            (root / intent.object_key).write_bytes(b"tampered")
            with self.assertRaises((VaultUnavailable, ExtractionError)):
                run(service, f)
            self.assertEqual(len(provider.calls), 2)

    def test_normalization_audit_failure_does_not_commit_artifact_or_call_model(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            f = provision(root)

            class BrokenEvent(DisposablePostgresJournal):
                def _event(self, conn, keys, revision, state, payload):
                    if keys[-1].startswith("normalize:") and revision == 2:
                        raise RuntimeError("synthetic audit outage")
                    return super()._event(conn, keys, revision, state, payload)

            provider = CorpusProvider()
            service = DocumentIntelligence(
                LimitedDocumentParser(),
                provider,
                BrokenEvent(connect, actor_id=f.actor),
                FinanceEvidencePolicy(),
            )
            document = Catalog((f,), (CASES[0],)).list_sources(
                type("Context", (), {"org_id": str(f.scope.org_id), "case_id": str(f.scope.case_id)})()
            )[0]
            from application.documents.intake import CapturedDocument

            with self.assertRaises(RuntimeError):
                service.run(
                    scope=Scope(f.scope.org_id, f.scope.case_id),
                    run_id="audit",
                    documents=(CapturedDocument(document.source_id, document.original),),
                    assignments=(CASES[0].assignment,),
                    slots=(CASES[0].slot,),
                )
            with connect() as conn:
                row = conn.execute(
                    "select state,payload from caseproof._ei_steps where org_id=%s and run_id='audit' "
                    "and step_id like 'normalize:%%'",
                    (f.scope.org_id,),
                ).fetchone()
            self.assertEqual(row, ("prepared", None))
            self.assertEqual(provider.calls, [])

    def test_unprocessed_email_part_blocks_calls_with_durable_incomplete_artifact(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            email_case = replace(CASES[2], case_id="supplier")
            raw = b"Content-Type: text/html\r\n\r\n<p>Unprocessed supplier claim</p>"
            f = seed(data=raw, media_type="message/rfc822")
            with connect() as conn:
                conn.execute(
                    "update caseproof.organization_members set actions=array['case:read','evidence:read','finding:write'] "
                    "where org_id=%s and user_id=%s",
                    (f.scope.org_id, f.actor),
                )
            vault = coordinator(root, f)
            begin(vault, f)
            vault.upload(scope=f.scope, intent_id=f.intent, data=f.data)
            provider = CorpusProvider()
            result = run(adapter(root, (f,), (email_case,), provider=provider), f, (email_case,))
            self.assertEqual(result.status, "blocked")
            self.assertEqual(provider.calls, [])
            self.assertFalse(result.documents[0].evidence.complete)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--recover":
        from apps.api.evidence_vault_protocol import VaultScope

        root = Path(sys.argv[2])
        data = json.loads((root / "synthetic-recovery.json").read_text())
        f = Fixture(
            VaultScope(UUID(data["org"]), UUID(data["case"])),
            UUID(data["actor"]),
            UUID(data["version"]),
            UUID(data["intent"]),
            CASES[0].captured().source.content,
            "application/pdf",
        )

        class NoParse(LimitedDocumentParser):
            def parse(self, source):
                raise AssertionError("restart must use preserved parser artifact")

        class NoInference(CorpusProvider):
            def complete(self, *args, **kwargs):
                raise AssertionError("restart must use saved extraction response")

        result = run(adapter(root, (f,), (CASES[0],), provider=NoInference(), parser=NoParse()), f)
        print(digest(json.loads(result.extraction.to_json())))
        return
    if len(sys.argv) != 1:
        raise SystemExit("unsupported disposable integration arguments")
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(Integration)
    )
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
