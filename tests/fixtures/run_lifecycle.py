"""M0.5 run-scoped fixture lifecycle. Never delete resources outside the manifest.

The manifest must be written durably before each external mutation. A run that
has no durable manifest must not be reaped by guessing email domains or paths.
"""
from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

ROLES = ("owner", "ungranted", "foreign")


def new_run_id() -> str:
    return str(uuid4())


def credentials(run_id: str) -> dict[str, tuple[str, str]]:
    UUID(run_id)
    return {
        role: (
            f"caseproof-ci-{role}-{run_id}@example.com",
            secrets.token_urlsafe(36),
        )
        for role in ROLES
    }


@dataclass
class RunManifest:
    run_id: str
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    state: str = "CREATING"
    users: dict[str, str] = field(default_factory=dict)
    matter_id: str | None = None
    org_id: str | None = None
    originals: list[dict[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        UUID(self.run_id)

    def save(self, path: Path) -> None:
        # Local manifest is a crash journal, NOT a durable cloud registry.
        # Reaper must not depend on runner-local filesystem persistence.
        data = {
            "run_id": self.run_id, "created_at": self.created_at,
            "state": self.state, "users": self.users,
            "matter_id": self.matter_id, "org_id": self.org_id,
            "originals": self.originals,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
        os.chmod(temp, 0o600)
        temp.replace(path)

    @classmethod
    def load(cls, path: Path) -> RunManifest:
        data = json.loads(path.read_text(encoding="utf-8"))
        if set(data) != {"run_id", "created_at", "state", "users", "matter_id", "org_id", "originals"}:
            raise ValueError("invalid manifest fields")
        return cls(**data)
