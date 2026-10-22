"""S2-008a: test-only immutable evidence graph against REAL local PostgreSQL 17.

Requires the pre-existing S2-002 fixture seeded in disposable caseproof_s2_ci.
NO migration, remote DB writer, Auth claims or production grants. Synthetic
source/representation digests describe fixture metadata, NOT stored bytes.
"""

from __future__ import annotations

from pathlib import Path

from scripts.verify_s2_002_database import _run
from scripts.verify_s2_007_disposable_tenancy import _isolated_postgres_env

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = (
    ROOT / "db/proposals/S2-008a_disposable_representation_anchor_graph.sql"
).read_text(encoding="utf-8")
ORG = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ACTOR = "11111111-1111-4111-8111-111111111111"
CASE = "aaaaaaaa-1111-4111-8111-111111111111"
OTHER_CASE = "aaaaaaaa-2121-4121-8121-aaaaaaaaaaaa"
DOC = "aaaaaaaa-3333-4333-8333-333333333333"
VERSION = "aaaaaaaa-5555-4555-8555-555555555555"
REP1 = "aaaaaaaa-9001-4001-8001-aaaaaaaaaaaa"
REP2 = "aaaaaaaa-9002-4002-8002-aaaaaaaaaaaa"
ANCHOR = "aaaaaaaa-a001-4a01-8a01-aaaaaaaaaaaa"
AUDITS = [
    f"aaaaaaaa-7{i:03d}-4{i:03d}-8{i:03d}-aaaaaaaaaaaa"
    for i in range(1, 9)
]


def _audit(i: int) -> str:
    return AUDITS[i - 1]


def _assert_sql_rejected(env: dict[str, str], sql: str, context: str) -> None:
    _run(sql, env, should_pass=False)
    print(f"S2-008a {context}: PASS")


