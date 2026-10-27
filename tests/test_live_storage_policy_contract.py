"""Private Storage policy action checks: guard the reviewed deployed correction."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUCKET_SQL = (ROOT / "supabase/migrations/20261027202734_caseproof_m1_private_originals_storage.sql").read_text()
CORRECTED_SQL = (ROOT / "supabase/migrations/20261027204343_caseproof_m1_storage_upload_action_correction.sql").read_text()


def test_bucket_stays_private_and_immutable() -> None:
    assert "'caseproof-originals-dev','caseproof-originals-dev',false" in BUCKET_SQL
    assert "create policy caseproof_m1_original_read" in BUCKET_SQL
    assert "create policy caseproof_m1_original_put_once" in BUCKET_SQL
    for forbidden in ("for update to authenticated", "for delete to authenticated"):
        assert forbidden not in BUCKET_SQL.lower()
        assert forbidden not in CORRECTED_SQL.lower()


def test_corrected_action_contract_is_possible_for_real_organization_members() -> None:
    assert "drop policy caseproof_m1_original_put_once" in CORRECTED_SQL
    _, policy = CORRECTED_SQL.split("create policy caseproof_m1_original_put_once", 1)
    policy, _ = policy.split("do $verify$", 1)
    assert "'case:read'=any(m.actions)" in policy
    assert "'evidence:read'=any(m.actions)" in policy
    assert "'evidence:upload'=any(g.permissions)" in policy
    assert "'case:read'=any(g.permissions)" in policy
    assert "'evidence:upload'=any(m.actions)" not in policy


def test_read_requires_exact_matter_and_real_version_digest() -> None:
    assert "and v.original_sha256_hex = split_part(storage.objects.name,'/',5)" in BUCKET_SQL
    assert "and g.user_id=m.user_id" in BUCKET_SQL
    assert "and m.active and g.active" in BUCKET_SQL
    assert "and 'evidence:read'=any(g.permissions)" in BUCKET_SQL
