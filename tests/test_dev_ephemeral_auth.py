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
