"""Pure application-supplied regional fidelity selection, never page-wide approval."""
from __future__ import annotations

from typing import Any

from application.litigation.representation_normalization import normalize_region


def select_visual_assessment(page: dict[str, Any] | None, quote: str | None) -> dict[str, Any]:
    result: dict[str, Any] = {'state': 'not_assessed', 'performed': page is not None,
                             'reason': 'visual_not_run', 'regions': [],
                             'human_confirmation_required': True,
                             'calibration_status': 'not_available', 'quote': quote}
    if page is None:
        return result
    if page.get('error'):
        result['reason'] = page['error']
        return result
    if not quote:
        result['reason'] = 'citation_has_no_anchored_quotation'
        # Page-wide candidates are context only, never evidence about this quote.
        result['page_candidate_count'] = sum(r['state'] != 'not_assessed' for r in page['regions'])
        return result
    layer = page.get('layer_text', '')
    if not layer:
        result['reason'] = 'scan_without_independent_text_layer'
        result['state'] = 'ocr_unreliable'
        return result
    normalized = normalize_region(layer[:4000])
    needle = normalize_region(quote).text
    starts = []
    cursor = 0
    while needle and (offset := normalized.text.find(needle, cursor)) >= 0:
        starts.append(offset)
        cursor = offset + 1
    if len(starts) != 1:
        result['reason'] = 'quotation_missing_or_ambiguous_in_layer'
        return result
    start = normalized.raw_ranges[starts[0]][0]
    end = normalized.raw_ranges[starts[0]+len(needle)-1][1]
    selected = [r for r in page['regions'] if r['text_start'] < end and start < r['text_end']]
    if not selected or min(r['text_start'] for r in selected) > start or max(r['text_end'] for r in selected) < end:
        result['reason'] = 'region_budget_or_alignment_gap'
        return result
    result['regions'] = selected
    result['raw_span'] = [start,end]
    result['reason'] = 'uncalibrated_agreement'
    if any(r['state'] == 'representation_conflict' for r in selected):
        result.update(state='representation_conflict', reason='regional_representation_conflict')
    elif any(r['state'] == 'ocr_unreliable' for r in selected):
        result.update(state='ocr_unreliable', reason='regional_ocr_unreliable')
    elif not page.get('vector_geometry_supported'):
        result['reason'] = 'unsupported_vector_geometry'
    return result
