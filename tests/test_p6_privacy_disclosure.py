"""Security-sensitive development processing disclosure stays explicit."""
from pathlib import Path


def test_intake_does_not_claim_offline_storage_or_approved_privacy():
    root = Path(__file__).resolve().parents[1]
    screen = (root / "frontend/src/features/intake/IntakeScreen.tsx").read_text()
    flow = (root / "docs/security/PILOT_DATA_FLOW.md").read_text()
    assert "original document bytes" in screen
    assert "Supabase" in screen
    assert "not offline" in screen
    assert "confidential client files" in screen
    assert "zero-egress" in screen
    assert "does not keep all document content on the local machine" in flow
