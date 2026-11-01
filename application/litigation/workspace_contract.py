"""Bounded read-only workspace projection; no capabilities inferred from membership."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MatterView(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    case_id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    case_revision: int = Field(ge=1)
    # Descriptive database state, never interpreted as an action permission.
    state: str = Field(min_length=1, max_length=64)


class MatterCatalogView(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)
    schema_version: Literal["caseproof-workspace-matters-v1"] = Field(alias="schema")
    matters: list[MatterView] = Field(max_length=100)

    @model_validator(mode="after")
    def unique_matters(self) -> "MatterCatalogView":
        if any(matter.case_id == "00000000-0000-0000-0000-000000000000" for matter in self.matters):
            raise ValueError("Nil matter identity")
        if len({matter.case_id for matter in self.matters}) != len(self.matters):
            raise ValueError("Duplicate matter identity")
        return self


class ReportLinkView(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    brief_id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    snapshot_hash: str = Field(pattern="^[0-9a-f]{64}$")
    created_at: str = Field(min_length=1, max_length=64)

    @field_validator('created_at')
    @classmethod
    def aware_creation_time(cls, value: str) -> str:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError('Timezone required')
        return value



class ReportCatalogView(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)
    schema_version: Literal["caseproof-workspace-reports-v1"] = Field(alias="schema")
    case_id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    reports: list[ReportLinkView] = Field(max_length=20)
    next_cursor: str | None = Field(pattern="^[0-9a-f]{64}$")
