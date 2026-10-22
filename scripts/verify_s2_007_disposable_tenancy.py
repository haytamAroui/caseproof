"""S2-007: genuine Auth-to-disposable-Postgres RLS integration (opt-in).

This is NOT a production database connector. Real Supabase Auth verifies
user A/B; a fresh per-run pseudonym maps each verified subject to a fixture
in an ephemeral PostgreSQL 17 instance. PostgreSQL tests actual RLS with
SIMULATED claim binding, never remote Supabase Postgres identity propagation.

Only localhost caseproof_s2_ci, explicit disposable flag, and an ephemeral
postgres superuser are accepted. Nothing is written to caseproof-dev. No
credentials, bearer, source subject UUIDs or SQL are printed on failure.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sys
from uuid import UUID

from apps.api.live_auth_probe import run_live_auth_probe
from apps.api.supabase_auth_verifier import (
    HttpsSupabaseUserLookup,
    SupabaseAuthUserVerifier,
)
from apps.api.supabase_password_signin import PasswordCredentials, SupabasePasswordSignin
from scripts.verify_s2_002_database import MIGRATION, PROPOSAL_PATH, SCHEMA_BOOTSTRAP, _env, _run
from scripts.verify_s2_006_live_auth import PROJECT_REF

ORG_A = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
ORG_B = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
CASE_A = "cccccccc-1111-4111-8111-111111111111"
CASE_B = "dddddddd-2222-4222-8222-222222222222"
DOC_A = "cccccccc-3333-4333-8333-333333333333"
DOC_B = "dddddddd-4444-4444-8444-444444444444"
VER_A = "cccccccc-5555-4555-8555-555555555555"
VER_B = "dddddddd-6666-4666-8666-666666666666"


def _as_uuid(value: str) -> UUID:
    parsed = UUID(value)
    if parsed.int == 0:
        raise ValueError("Nil subject not allowed")
    return parsed


def pseudonymous_fixture_subjects(
    original_a: str, original_b: str, *, nonce: bytes,
) -> tuple[str, str]:
    """Randomized, nonreversible per-run aliases; never print Auth subjects."""
    a, b = _as_uuid(original_a), _as_uuid(original_b)
    if a == b or len(nonce) < 32:
        raise ValueError("Distinct subjects and a strong per-run nonce required")

    def alias(identity: UUID) -> str:
        digest = hmac.new(nonce, identity.bytes, hashlib.sha256).digest()
        return str(UUID(bytes=digest[:16], version=4))

    first, second = alias(a), alias(b)
    if first == second:
        raise AssertionError("Unexpected test pseudonym collision")
    return first, second


def _bootstrap(env: dict[str, str]) -> None:
    if MIGRATION.read_bytes() != PROPOSAL_PATH.read_bytes():
        raise RuntimeError("Review-approved schema and canonical migration differ")
    state = _run("select coalesce(to_regclass('caseproof.cases')::text, 'absent');", env)
    if state == "absent":
        # An empty localhost-only CI service. This must NEVER target Supabase.
        _run("BEGIN;\n" + SCHEMA_BOOTSTRAP + MIGRATION.read_text(encoding="utf-8")
             + "\nCOMMIT;", env)
    elif state != "caseproof.cases":
        raise AssertionError("Unexpected disposable database schema")


def _fixture_sql(subject_a: str, subject_b: str) -> str:
    # Only UUID values, strictly normalized from a successful Auth probe or
    # explicitly synthetic CI fixture. No SQL supplied from user requests.
    a, b = str(_as_uuid(subject_a)), str(_as_uuid(subject_b))
    return f"""
begin;
insert into auth.users(id,instance_id) values
 ('{a}','00000000-0000-4000-8000-000000000001'),
 ('{b}','00000000-0000-4000-8000-000000000001');
insert into caseproof.organizations(id,display_name) values
 ('{ORG_A}','Fixture tenant A'),('{ORG_B}','Fixture tenant B');
insert into caseproof.organization_members(org_id,user_id,actions) values
 ('{ORG_A}','{a}',array['case:read','evidence:read']::text[]),
 ('{ORG_B}','{b}',array['case:read','evidence:read']::text[]);
insert into caseproof.cases(id,org_id,created_by_user,effective_policy_version) values
 ('{CASE_A}','{ORG_A}','{a}','test-v1'),
 ('{CASE_B}','{ORG_B}','{b}','test-v1');
insert into caseproof.documents(id,org_id,case_id,source_label) values
 ('{DOC_A}','{ORG_A}','{CASE_A}','synthetic-A'),
 ('{DOC_B}','{ORG_B}','{CASE_B}','synthetic-B');
insert into caseproof.document_versions(
 id,org_id,document_id,version_number,original_sha256_hex,byte_length,media_type
) values
 ('{VER_A}','{ORG_A}','{DOC_A}',1,repeat('a',64),10,'text/plain'),
 ('{VER_B}','{ORG_B}','{DOC_B}',1,repeat('b',64),10,'text/plain');
commit;
"""


def _session_sql(
    alias: str, own_case: str, other_case: str, *,
    expected_own: int = 1,
    claim: bool = True,
) -> str:
    subject = str(_as_uuid(alias))
    own, other = str(_as_uuid(own_case)), str(_as_uuid(other_case))
    # BEGIN + SET LOCAL means a single transaction owns its claim and role,
    # never a connection-global principal. This is a policy simulation, NOT
    # signature verification by Postgres.
    assign = (
        f"perform set_config('request.jwt.claim.sub','{subject}',true);"
        if claim else ""
    )
    expected_inventory = expected_own
    return f"""
