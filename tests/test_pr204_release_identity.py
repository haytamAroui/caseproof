"""PR204: only server-verified account identifiers may label releases."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.dossier_journey import DossierStore


class StubUserLookup:
    def __init__(self, user):
        self.user = user

    def get_verified_user(self, bearer):
        assert bearer == "signed"
        return self.user


class StubVerifier:
    def __init__(self, actor: str, user):
        self.actor = actor
        self.user_lookup = StubUserLookup(user)

    def verify_bearer(self, bearer):
        assert bearer == "signed"
        return SimpleNamespace(subject_id=self.actor)


def make_store(actor: str, user: dict) -> DossierStore:
    store = DossierStore("sb_publishable_synthetic123456")
    store.revisions.verifier = StubVerifier(actor, user)
    return store


def test_confirmed_email_is_account_label_not_spoofed_lawyer_name():
    actor = str(uuid4())
    store = make_store(actor, {
        "id": actor,
        "email": "associate@example.test",
        "email_confirmed_at": "2026-11-06T18:00:00Z",
        "user_metadata": {"full_name": "Meester Fake Partner", "role": "partner"},
    })
    label = store.release_actor("signed")
    assert label == {
        "actor_id": actor,
        "actor_label": "associate@example.test",
        "actor_label_type": "confirmed_email",
    }
    assert "Fake Partner" not in str(label)


def test_unconfirmed_email_falls_back_to_server_verified_uuid():
    actor = str(uuid4())
    store = make_store(actor, {
        "id": actor,
        "email": "unconfirmed@example.test",
        "email_confirmed_at": None,
    })
    label = store.release_actor("signed")
    assert label["actor_id"] == actor
    assert label["actor_label_type"] == "account_id"
    assert label["actor_label"] == f"Account {actor}"


def test_actor_user_mismatch_fails_closed_before_export():
    actor = str(uuid4())
    store = make_store(actor, {
        "id": str(uuid4()),
        "email": "not-the-actor@example.test",
        "email_confirmed_at": "2026-11-06T18:00:00Z",
    })
    with pytest.raises(AccessRejected) as error:
        store.release_actor("signed")
    assert error.value.code is AccessFailure.SERVICE_UNAVAILABLE
