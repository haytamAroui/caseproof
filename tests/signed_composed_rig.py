"""Isolated rig for the composed signed workflow against disposable PostgreSQL.

EVIDENCE TRACK LABEL: every external boundary here is FAKE and explicit:
- fake PostgREST transport (executes the real SQL RPC proposals in a
  disposable PostgreSQL under SET ROLE authenticated / service_role);
- fake Storage (bytes held in memory, verified-intent rows inserted by the
  rig, never a real bucket);
- fake auth (bearer tokens minted by the rig, mapped to JWT claims).
It proves composition of the real Python adapters + real SQL proposals, not
live Supabase behavior, not live Auth, not Storage policy.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from psycopg import errors
from psycopg.types.json import Jsonb  # noqa: F401  (kept for adapters)

SERVICE_KEY = "sb_secret_" + "R" * 30
PUBLISHABLE_KEY = "sb_publishable_" + "R" * 24
BUCKET = "caseproof-originals-dev"


class _Response:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def read(self, limit: int = -1) -> bytes:
        return self._body if limit < 0 else self._body[:limit]


@dataclass
class FakePostgrest:
    """http.client-shaped fake: POST /rest/v1/rpc/<name> -> real SQL RPC."""

    conn: Any
    tokens: dict[str, str] = field(default_factory=dict)  # bearer -> user uuid
    calls: list[tuple[str, str]] = field(default_factory=list)  # (role, rpc)
    errors: list[str] = field(default_factory=list)  # diagnostics, never returned to callers

    def factory(self) -> Any:
        rig = self

        class _Conn:
            def request(self, method: str, path: str, body: bytes, headers: dict[str, str]) -> None:
                self._m, self._p, self._b, self._h = method, path, body, headers

            def getresponse(self) -> _Response:
                return rig._handle(self._m, self._p, self._b, self._h)

            def close(self) -> None:
                return None

        return _Conn()

    def _handle(self, method: str, path: str, body: bytes, headers: dict[str, str]) -> _Response:
        assert method == "POST" and path.startswith("/rest/v1/rpc/")
        name = path.rsplit("/", 1)[1]
        bearer = headers["Authorization"].removeprefix("Bearer ")
        if bearer == SERVICE_KEY:
            role, sub = "service_role", None
            claims = {"role": "service_role"}
        elif bearer in self.tokens:
            role, sub = "authenticated", self.tokens[bearer]
            claims = {"role": "authenticated", "sub": sub, "is_anonymous": "false"}
        else:
            return _Response(401, b'{"code":"PGRST301"}')
        args = json.loads(body.decode("utf-8"))
        self.calls.append((role, name))
        spec = self.conn.execute(
            "select p.proargnames, p.proargtypes::oid[]::regtype[]::text[]"
            " from pg_proc p join pg_namespace n on n.oid=p.pronamespace"
            " where n.nspname='public' and p.proname=%s", (name,)).fetchall()
        if len(spec) != 1:
            return _Response(404, b'{"code":"PGRST202"}')
        names, types = spec[0]
        if set(args) - set(names):
            return _Response(404, b'{"code":"PGRST202"}')
        parts, values = [], []
        for arg_name, arg_type in zip(names, types, strict=True):
            if arg_name not in args:
                continue
            value = args[arg_name]
            if arg_type in {"jsonb", "json"}:
                value = json.dumps(value, ensure_ascii=False)
            parts.append(f"{arg_name} => %s::{arg_type}")
            values.append(value)
        sql = f"select public.{name}(" + ", ".join(parts) + ")"
        try:
            with self.conn.transaction():
                self.conn.execute(
                    "select set_config('request.jwt.claims', %s, true)", (json.dumps(claims),))
                self.conn.execute(
                    "select set_config('request.jwt.claim.sub', %s, true)", (sub or "",))
                self.conn.execute(f"set local role {role}")
                result = self.conn.execute(sql, values).fetchone()[0]
                self.conn.execute("reset role")
        except errors.InsufficientPrivilege as exc:
            self.errors.append(f"{name}: 42501 {str(exc)[:200]}")
            return _Response(403, b'{"code":"42501"}')
        except errors.Error as exc:
            code = exc.sqlstate or "XX000"
            self.errors.append(f"{name}: {code} {str(exc)[:200]}")
            return _Response(400, json.dumps({"code": code}).encode())
        return _Response(200, json.dumps(result, ensure_ascii=False).encode("utf-8"))


class FakeStorageLibrary:
    """Fake signed-originals library: bytes in memory, digests re-verified."""

    def __init__(self, conn: Any, org: UUID) -> None:
        self.conn = conn
        self.org = org
        self.blobs: dict[tuple[str, str], tuple[bytes, str]] = {}

    def put(self, *, case: UUID, doc: UUID, ver: UUID, actor: UUID, data: bytes,
            media: str) -> None:
        sha = hashlib.sha256(data).hexdigest()
        self.blobs[(str(doc), str(ver))] = (data, media)
        key = f"{self.org}/{case}/{doc}/{ver}/{sha}"
        self.conn.execute(
            "insert into storage.objects(bucket_id, name) values(%s, %s)", (BUCKET, key))
        audit = uuid4()
        self.conn.execute(
            "insert into caseproof.audit_events(id, org_id, case_id, actor_type,"
            " actor_user_id, action, event_schema_version, correlation_id,"
            " input_sha256_hex) values(%s, %s, %s, 'human', %s, 'ingest', 'v1', %s, %s)",
            (audit, self.org, case, actor, uuid4(), sha))
        self.conn.execute(
            "insert into caseproof._s2_009b_vault_intents(org_id, case_id, intent_id,"
            " actor_user_id, document_id, document_version_id, object_key, sha256_hex,"
            " byte_length, media_type, state, created_audit_id, created_case_revision,"
            " last_audit_id) values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,"
            " 'verified', %s, 1, %s)",
            (self.org, case, uuid4(), actor, doc, ver, key, sha, len(data), media,
             audit, audit))

    # --- adapter surface used by composer / check store -------------------
    def source(self, *, bearer: str, case_id: str, document_id: str, version_id: str) -> Any:
        from apps.api.signed_supabase_originals import OriginalRef

        data, media = self.blobs[(str(document_id), str(version_id))]
        ref = OriginalRef(self.org, UUID(str(case_id)), UUID(str(document_id)),
                          UUID(str(version_id)), hashlib.sha256(data).hexdigest(), media)
        return ref, len(data)

    def read(self, *, bearer: str, case_id: str, document_id: str, version_id: str) -> bytes:
        return self.blobs[(str(document_id), str(version_id))][0]


def install_shims(conn: Any, root: Any, proposals: tuple[str, ...]) -> None:
    conn.execute(
        "create or replace function auth.jwt() returns jsonb language sql stable as "
        "$$ select nullif(current_setting('request.jwt.claims', true), '')::jsonb $$")
    conn.execute("create schema if not exists storage")
    conn.execute("create table if not exists storage.objects(bucket_id text, name text)")
    # Disposable DB only: earlier tests leave overloaded proposal signatures
    # behind; a clean slate keeps PostgREST-style name resolution unambiguous.
    stale = conn.execute(
        "select p.oid::regprocedure::text from pg_proc p"
        " join pg_namespace n on n.oid=p.pronamespace where n.nspname='public'"
        " and (p.proname like 'caseproof\\_signed\\_%' or p.proname like"
        " 'caseproof\\_registry\\_%')").fetchall()
    for (signature,) in stale:
        conn.execute(f"drop function {signature}")
    for name in proposals:
        conn.execute((root / f"{name}.sql").read_text(encoding="utf-8"))


def docx_without_custom_xml(paragraphs: list[str]) -> bytes:
    """python-docx's default template ships a customXml bibliography stub,
    which the fail-closed signed Word reader refuses (docx_custom_xml_unprocessed).
    Strip it so the fixture models a plain Word brief; the reader is NOT weakened."""
    import io
    import re
    import zipfile

    from docx import Document

    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    raw = io.BytesIO()
    doc.save(raw)
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw.getvalue())) as src, \
            zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            if item.filename.startswith("customXml/"):
                continue
            data = src.read(item.filename)
            if item.filename == "word/_rels/document.xml.rels":
                data = re.sub(rb"<Relationship [^>]*customXml[^>]*/>", b"", data)
            if item.filename == "[Content_Types].xml":
                data = re.sub(rb"<Override [^>]*customXml[^>]*/>", b"", data)
            dst.writestr(item.filename, data)
    return out.getvalue()