begin;
set local role authenticated;
do $probe$
begin
 {assign}
 if (select count(*) from caseproof.cases where id='{own}') <> {expected_own}
    or (select count(*) from caseproof.cases where id='{other}') <> 0
    or (select count(*) from caseproof.documents where case_id='{own}')
        <> {expected_inventory}
    or (select count(*) from caseproof.document_versions where
        document_id in (select id from caseproof.documents where case_id='{own}'))
        <> {expected_inventory}
 then
   raise exception 'S2-007 own/foreign isolation invariant violated';
 end if;
end
$probe$;
rollback;
"""


def _no_claim_after_rollback(alias: str, case: str) -> str:
    subject, case_id = str(_as_uuid(alias)), str(_as_uuid(case))
    return f"""
begin;
set local role authenticated;
do $one$
begin
 perform set_config('request.jwt.claim.sub','{subject}',true);
 if (select count(*) from caseproof.cases where id='{case_id}') <> 1 then
     raise exception 'first transaction cannot see own case';
 end if;
end $one$;
rollback;
begin;
set local role authenticated;
do $two$
begin
 if (select count(*) from caseproof.cases) <> 0 then
     raise exception 'previous transaction leaked subject into fresh transaction';
 end if;
end $two$;
rollback;
"""


def check_disposable_rls(
    subject_a: str, subject_b: str, *,
    env: dict[str, str],
) -> None:
    """Check real PostgreSQL policies, including a positive path for EACH user."""
    # Caller has already enforced _env() for local test container. Validate
    # values BEFORE opening SQL, and use two random fixture accounts.
    a, b = str(_as_uuid(subject_a)), str(_as_uuid(subject_b))
    if a == b:
        raise ValueError("Different principals required")
    _bootstrap(env)
    _run(_fixture_sql(a, b), env)

    # Positive controls first: a deny-all RLS role cannot pass the gate.
    _run(_session_sql(a, CASE_A, CASE_B), env)
    _run(_session_sql(b, CASE_B, CASE_A), env)

    # No claim, bad claim and wrong-tenant case do not expose any case.
    _run(_session_sql(a, CASE_A, CASE_B, expected_own=0, claim=False), env)
    _run(_session_sql(a, CASE_B, CASE_A, expected_own=0), env)
    _run(_session_sql(b, CASE_A, CASE_B, expected_own=0), env)
    _run(_no_claim_after_rollback(a, CASE_A), env)

    # Revocation persists. A can no longer read its own earlier document,
    # while B continues to read B; authorization is evaluated afresh.
    _run(
        "update caseproof.organization_members set active=false,"
        "membership_revision=membership_revision+1 "
        f"where org_id='{ORG_A}' and user_id='{a}';",
        env,
    )
    _run(_session_sql(a, CASE_A, CASE_B, expected_own=0), env)
    _run(_session_sql(b, CASE_B, CASE_A), env)


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError("Missing required test configuration")
    return value


def _real_auth_subjects() -> tuple[str, str]:
    if os.environ.get("CASEPROOF_LIVE_AUTH_TEST") != "YES":
        raise ValueError("Explicit live Auth opt-in missing")
    key = _required("CASEPROOF_DEV_PUBLISHABLE_KEY")
    a = PasswordCredentials(
        _required("CASEPROOF_DEV_AUTH_A_EMAIL"),
        _required("CASEPROOF_DEV_AUTH_A_PASSWORD"),
    )
    b = PasswordCredentials(
        _required("CASEPROOF_DEV_AUTH_B_EMAIL"),
        _required("CASEPROOF_DEV_AUTH_B_PASSWORD"),
    )
    if a.email == b.email:
        raise ValueError("Two distinct test accounts required")
    outcome = run_live_auth_probe(
        SupabasePasswordSignin(PROJECT_REF, key),
        SupabaseAuthUserVerifier(
            PROJECT_REF, HttpsSupabaseUserLookup(PROJECT_REF, key),
        ),
        a, b,
        f"https://{PROJECT_REF}.supabase.co/auth/v1",
    )
    if not all((
        outcome.signed_session_a_verified,
        outcome.signed_session_b_verified,
        outcome.altered_signature_rejected,
    )):
        raise AssertionError("Signed-session verification incomplete")
    return outcome.user_a_id, outcome.user_b_id


def main() -> int:
    try:
        env = _env()  # Refuse any nonlocal host/DB before Auth network traffic.
        if os.environ.get("CASEPROOF_S2_007_REAL_AUTH") == "YES":
            user_a, user_b = _real_auth_subjects()
            mode = "SIGNED_AUTH_WITH_DISPOSABLE_RLS"
        elif os.environ.get("CASEPROOF_S2_007_SYNTHETIC") == "YES":
            user_a = "11111111-1111-4111-8111-111111111111"
            user_b = "22222222-2222-4222-8222-222222222222"
            mode = "SYNTHETIC_IDENTITY_DISPOSABLE_RLS"
        else:
            print("S2-007 opt-in required", file=sys.stderr)
            return 2

        aliases = pseudonymous_fixture_subjects(
            user_a, user_b, nonce=secrets.token_bytes(32),
        )
        check_disposable_rls(*aliases, env=env)
        print(f"S2-007_{mode}_POSITIVE_NEGATIVE_REVOCATION_PASSED")
        print("NOTE: actual Supabase Postgres runtime role and IdP-session revocation NOT proven")
        return 0
    except Exception as exc:
        # Under no circumstances log SQL, PostgreSQL stderr, real Auth UUIDs,
        # bearer tokens, emails, project passwords or provider exceptions.
        print(f"S2-007_VERIFY_FAILED: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
