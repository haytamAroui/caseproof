"""Read-only canonical report projection. Validation never computes verdicts."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FindingView(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    reference_id: str = Field(min_length=1, max_length=200)
    literal: str = Field(max_length=10000)
    identity: Literal["not_assessed", "not_in_inventory", "source_missing", "ambiguous", "resolved"]
    page_mapping: Literal["mapped", "unmapped", "conflicting"]
    fidelity: Literal["not_assessed", "ocr_unreliable", "representation_conflict", "translation_review_required", "multiple_matches", "exact_match", "quote_not_found"]
    support: Literal["not_assessed", "supported", "qualified", "contradicted"]

class DossierView(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    schema_version: Literal["caseproof-dossier-v1"] = Field(alias="schema")
    case_id: str = Field(min_length=1, max_length=200)
    brief_id: str = Field(min_length=1, max_length=200)
    snapshot_hash: str = Field(pattern="^[0-9a-f]{64}$")
    findings: list[FindingView] = Field(max_length=10000)
    coverage: dict[str, object]