def main() -> None:
    env = _isolated_postgres_env()
    if _run(
        f"select count(*)::text from caseproof.document_versions where id='{VERSION}';",
        env,
    ) != "1":
        raise RuntimeError("Only the fresh S2-002 disposable database is supported")
    if _run("select to_regclass('caseproof.s2_008a_anchors') is null;", env) != "t":
        raise RuntimeError("Expected fresh disposable S2-008a schema")
    _run(SCHEMA, env)
    print("S2-008a additive disposable schema: PASS")

    audit_values = ",".join(
        "("
        + f"'{event}','{ORG}','{CASE}','human','{ACTOR}',"
        + f"'s2_008a_test_append','s2-008a-fixture-v1',gen_random_uuid(),repeat('a',64)"
        + ")"
        for event in AUDITS
    )
    fixture = f"""
begin;
insert into caseproof.audit_events(
 id,org_id,case_id,actor_type,actor_user_id,action,
 event_schema_version,correlation_id,input_sha256_hex
) values {audit_values};
insert into caseproof.s2_008a_source_logical_ids(
 org_id,case_id,document_pk,kernel_document_id,audit_event_id
) values ('{ORG}','{CASE}','{DOC}','invoice/source-A','{_audit(1)}');
insert into caseproof.s2_008a_version_logical_ids(
 org_id,case_id,document_pk,version_pk,kernel_version_id,source_sha256_hex,audit_event_id
) values ('{ORG}','{CASE}','{DOC}','{VERSION}','v1',repeat('a',64),'{_audit(2)}');
insert into caseproof.s2_008a_representations(
 representation_pk,org_id,case_id,document_pk,version_pk,kernel_version_id,
 kernel_representation_id,source_sha256_hex,representation_sha256_hex,
 media_type,transform_name,transform_version,transform_config_sha256,
 coordinate_convention,audit_event_id
) values
 ('{REP1}','{ORG}','{CASE}','{DOC}','{VERSION}','v1',
  'ocr-1',repeat('a',64),repeat('c',64),'text/plain',
  'test-parser','1',repeat('f',64),'unicode_codepoint_zero_based_half_open','{_audit(3)}'),
 ('{REP2}','{ORG}','{CASE}','{DOC}','{VERSION}','v1',
  'ocr-2',repeat('a',64),repeat('c',64),'text/plain',
  'test-parser','2',repeat('f',64),'unicode_codepoint_zero_based_half_open','{_audit(4)}');
insert into caseproof.s2_008a_layouts(
 org_id,case_id,representation_pk,layout_kind,layout_schema_version,
 layout_manifest,layout_sha256_hex,audit_event_id
) values
 ('{ORG}','{CASE}','{REP1}','text','krn102-layout-v1',
  '{{"normalization":"none","codepoints":10}}'::jsonb,repeat('d',64),'{_audit(5)}'),
 ('{ORG}','{CASE}','{REP2}','text','krn102-layout-v1',
  '{{"normalization":"none","codepoints":10}}'::jsonb,repeat('d',64),'{_audit(6)}');
insert into caseproof.s2_008a_anchors(
 anchor_pk,org_id,case_id,kernel_anchor_id,document_pk,version_pk,representation_pk,
 source_sha256_hex,representation_sha256_hex,locator_kind,locator_schema_version,
 locator,audit_event_id
) values
 ('{ANCHOR}','{ORG}','{CASE}','span:1','{DOC}','{VERSION}','{REP1}',
  repeat('a',64),repeat('c',64),'text_span','krn102-locator-v1',
  '{{"start":0,"end":10,"encoding":"utf-8","normalization":"none"}}'::jsonb,'{_audit(7)}');
commit;
"""
    _run(fixture, env)
    if _run(
        "select count(*)::text from caseproof.s2_008a_representations "
        f"where org_id='{ORG}' and case_id='{CASE}' "
        "and representation_sha256_hex=repeat('c',64)", env
    ) != "2":
        raise AssertionError("Equal-byte representations must preserve TWO distinct IDs")
    if _run(
        "select kernel_document_id||'|'||kernel_version_id||'|'||kernel_representation_id "
        "from caseproof.s2_008a_anchors a "
        "join caseproof.s2_008a_representations r using(representation_pk) "
        "join caseproof.s2_008a_version_logical_ids v "
        " on v.version_pk=a.version_pk and v.org_id=a.org_id and v.case_id=a.case_id "
        "join caseproof.s2_008a_source_logical_ids s "
        " on s.document_pk=a.document_pk and s.org_id=a.org_id and s.case_id=a.case_id "
        f"where a.anchor_pk='{ANCHOR}'", env
    ) != "invoice/source-A|v1|ocr-1":
        raise AssertionError("Kernel logical IDs did not survive exact DB round-trip")
    print("S2-008a opaque IDs and equal digest distinct representations: PASS")

    # Same tenant, DIFFERENT case: server scope must not allow parent-pointer
    # swapping even when the tenant-level org_id is unchanged.
    _run(
        "insert into caseproof.cases(id,org_id,created_by_user,effective_policy_version) "
        f"values('{OTHER_CASE}','{ORG}','{ACTOR}','test-v1')", env,
    )
    _assert_sql_rejected(env, f"""
insert into caseproof.s2_008a_source_logical_ids(
 org_id,case_id,document_pk,kernel_document_id,audit_event_id
) values ('{ORG}','{OTHER_CASE}','{DOC}','forged-cross-case','{_audit(1)}');
""", "same-tenant cross-case composite FK")
    _assert_sql_rejected(env, f"""
insert into caseproof.s2_008a_representations(
 representation_pk,org_id,case_id,document_pk,version_pk,kernel_version_id,
 kernel_representation_id,source_sha256_hex,representation_sha256_hex,
 media_type,transform_name,transform_version,transform_config_sha256,
 coordinate_convention,audit_event_id
) values (
 gen_random_uuid(),'{ORG}','{CASE}','{DOC}','{VERSION}','v1',
 'invalid-source-hash',repeat('b',64),repeat('c',64),'text/plain',
 'test-parser','3',repeat('f',64),'unicode_codepoint_zero_based_half_open','{_audit(8)}');
""", "stale original-byte fingerprint FK")
    _assert_sql_rejected(env, f"""
insert into caseproof.s2_008a_anchors(
 anchor_pk,org_id,case_id,kernel_anchor_id,document_pk,version_pk,representation_pk,
 source_sha256_hex,representation_sha256_hex,locator_kind,locator_schema_version,locator,audit_event_id
) values (
 gen_random_uuid(),'{ORG}','{OTHER_CASE}','forged','{DOC}','{VERSION}','{REP1}',
 repeat('a',64),repeat('c',64),'text_span','krn102-locator-v1','{{}}'::jsonb,'{_audit(8)}');
""", "foreign case anchor denied")

    # The external object store and exact bytes are NOT yet present. Prove
    # that metadata row insert has mandatory audit relationship and that
    # a failed schema insert automatically rolls back its own fresh audit.
    stray_audit = "aaaaaaaa-7999-4999-8999-aaaaaaaaaaaa"
    fail_tx = f"""
begin;
insert into caseproof.audit_events(
 id,org_id,case_id,actor_type,actor_user_id,action,
 event_schema_version,correlation_id,input_sha256_hex
) values ('{stray_audit}','{ORG}','{CASE}','human','{ACTOR}',
 'aborted-evidence-append','test-v1',gen_random_uuid(),repeat('a',64));
insert into caseproof.s2_008a_source_logical_ids(
 org_id,case_id,document_pk,kernel_document_id,audit_event_id
) values ('{ORG}','{CASE}','{DOC}','duplicate-physical-source','{stray_audit}');
commit;
"""
    _assert_sql_rejected(env, fail_tx, "aborted append transaction")
    if _run(
        f"select count(*)::text from caseproof.audit_events where id='{stray_audit}';", env
    ) != "0":
        raise AssertionError("Aborted evidence insert committed an orphan audit event")
    _assert_sql_rejected(env, f"""
insert into caseproof.s2_008a_anchors(
 anchor_pk,org_id,case_id,kernel_anchor_id,document_pk,version_pk,representation_pk,
 source_sha256_hex,representation_sha256_hex,locator_kind,locator_schema_version,locator,audit_event_id
) values (
 gen_random_uuid(),'{ORG}','{CASE}','no-audit','{DOC}','{VERSION}','{REP1}',
 repeat('a',64),repeat('c',64),'text_span','krn102-locator-v1','{{}}'::jsonb,
 'aaaaaaaa-7998-4998-8998-aaaaaaaaaaaa');
""", "missing trusted audit FK")
    _assert_sql_rejected(
        env,
        "update caseproof.s2_008a_representations set kernel_representation_id='mutated' "
        f"where representation_pk='{REP1}';",
        "append-only update denied",
    )
    _assert_sql_rejected(
        env,
        f"delete from caseproof.s2_008a_anchors where anchor_pk='{ANCHOR}';",
        "append-only delete denied",
    )
    # No client-facing write or read grants: authenticating a user does NOT
    # grant automatic ability to query evidence. This is deliberate.
    _assert_sql_rejected(
        env,
        "set role authenticated; "
        "select count(*) from caseproof.s2_008a_representations;",
        "authenticated role cannot read unapproved graph",
    )
    print("S2-008a_DISPOSABLE_EVIDENCE_GRAPH_CONTRACT_PASSED")


if __name__ == "__main__":
    main()
