"""Adversarial disposable PostgreSQL test of uninstalled DOCX review/commit SQL.

Synthetic SQL-only fixtures. Not a live signed Supabase/Word test and does not
authorize applying the proposal to caseproof-dev or customer deployments.
"""
from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from scripts.verify_retention_disposable import main as install
from scripts.verify_s2_002_database import ROOT, _env, _run


def main() -> None:
    install()
    env = _env()
    proposal = ROOT / "docs/security/DOCX_EDITOR_DOCUMENT_SCOPE_SQL_PROPOSAL.sql"
    _run(proposal.read_text(encoding="utf-8"), env)
    actor, other, org, case = [str(uuid4()) for _ in range(4)]
    docs = [str(uuid4()) for _ in range(4)]
    versions = [str(uuid4()) for _ in range(4)]
    _run(f"""
insert into auth.users(id,instance_id) values('{actor}','{org}'),('{other}','{org}');
insert into caseproof.organizations(id,display_name) values('{org}','Synthetic editor');
insert into caseproof.organization_members(org_id,user_id,actions) values
('{org}','{actor}',array['case:read','evidence:read','finding:write','review:request','draft:edit']),
('{org}','{other}',array['case:read','evidence:read','finding:write','review:request']);
insert into caseproof.cases(id,org_id,created_by_user,effective_policy_version)
values('{case}','{org}','{actor}','caseproof-dev-txt-v1');
insert into caseproof._m1_matter_grants(org_id,case_id,user_id,role,permissions)
values('{org}','{case}','{actor}','reviewer',
array['case:read','evidence:read','evidence:upload','draft:check','review:request','draft:edit']);
""", env)
    sources = []
    for doc, version, role in zip(
        docs, versions, ("draft", "inventory", "exhibit", "exhibit"), strict=True
    ):
        media = ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                 if role == "draft" else "application/pdf")
        _run(f"""
insert into caseproof.documents(id,org_id,case_id,source_label)
values('{doc}','{org}','{case}','{role}');
insert into caseproof.document_versions(
id,org_id,document_id,version_number,original_sha256_hex,byte_length,media_type,bundle_role)
values('{version}','{org}','{doc}',1,repeat('a',64),30000,'{media}','{role}');
""", env)
        sources.append(dict(
            role=role, filename=role, document_id=doc, version_id=version,
            sha256="a" * 64, byte_length=30000, media_type=media
        ))
    payload = json.dumps(dict(case_id=case, sources=sources))
    _run(
        "insert into caseproof._dev_journey_operations"
        "(org_id,actor_id,operation,request_id,input_sha,response)"
        f" values('{org}','{actor}','bundle_register','{uuid4()}',repeat('a',64),"
        f"'{payload}'::jsonb);",
        env,
    )

    def call(function: str, args: list[str], *, who: str = actor,
             service: bool = False, succeeds: bool = True) -> str:
        role = "service_role" if service else "authenticated"
        vals = ",".join("'" + str(v).replace("'", "''") + "'" for v in args)
        return _run(
            f"begin; set local role {role};"
            f"set local request.jwt.claim.sub='{who}';"
            f"set local request.jwt.claims='{{\"role\":\"{role}\"}}';"
            f"select public.{function}({vals}); commit;",
            env, should_pass=succeeds,
        )

    context = json.loads(call("caseproof_dossier", [case, "context", "{}"]))
    confirm_id = str(uuid4())
    call("caseproof_dossier", [
        case, "confirm", json.dumps(dict(
            bundle_signature=context["bundle_signature"],
            request_id=confirm_id,
            payload=dict(inventory_complete=True, entries=[]),
        ))
    ])
    report = dict(
        case_id=case, brief_id=versions[0],
        bundle_signature=context["bundle_signature"],
        confirmation_id=confirm_id,
        findings=[dict(reference_id="ref-0000", technical_check="checked")],
    )
    serial = json.dumps(report, sort_keys=True)
    snapshot = hashlib.sha256(serial.encode()).hexdigest()
    call("caseproof_dossier", [
        case, "snapshot", json.dumps(dict(snapshot_hash=snapshot, serialized=serial))
    ])
    review_id, request_id, missing_id = [str(uuid4()) for _ in range(3)]
    command_sha = "b" * 64
    candidate_sha = "c" * 64
    review = dict(
        original_sha256="a" * 64, command_sha256=command_sha,
        candidate_sha256=candidate_sha,
        rationale="I inspected the entire synthetic document candidate.",
    )
    values = dict(
        original_sha256="a" * 64, command_sha256=command_sha,
        candidate_sha256=candidate_sha, byte_length=40000,
    )
    review_args = [case, versions[0], snapshot, review_id, json.dumps(review)]
    reserve_args = [
        case, versions[0], snapshot, request_id, review_id, json.dumps(values)
    ]
    # Cannot reserve without a review, or by another matter reader without grants.
    call("caseproof_dossier_document_edit_reserve", reserve_args, succeeds=False)
    call("caseproof_dossier_document_edit_review", review_args, who=other, succeeds=False)
    assert _run(
        f"select count(*) from caseproof.dossier_document_edit_reviews"
        f" where case_id='{case}';", env
    ) == "0"
    # Audit failure atomically rolls the review operation back.
    _run(
        "create function caseproof.fail_document_review_audit() returns trigger"
        " language plpgsql as $$ begin if new.action='dossier_document_edit_reviewed'"
        " then raise exception 'forced audit denial'; end if; return new; end $$;"
        "create trigger fail_document_edit_audit before insert on caseproof.audit_events"
        " for each row execute function caseproof.fail_document_review_audit();",
        env,
    )
    call("caseproof_dossier_document_edit_review", review_args, succeeds=False)
    assert _run(
        f"select count(*) from caseproof.dossier_document_edit_reviews"
        f" where case_id='{case}';", env
    ) == "0"
    _run("drop trigger fail_document_edit_audit on caseproof.audit_events;", env)
    reviewed = json.loads(call("caseproof_dossier_document_edit_review", review_args))
    assert reviewed["review_request_id"] == review_id and reviewed["state"] == "reviewed"
    assert json.loads(call("caseproof_dossier_document_edit_review", review_args))["replayed"] is True
    call("caseproof_dossier_document_edit_review", [
        case, versions[0], snapshot, review_id,
        json.dumps({**review, "candidate_sha256": "e" * 64}),
    ], succeeds=False)
    call("caseproof_dossier_document_edit_reserve", [
        case, versions[0], snapshot, missing_id, missing_id, json.dumps(values),
    ], succeeds=False)
    call("caseproof_dossier_document_edit_reserve", [
        case, versions[0], snapshot, request_id, review_id,
        json.dumps({**values, "candidate_sha256": "d" * 64}),
    ], succeeds=False)

    # No invented finding approval is needed: the exact reviewed document
    # command is the independent authority for this new draft reservation.
    reserved = json.loads(call("caseproof_dossier_document_edit_reserve", reserve_args))
    assert reserved["state"] == "reserved"
    assert reserved["reference_id"] == "doc-edit:" + review_id
    assert reserved["original_sha256"] == candidate_sha
    assert json.loads(call("caseproof_dossier_document_edit_reserve", reserve_args))["replayed"] is True
    assert json.loads(call("caseproof_dossier_draft_reserve", [
        case, request_id, "status", json.dumps({"command_sha256": command_sha})
    ]))["state"] == "reserved"
    assert json.loads(call("caseproof_dossier", [case, "context", "{}"]))["bundle_signature"] == context["bundle_signature"]

    # Only a trusted service-role readback assertion can activate; even that
    # operation fails if the bytes/digest do not match the reserved derivative.
    activation = [actor, case, request_id, review_id, candidate_sha, "40000"]
    call("caseproof_dossier_document_edit_activate", activation, succeeds=False)
    call("caseproof_dossier_document_edit_activate", [
        actor, case, request_id, "f" * 64, "40000"
    ], service=True, succeeds=False)
    # A user whose fresh document-edit grant was revoked cannot activate a
    # reserved edit despite retaining every ordinary citation-review permission.
    _run(
        f"update caseproof.organization_members set actions=array_remove(actions,'draft:edit')"
        f" where org_id='{org}' and user_id='{actor}';", env
    )
    call("caseproof_dossier_document_edit_activate", activation, service=True, succeeds=False)
    _run(
        f"update caseproof.organization_members set actions=array_append(actions,'draft:edit')"
        f" where org_id='{org}' and user_id='{actor}';", env
    )
    activated = json.loads(call(
        "caseproof_dossier_document_edit_activate", activation, service=True
    ))
    assert activated["state"] == "active"
    assert json.loads(call(
        "caseproof_dossier_document_edit_activate", activation, service=True
    ))["replayed"] is True
    current = json.loads(call("caseproof_dev_bundle_manifest", [case]))
    assert current["sources"][0]["version_id"] == reserved["version_id"]
    assert current["sources"][0]["version_number"] == 2
    changed = json.loads(call("caseproof_dossier", [case, "context", "{}"]))
    assert changed["bundle_signature"] != context["bundle_signature"]
    assert changed["confirmation"] is None
    # Revocation prevents further status, review and document-reservation use.
    _run(
        f"update caseproof._m1_matter_grants set active=false where case_id='{case}';", env
    )
    call("caseproof_dossier_document_edit_review", review_args, succeeds=False)
    call("caseproof_dossier_document_edit_reserve", reserve_args, succeeds=False)
    call("caseproof_dossier_draft_reserve", [
        case, request_id, "status", json.dumps({"command_sha256": command_sha})
    ], succeeds=False)
    print(
        "DOCX_DOCUMENT_REVIEW_ACTOR_SCOPE_AUDIT_ROLLBACK_RESERVE_REPLAY"
        "_ACTIVATE_RECHECK_INVALIDATION_REVOKE_PASSED",
        flush=True,
    )


if __name__ == "__main__":
    main()
