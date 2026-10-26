"""The disposable Auth admin test NEVER counts mocked sessions as live evidence."""
from dataclasses import dataclass

import pytest

from apps.api.live_auth_probe import SessionProbeResult
from scripts.verify_dev_ephemeral_auth import (
    ISSUER,
    EphemeralAuthFailure,
    GoTrueDevAdmin,
    run_ephemeral_auth_probe,
)


@dataclass
class MemoryAdmin:
    created: list[str]
    deleted: list[str]
    fail_second: bool = False
    fail_delete: bool = False

    def create_confirmed(self, *, email: str, password: str) -> str:
        assert email.startswith("caseproof-ci-") and email.endswith("@example.com")
        assert len(password) >= 32
        if self.fail_second and self.created:
            raise EphemeralAuthFailure("create_failed")
        uid = f"synthetic-{len(self.created) + 1}"
        self.created.append(uid)
        return uid

    def delete(self, user_id: str) -> None:
        self.deleted.append(user_id)
        if self.fail_delete:
            raise EphemeralAuthFailure("delete_failed")


def _receipt(a: str = "synthetic-1", b: str = "synthetic-2") -> SessionProbeResult:
    return SessionProbeResult(
        ISSUER, a, b, True, True, True,
    )


def test_ephemeral_user_lifecycle_cleans_both_accounts_on_success():
    admin = MemoryAdmin([], [])
    seen = []

    def verified(a, b):
        seen.extend([a, b])
        assert a.email != b.email and a.password != b.password
        return _receipt()

    run_ephemeral_auth_probe(admin=admin, probe=verified)
    assert admin.created == ["synthetic-1", "synthetic-2"]
    assert admin.deleted == ["synthetic-2", "synthetic-1"]
    assert len(seen) == 2


def test_failed_second_create_deletes_first_account():
    admin = MemoryAdmin([], [], fail_second=True)
    with pytest.raises(EphemeralAuthFailure):
        run_ephemeral_auth_probe(admin=admin, probe=lambda a, b: _receipt())
    assert admin.deleted == ["synthetic-1"]


def test_failed_signed_session_still_cleans_up():
    admin = MemoryAdmin([], [])

    def fail(a, b):
        raise EphemeralAuthFailure("tampered_token_accepted")

    with pytest.raises(EphemeralAuthFailure):
        run_ephemeral_auth_probe(admin=admin, probe=fail)
    assert admin.deleted == ["synthetic-2", "synthetic-1"]


def test_subject_mismatch_not_a_successful_auth_smoke():
    admin = MemoryAdmin([], [])
    with pytest.raises(EphemeralAuthFailure, match="dev_signed_session_mismatch"):
        run_ephemeral_auth_probe(admin=admin, probe=lambda a, b: _receipt("wrong-id"))
    assert len(admin.deleted) == 2


def test_admin_cleanup_error_blocks_success():
    admin = MemoryAdmin([], [], fail_delete=True)
    with pytest.raises(EphemeralAuthFailure, match="cleanup_failed"):
        run_ephemeral_auth_probe(admin=admin, probe=lambda a, b: _receipt())
    assert len(admin.deleted) == 2


@pytest.mark.parametrize("key", [
    "sb_publishable_" + "x" * 40,
    "sb_secret_short",
    "public",
    "   ",
])
def test_published_keys_never_authorize_auth_admin(key):
    with pytest.raises(EphemeralAuthFailure):
        GoTrueDevAdmin(key)


def test_non_dev_email_and_unbounded_delete_fail_before_network():
    a = GoTrueDevAdmin("sb_secret_" + "x" * 44)
    with pytest.raises(EphemeralAuthFailure, match="reserved_test_email"):
        a.create_confirmed(email="someone@realmail.com", password="longtestpassword")
    with pytest.raises(EphemeralAuthFailure, match="unbounded_admin_delete"):
        a.delete("../../../auth/users")


def test_secret_injection_stays_inside_main_only_protected_environment():
    """Enforce the existing S2-006 private credential boundary on the new workflow."""
    import json
    from pathlib import Path

    p = Path(__file__).resolve().parents[1] / ".github/workflows/caseproof-dev-real-auth.yml"
    workflow = json.loads(p.read_text(encoding="utf-8"))
    assert list(workflow["on"]) == ["workflow_dispatch"]
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["jobs"]) == {"ephemeral-auth", "existing-users"}
    for mode, job in workflow["jobs"].items():
        assert job["environment"] == "caseproof-dev-live-auth"
        assert "github.event_name == 'workflow_dispatch'" in job["if"]
        assert "github.ref == 'refs/heads/main'" in job["if"]
        assert "github.repository == 'haytamAroui/caseproof'" in job["if"]
        assert job["steps"][0]["with"] == {"ref": "main", "persist-credentials": False}
        assert not any("setup-uv" in str(step) for step in job["steps"])
        steps = [step for step in job["steps"] if "env" in step]
        assert len(steps) == 1, mode
        for key, value in steps[0]["env"].items():
            if key in {"CASEPROOF_LIVE_AUTH_TEST", "CASEPROOF_EPHEMERAL_AUTH_TEST"}:
                assert value == "YES"
                continue
            assert value == "$" + "{{ secrets." + key + " }}"
    ephemeral = str(workflow["jobs"]["ephemeral-auth"]["steps"][-1]["env"])
    existing = str(workflow["jobs"]["existing-users"]["steps"][-1]["env"])
    assert "CASEPROOF_DEV_AUTH_ADMIN_KEY" in ephemeral
    assert "CASEPROOF_DEV_AUTH_ADMIN_KEY" not in existing
