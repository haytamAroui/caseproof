"""Deterministic dossier findings; explicit human mappings, never filename inference."""
from __future__ import annotations

import re
from typing import Any

ALGORITHM = 'caseproof-dossier-v1'
_PAGE = re.compile(r'^\s*[,;:]?\s*(?:(PDF|printed|gedrukte|imprimée|bundle|bundel|liasse)\s+)?p(?:age)?\.?\s*(\d+)\b', re.I)


def build_findings(discovery: Any, regions: dict[str, str], sources: list[dict[str, Any]], confirmation: dict[str, Any] | None) -> dict[str, Any]:
    entries = confirmation['payload']['entries'] if confirmation else []
    complete = bool(confirmation and confirmation['payload']['inventory_complete'])
    findings = []
    for index, ref in enumerate(discovery.references):
        label = 'stuk' if ref.label.startswith('stuk') else 'piece'
        matches = [e for e in entries if e['label'] == label and e['number'] == ref.number]
        entry = matches[0] if len(matches) == 1 else None
        version = entry.get('source_version_id') if entry else None
        candidates = [s for s in sources if s['version_id'] == version and s['role'] == 'exhibit']
        source = candidates[0] if len(candidates) == 1 else None
        identity = ('not_assessed' if not confirmation else 'ambiguous' if len(matches) > 1
                    else 'resolved' if source else 'source_missing' if entry
                    else 'not_in_inventory' if complete else 'not_assessed')
        page = _PAGE.match(regions.get(ref.region, '')[ref.end:])
        requested = None
        if page:
            raw_space = (page[1] or '').casefold()
            space = ('pdf' if raw_space == 'pdf' else 'printed' if raw_space in
                     {'printed', 'gedrukte', 'imprimée'} else 'bundle' if raw_space in
                     {'bundle', 'bundel', 'liasse'} else 'unspecified')
            requested = {'space': space, 'label': page[2]}
        mapped = []
        if source and entry and requested and requested['space'] != 'unspecified':
            if requested['space'] == 'pdf':
                physical = int(requested['label'])
                if 1 <= physical <= source.get('page_count', 0):
                    mapped = [{'pdf_page': physical, 'basis': 'physical_pdf_index'}]
            else:
                mapped = [p for p in entry['pages'] if p['space'] == requested['space'] and p['label'] == requested['label']
                          and 1 <= p['pdf_page'] <= source.get('page_count', 0)]
        targets = {p['pdf_page'] for p in mapped}
        pdf_page = next(iter(targets)) if len(targets) == 1 else None
        geometry = source.get('geometry', {}).get(str(pdf_page)) if source and pdf_page else None
        findings.append({
            'reference_id': f'ref-{index:04d}', 'literal': ref.raw, 'region': ref.region,
            'offsets': {'start': ref.start, 'end': ref.end}, 'number': ref.number,
            'identity': identity, 'requested_page': requested,
            'source_id': source['document_id'] if source else None,
            'version_id': source['version_id'] if source else None,
            'source_sha256': source['sha256'] if source else None,
            'page_mapping': 'mapped' if pdf_page else 'conflicting' if len(targets) > 1 else 'unmapped',
            'pdf_page': pdf_page,
            'printed_page': requested['label'] if pdf_page and requested and requested['space'] == 'printed' else None,
            'bundle_page': requested['label'] if pdf_page and requested and requested['space'] == 'bundle' else None,
            'mapping_basis': mapped if pdf_page else [],
            'source_page': {'version_id': version, 'pdf_page': pdf_page} if pdf_page else None,
            'ocr_crop': geometry.get('crop') if geometry else None,
            'ocr_uncertainty': 'requires_human_confirmation' if geometry else
                               'image_only_no_usable_ocr' if source and source.get('image_only') else 'not_assessed',
            'fidelity': 'ocr_unreliable' if geometry or (source and source.get('image_only')) else 'not_assessed',
            'support': 'not_assessed',
            'technical_check': 'checked' if identity == 'resolved' and pdf_page else 'unresolved',
        })
    checked = sum(f['technical_check'] == 'checked' for f in findings)
    return {'algorithm': ALGORITHM, 'findings': findings,
            'coverage': {'detected': len(findings), 'checked': checked,
                         'unresolved': len(findings) - checked,
                         'unprocessed_regions': len(discovery.unscanned_parts),
                         'unprocessed_parts': list(discovery.unscanned_parts),
                         'text_coverage_complete': discovery.text_coverage_complete,
                         'reference_recall_measured': False, 'fully_checked': False,
                         'inventory_confirmed_complete': complete,
                         'limits': ['Explicit Stuk/Pièce numbers only; ranges and implicit references are not expanded.',
                                    'Checked means identity and pinpoint checks, not quote fidelity or semantic support.',
                                    'Printed/bundle labels require explicit reviewer mappings; plain p. is ambiguous.']}}
