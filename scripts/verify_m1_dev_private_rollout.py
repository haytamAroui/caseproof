"""M1-B exact-caseproof-dev private migration: DISPOSABLE install acceptance.

This test MUST run on an EMPTY, ONE-TIME, LOCAL PostgreSQL fixture only.
It bootstraps the installed foundation, injects unexpected policy/data,
requires a completely rolled-back migration, then verifies successful
atomic policy replacement, revoked case grants and a true non-BYPASSRLS
read login. It does not deploy to Supabase or forge real signed users.
"""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from scripts.verify_m1_private_rls import assert_counts, count, seed
from scripts.verify_m1_signed_private_reader import (
    SyntheticVerifier,
    verify_three_subjects,
)
from scripts.verify_s2_002_database import (
    MIGRATION,
    PROPOSAL_PATH,
    SCHEMA_BOOTSTRAP,
    _env,
    _run,
)

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "db/proposals/PIV-M1_DEV_atomic_private_grant_install.sql"


def _assert_not_installed(env: dict[str, str]) -> None:
    if _run(
        "select coalesce(to_regclass('caseproof._m1_matter_grants')::text,"
        "'not_installed')", env,
    ) != "not_installed":
        raise AssertionError("aborted private rollout created grant table")
    if _run(
        "select count(*) from pg_policies where schemaname='caseproof' "
        "and policyname in ('tenant_case_read','tenant_document_read',"
        "'tenant_document_version_read')", env,
    ) != "3":
        raise AssertionError("aborted rollout mutated existing policies")


def _assert_final_policies(env: dict[str, str]) -> None:
    if _run(
        "select count(*) from pg_policies where schemaname='caseproof' "
        "and policyname in ('tenant_case_read','tenant_document_read',"
        "'tenant_document_version_read')", env,
    ) != "0":
        raise AssertionError("privileged organization-wide read policy remains")
    got = _run(
        "select string_agg(tablename || ':' || policyname, ',' "
        "order by tablename,policyname) from pg_policies "
        "where schemaname='caseproof' and tablename in "
        "('cases','documents','document_versions','_m1_matter_grants')", env,
    )
    expected = ",".join((
        "_m1_matter_grants:m1_own_private_grant_read",
        "cases:m1_private_case_read",
        "document_versions:m1_private_document_version_read",
        "documents:m1_private_document_read",
    ))
    if got != expected:
        raise AssertionError("unexpected effective private-case RLS policy set")


def main() -> None:
    env = _env()
    if env.get("PGHOST") != "127.0.0.1" or env.get("PGPORT") != "5432":
        raise RuntimeError("Only pinned loopback ephemeral PostgreSQL accepted")
    if any(k in env for k in ("PGHOSTADDR", "PGSERVICE", "PGOPTIONS")):
        raise RuntimeError("Unexpected libpq address/option override")
    if MIGRATION.read_bytes() != PROPOSAL_PATH.read_bytes():
        raise RuntimeError("foundation source != canonical migration")
    if _run("select to_regclass('caseproof.cases') is null", env) != "t":
        raise RuntimeError("only fresh disposable database allowed")
    _run("begin;\n" + SCHEMA_BOOTSTRAP + MIGRATION.read_text() + "\ncommit;", env)
    proposed = INSTALL.read_text(encoding="utf-8")
    original_policy = (
        ROOT / "db/proposals/PIV-M1_default_private_rls_candidate.sql"
    ).read_text(encoding="utf-8")
    reviewed_body = (
        original_policy.split("\nbegin;", 1)[1]
        .rsplit("\ncommit;", 1)[0]
        .strip()
    )
    if reviewed_body not in proposed:
        raise AssertionError("atomic installer drifted from reviewed #86 policy body")

    # Unexpected permissive RLS policy: rollout must roll back entirely.
    _run(
        "create policy m1_attack_allow_every_case on caseproof.cases "
        "for select to authenticated using (true);", env,
    )
    _run(proposed, env, should_pass=False)
    _assert_not_installed(env)
    _run("drop policy m1_attack_allow_every_case on caseproof.cases", env)

    # A permissive membership policy is also forbidden: subject inventories
    # must remain private, not just cases and source versions.
    _run(
        "create policy m1_attack_read_all_members on "
        "caseproof.organization_members for select "
        "to authenticated using (true);", env,
    )
    _run(proposed, env, should_pass=False)
    _assert_not_installed(env)
    _run(
        "drop policy m1_attack_read_all_members on "
        "caseproof.organization_members", env,
    )

    # Existing genuine/synthetic users: requires a reviewed backfill, never
    # silently flip policy on a nonempty installed instance.
    a_fake = str(uuid4())
    _run(
        "insert into auth.users(id,instance_id) "
        f"values('{a_fake}','00000000-0000-4000-8000-000000000001');", env,
    )
    _run(proposed, env, should_pass=False)
    _assert_not_installed(env)
    _run(f"delete from auth.users where id='{a_fake}'", env)

    # Approve only an exact empty canonical foundation, all-or-nothing.
    _run(proposed, env)
    _assert_final_policies(env)

    # Reapplication requires human reconciliation, not accidental double
    # CREATE or partial privilege change.
    _run(proposed, env, should_pass=False)
    _assert_final_policies(env)

    a = seed()
    b = seed(org=a.org)
    c = seed()
    for fixture in (a, b, c):
        assert_counts(fixture.actor, (1, 1, 1, 1))

    # Stronger application acceptance uses real localhost unprivileged login
    # and independently seeded test subjects; these are not signed tokens.
    subjects = tuple(str(uuid4()) for _ in range(3))
    tokens = ("local-one", "local-two", "local-three")
    verify_three_subjects(
        tokens=tokens, subjects=subjects,
        verifier=SyntheticVerifier(dict(zip(tokens, subjects, strict=True))),
    )

    # Earlier synthetic A/B/C still have their own private reads and never
    # inherit newly seeded actors' privileges.
    for fixture in (a, b, c):
        assert_counts(fixture.actor, (1, 1, 1, 1))
    if count(uuid4(), "cases") != 0:
        raise AssertionError("unknown principal can see private matter")

    print("M1_DEV_FOUNDATION_ATOMIC_PRIVATE_ROLLOUT_NEGATIVE_AND_POSITIVE_PASSED")
    print("DISPOSABLE_DATABASE_ONLY: no Supabase Auth/Storage/live migration")


if __name__ == "__main__":
    main()
