"""M1-B protected ephemeral account cleanup never depends on SQL success."""
from __future__ import annotations

from uuid import uuid4

import pytest

from apps.api.supabase_password_signin import PasswordCredentials
from scripts.verify_m1_ephemeral_signed_private import ephemeral_private_probe


class AdminFake:
    def __init__(self, *, fail_create_at: int = 0, fail_cleanup: bool = False) -> None:
        self.created: list[str] = []
        self.deleted: list[str] = []
        self.fail_create_at = fail_create_at
        self.fail_cleanup = fail_cleanup

    def create_confirmed(self, *, email: str, password: str) -> str:
        assert email.startswith("caseproof-ci-") and email.endswith("@example.com")
        assert len(password) >= 36
        if self.fail_create_at == len(self.created) + 1:
            raise RuntimeError("fixture create failure")
        actor = str(uuid4())
        self.created.append(actor)
        return actor

    def delete(self, user_id: str) -> None:
        self.deleted.append(user_id)
        if self.fail_cleanup:
            raise RuntimeError("fixture cleanup failed")


def test_real_auth_fixture_cleanup_after_complete_probe() -> None:
    admin = AdminFake()
    credentials_seen: list[PasswordCredentials] = []

    def probe(credentials: tuple[PasswordCredentials, ...]) -> None:
        assert len(credentials) == 3
        assert len({x.email for x in credentials}) == 3
        credentials_seen.extend(credentials)

    ephemeral_private_probe(admin=admin, probe=probe)
    assert len(credentials_seen) == 3
    assert admin.deleted == list(reversed(admin.created))


def test_auth_fixture_cleanup_if_reader_or_review_fails() -> None:
    admin = AdminFake()

    def failing_probe(credentials: tuple[PasswordCredentials, ...]) -> None:
        assert len(credentials) == 3
        raise AssertionError("simulated RLS denial")

    with pytest.raises(AssertionError, match="simulated RLS"):
        ephemeral_private_probe(admin=admin, probe=failing_probe)
    assert len(admin.created) == 3
    assert admin.deleted == list(reversed(admin.created))


def test_partial_account_provisioning_failure_cleans_earlier_users() -> None:
    admin = AdminFake(fail_create_at=2)
    with pytest.raises(RuntimeError, match="create failure"):
        ephemeral_private_probe(admin=admin, probe=lambda _: None)
    assert len(admin.created) == 1
    assert admin.deleted == list(reversed(admin.created))


def test_cleanup_error_fails_acceptance_even_if_auth_and_rls_passed() -> None:
    admin = AdminFake(fail_cleanup=True)
    with pytest.raises(RuntimeError, match="cleanup failed"):
        ephemeral_private_probe(admin=admin, probe=lambda _: None)
    assert len(admin.created) == 3
    assert admin.deleted == list(reversed(admin.created))
