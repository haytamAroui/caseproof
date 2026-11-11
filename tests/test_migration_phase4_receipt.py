"""The Phase 4 signed review ledger is a first-class, chronologically ordered migration."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
PHASE4 = MIGRATIONS / "20261030150030_caseproof_phase4_signed_reference_review.sql"
REVIEWED = ROOT / "supabase" / "phase4_reviewed" / "caseproof_phase4_signed_reference_review.sql"


def test_phase4_signed_sql_is_versioned_and_exactly_reviewed() -> None:
    assert PHASE4.is_file()
    assert PHASE4.read_bytes() == REVIEWED.read_bytes()
    sql = PHASE4.read_text(encoding="utf-8")
    assert "create table if not exists caseproof._phase4_reference_decisions" in sql
    assert "alter table caseproof._phase4_reference_decisions enable row level security" in sql
    assert "revoke all on caseproof._phase4_reference_decisions from public,anon,authenticated" in sql


def test_phase4_precedes_dependents_without_out_of_band_install() -> None:
    ordered = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
    phase4 = PHASE4.name
    assert len(ordered) == len(set(name[:14] for name in ordered))
    for dependent in (
        "20261030155817_matter_retention.sql",
        "20261030161844_complete_dossier_journey.sql",
    ):
        assert ordered.index(phase4) < ordered.index(dependent)
    script = (ROOT / "scripts" / "verify_retention_disposable.py").read_text(encoding="utf-8")
    assert "supabase/phase4_reviewed/caseproof_phase4_signed_reference_review.sql" not in script
    assert "paths = sorted((ROOT / 'supabase/migrations').glob('*.sql'))" in script
