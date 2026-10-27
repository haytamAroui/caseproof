"""Stable contract guards for dev-only positive Storage fixture & cleanup."""
from __future__ import annotations

from pathlib import Path

from scripts import verify_m1_live_positive_original as live

ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "db/proposals/PIV-M1_DEV_live_positive_fixture_rpc.sql").read_text()
WORKFLOW = (ROOT / ".github/workflows/m1-m2-one-click-e2e.yml").read_text()


def test_privileged_rpc_is_service_role_only() -> None:
    for op in ("begin(uuid,uuid,uuid,uuid,text,bigint)", "revoke(uuid,uuid)",
               "cleanup(uuid,uuid)"):
        assert f"revoke all on function public.caseproof_dev_fixture_{op} from public,anon,authenticated" in SQL
        assert f"grant execute on function public.caseproof_dev_fixture_{op} to service_role" in SQL
    assert SQL.count("language plpgsql security definer set search_path = ''") == 3


def test_fixture_is_unique_and_only_reserved_real_auth_users() -> None:
    assert "email like 'caseproof-ci-%@example.com'" in SQL
    assert "email_confirmed_at is not null" in SQL
    assert "exists(select 1 from caseproof._dev_ci_fixture)" in SQL
    assert "exists(select 1 from caseproof.cases)" in SQL
    assert "exists(select 1 from storage.objects where bucket_id='caseproof-originals-dev')" in SQL
    assert "alter table caseproof._dev_ci_fixture enable row level security" in SQL


def test_cleanup_requires_storage_api_not_sql_object_delete() -> None:
    assert "remove original through Storage API before DB cleanup" in SQL
    assert "delete from storage.objects" not in SQL.lower()
    assert "/storage/v1/object/caseproof-originals-dev" in (ROOT / "scripts/verify_m1_live_positive_original.py").read_text()
    assert live.DIGEST == __import__("hashlib").sha256(live.FIXTURE).hexdigest()


def test_genuinely_live_manual_only_with_existing_two_secrets() -> None:
    assert "workflow_dispatch:" in WORKFLOW
    assert "environment: caseproof-dev-live-auth" in WORKFLOW
    assert "secrets.CASEPROOF_DEV_AUTH_ADMIN_KEY" in WORKFLOW
    assert "secrets.CASEPROOF_DEV_PUBLISHABLE_KEY" in WORKFLOW
    assert "CASEPROOF_DEV_DB_ADMIN_DSN" not in WORKFLOW
    assert "CASEPROOF_DEV_DB_CA_PEM" not in WORKFLOW
    assert "LIVE_M2_CHECK_REVIEW_CORRECTION_NOT_RUN_IN_THIS_WORKFLOW" in (ROOT / "scripts/verify_m1_live_positive_original.py").read_text()
