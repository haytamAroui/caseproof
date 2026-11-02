"""Read-only canonical report projection. Validation never computes verdicts."""

import re
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from domains.disputes.page_labels import PAGE_LABEL_PATTERN


class FindingView(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    reference_id: str = Field(min_length=1, max_length=200)
    literal: str = Field(max_length=10000)
    identity: Literal["not_assessed", "not_in_inventory", "source_missing", "ambiguous", "resolved"]
    page_mapping: Literal["mapped", "unmapped", "conflicting"]
    fidelity: Literal[
        "not_assessed",
        "ocr_unreliable",
        "representation_conflict",
        "translation_review_required",
        "multiple_matches",
        "exact_match",
        "quote_not_found",
    ]
    support: Literal["not_assessed", "supported", "qualified", "contradicted"]

    @model_validator(mode="after")
    def validate_page_spaces(self) -> Self:
        spaces = self.model_extra.get("page_spaces") if self.model_extra else None
        if spaces is None:
            return self
        if not isinstance(spaces, dict) or set(spaces) != {"pdf", "printed", "bundle"}:
            raise ValueError("invalid page spaces")
        for name, row in spaces.items():
            if not isinstance(row, dict) or set(row) != {"state", "value"}:
                raise ValueError("invalid page space row")
            state, value = row["state"], row["value"]
            if state not in {"mapped", "unmapped", "conflicting"}:
                raise ValueError("invalid page space state")
            if state != "mapped":
                if value is not None:
                    raise ValueError("unresolved page space has a value")
            elif name == "pdf":
                if type(value) is not int or not 1 <= value <= 100000:
                    raise ValueError("invalid physical page")
            elif not isinstance(value, str) or re.fullmatch(PAGE_LABEL_PATTERN, value) is None or not value:
                raise ValueError("invalid page label")
        # Match the TypeScript parser: a supplied PDF page-space mapping
        # must not contradict the canonical finding mapping.
        if (self.page_mapping == "mapped") != (spaces["pdf"]["state"] == "mapped"):
            raise ValueError("physical page space contradicts finding page mapping")
        return self


class DossierView(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    schema_version: Literal["caseproof-dossier-v1"] = Field(alias="schema")
    case_id: str = Field(min_length=1, max_length=200)
    brief_id: str = Field(min_length=1, max_length=200)
    snapshot_hash: str = Field(pattern="^[0-9a-f]{64}$")
    findings: list[FindingView] = Field(max_length=10000)
    coverage: dict[str, object]
