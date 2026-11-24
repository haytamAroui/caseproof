"""BE-06 (P1-7): HMAC receipt key custody separation & zero-downtime key rotation."""

from __future__ import annotations

import pytest

from apps.api.access_control import AccessRejected
from apps.api.dossier_journey import DossierStore

PUBLISHABLE = "sb_publishable_" + "a" * 40
ADMIN_KEY = "sb_secret_" + "b" * 40
HMAC_V1 = "caseproof-hmac-key-custody-v1-secret-material-0001"
HMAC_V2 = "caseproof-hmac-key-custody-v2-secret-material-0002"
PAYLOAD = {"case_id": "11111111-1111-4111-8111-111111111111", "snapshot": "a" * 64}


def test_dedicated_hmac_secret_is_separated_from_supabase_admin_key() -> None:
    legacy = DossierStore(PUBLISHABLE, receipt_secret=ADMIN_KEY)
    separated = DossierStore(PUBLISHABLE, receipt_secret=ADMIN_KEY, hmac_secret=HMAC_V1)

    assert legacy.receipt_key_separated is False
    assert separated.receipt_key_separated is True
    assert separated.revisions.trusted_key == ADMIN_KEY
    assert separated.receipt(PAYLOAD) != legacy.receipt(PAYLOAD)
    assert separated.verify_receipt(PAYLOAD, separated.receipt(PAYLOAD)) is True
    assert separated.verify_receipt(PAYLOAD, legacy.receipt(PAYLOAD)) is False


def test_hmac_key_rotation_verifies_previous_receipts_and_rejects_tampered() -> None:
    store_v1 = DossierStore(PUBLISHABLE, receipt_secret=ADMIN_KEY, hmac_secret=HMAC_V1)
    old_receipt = store_v1.receipt(PAYLOAD)

    store_v2 = DossierStore(
        PUBLISHABLE,
        receipt_secret=ADMIN_KEY,
        hmac_secret=HMAC_V2,
        previous_hmac_secrets=(HMAC_V1,),
    )
    new_receipt = store_v2.receipt(PAYLOAD)

    assert new_receipt != old_receipt
    assert store_v2.verify_receipt(PAYLOAD, new_receipt) is True
    assert store_v2.verify_receipt(PAYLOAD, old_receipt) is True
    assert store_v2.verify_receipt({**PAYLOAD, "tampered": True}, old_receipt) is False
    assert store_v2.verify_receipt(PAYLOAD, "0" * 64) is False
    assert store_v2.verify_receipt(PAYLOAD, "not-hex") is False


@pytest.mark.parametrize(
    "bad_secret",
    [
        "short-key",
        PUBLISHABLE,
        ADMIN_KEY,
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig",
    ],
)
def test_dedicated_hmac_rejects_supabase_or_weak_keys_fail_closed(bad_secret: str) -> None:
    store = DossierStore(PUBLISHABLE, receipt_secret=ADMIN_KEY, hmac_secret=bad_secret)
    assert store.receipt_key is None
    with pytest.raises(AccessRejected):
        store.receipt(PAYLOAD)
    with pytest.raises(AccessRejected):
        store.verify_receipt(PAYLOAD, "a" * 64)

    with pytest.raises(ValueError, match="previous HMAC receipt secret"):
        DossierStore(
            PUBLISHABLE,
            receipt_secret=ADMIN_KEY,
            hmac_secret=HMAC_V2,
            previous_hmac_secrets=(bad_secret,),
        )
