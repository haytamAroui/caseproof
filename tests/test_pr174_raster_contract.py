"""Negative geometry invariants: never interpret raster pixels as PDF page proof."""
import pytest
from pydantic import ValidationError

from application.litigation.viewer_contract import RasterOverlay

REGION = {
    'region_id': 'a' * 64, 'original_sha256': 'b' * 64,
    'page_number': 6, 'bbox': (10, 20, 30, 40),
    'image_size': (100, 200), 'crop_box': (200.0, 300.0, 300.0, 500.0),
    'rotation': 0, 'user_unit': 2.0, 'cropbox_rasterized': True,
}


def test_cropped_page_geometry_is_validated_before_projection():
    assert RasterOverlay.model_validate(REGION).crop_box == REGION['crop_box']
    rotated = {**REGION, 'rotation': 90, 'image_size': (200, 100)}
    assert RasterOverlay.model_validate(rotated).rotation == 90


@pytest.mark.parametrize('mutated', [
    {'bbox': (-1, 20, 30, 40)},
    {'bbox': (10, 20, 300, 40)},
    {'bbox': (10, 20, 10, 40)},
    {'image_size': (500, 200)},
    {'rotation': 45},
    {'user_unit': float('nan')},
    {'user_unit': 0.0},
    {'crop_box': (200.0, 300.0, 200.0, 500.0)},
    {'crop_box': (200.0, 300.0, float('inf'), 500.0)},
    {'cropbox_rasterized': False},
    {'page_number': 0},
    {'region_id': 'not-sha256'},
    {'unsupported_claim': 'verified'},
])
def test_unsupported_raster_coordinate_data_abstains(mutated):
    with pytest.raises(ValidationError):
        RasterOverlay.model_validate({**REGION, **mutated})
