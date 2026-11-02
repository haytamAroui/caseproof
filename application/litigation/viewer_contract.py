"""Read-only source inspection projection; never upgrades a finding."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


    @model_validator(mode="after")
    def validate_page_mapping(self) -> Self:
        if (self.page_mapping == "mapped") != (self.pdf_page is not None):
            raise ValueError("mapped page requires exactly one physical PDF page")
        return self


class RasterOverlay(BaseModel):
    """Source-bound raster rectangle, not a verification or human decision."""

    model_config = ConfigDict(extra="forbid", strict=True)
    region_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    original_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_number: int = Field(ge=1, le=200)
    bbox: tuple[int, int, int, int]
    image_size: tuple[int, int]
    crop_box: tuple[float, float, float, float]
    rotation: Literal[0, 90, 180, 270]
    user_unit: float = Field(gt=0, le=75)
    cropbox_rasterized: Literal[True]

    @model_validator(mode="after")
    def validate_raster_basis(self) -> Self:
        import math

        x0, y0, x1, y1 = self.bbox
        width, height = self.image_size
        left, bottom, right, top = self.crop_box
        if not (1 <= width <= 5000 and 1 <= height <= 6500
                and width * height <= 16_000_000
                and 0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height
                and all(math.isfinite(n) for n in self.crop_box)
                and all(abs(n) <= 100000 for n in self.crop_box)
                and right > left and top > bottom):
            raise ValueError("unsupported raster geometry")
        native_width = right - left
        native_height = top - bottom
        if self.rotation in (90, 270):
            native_width, native_height = native_height, native_width
        # Integer pixel rounding at rasterization is expected, but page
        # dimensions that disagree with the crop/rotation are not.
        if abs(width / height - native_width / native_height) > max(
            0.02, 3 / min(width, height)
        ):
            raise ValueError("raster aspect differs from cropped PDF page")
        return self
