"""Read-only source inspection projection; never upgrades a finding."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ViewerContext(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)
    schema_version: Literal["caseproof-viewer-v1"] = Field(alias="schema")
    case_id: str = Field(min_length=1, max_length=200)
    brief_id: str = Field(min_length=1, max_length=200)
    snapshot_hash: str = Field(pattern="^[0-9a-f]{64}$")
    reference_id: str = Field(min_length=1, max_length=200)
    version_id: str = Field(min_length=1, max_length=200)
    original_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    byte_length: int = Field(ge=1, le=20_000_000)
    page_mapping: Literal["mapped", "unmapped", "conflicting"]
    pdf_page: int | None = Field(ge=1, le=200)
    legacy_region_count: int = Field(ge=0, le=96)
    geometry_policy: Literal["derived_pdf_text_only_legacy_raster_not_projected"]
