"""Disposable Postgres + verified Vault original reader; not production storage."""
from __future__ import annotations

import hashlib
from uuid import UUID

from apps.api.litigation_check_service import PrivateMatterAccess
from apps.api.litigation_original_reader import Original
from apps.api.postgres_litigation_check_store import PostgresPrivateMatterCheckStore


class DisposableOriginalStore:
    def __init__(self, store: PostgresPrivateMatterCheckStore) -> None:
        self.store = store

    def read(self, *, access: PrivateMatterAccess, source_id: str, version_id: str) -> Original:
        source = self.store._source(access=access, source_id=source_id, version_id=version_id)
        raw = self.store._read_original(UUID(access.org_id), UUID(access.case_id), source.intent_id)
        if (type(raw) is not bytes or not 0 < len(raw) <= 5_242_880
                or hashlib.sha256(raw).hexdigest() != source.sha256_hex):
            raise ValueError("verified original is unavailable")
        return Original(raw, source.sha256_hex, source.media_type)
