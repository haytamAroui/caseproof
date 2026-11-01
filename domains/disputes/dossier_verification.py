"""Deterministic dossier findings; explicit human mappings, never filename inference."""
from __future__ import annotations

import re
from typing import Any

from domains.disputes.exhibit_identity import InventoryStatus, resolve_exhibit_identity

ALGORITHM = 'caseproof-dossier-v4'
_PAGE = re.compile(r'^\s*[,;:]?\s*(?:(PDF|printed|gedrukte|imprimée|bundle|bundel|liasse)\s+)?(?:pp?|pages?)\.?\s*(\d+)\b', re.I)


def build_findings(discovery: Any, regions: dict[str, str], sources: list[dict[str, Any]], confirmation: dict[str, Any] | None, *, inventory_status: InventoryStatus | None = None) -> dict[str, Any]:
    entries = confirmation['payload']['entries'] if confirmation else []
    complete = bool(confirmation and confirmation['payload']['inventory_complete'])
    status = inventory_status or (InventoryStatus.CONFIRMED_COMPLETE if complete else
                                  InventoryStatus.INCOMPLETE if confirmation else InventoryStatus.UNCONFIRMED)
    complete = status is InventoryStatus.CONFIRMED_COMPLETE
    findings = []
    references = (*discovery.references, *getattr(discovery, 'unsupported_references', ()))
    for index, ref in enumerate(references):
        supported = ref.label in {'stuk', 'stukken', 'piece', 'pièce', 'pieces', 'pièces'}
        label = 'stuk' if ref.label.startswith('stuk') else 'piece'
        matches = [e for e in entries if supported and e['label'] == label and e['number'] == ref.number]
        entry = matches[0] if len(matches) == 1 else None
        version = entry.get('source_version_id') if entry else None
        candidates = [s for s in sources if s['version_id'] == version and s['role'] == 'exhibit']
        source = candidates[0] if len(candidates) == 1 else None
        identities = tuple(f"entry-{i}" for i, _ in enumerate(matches))
        decision = resolve_exhibit_identity(inventory_status=status, matching_exhibit_ids=identities,
                                            authorized_source_ids=frozenset({"entry-0"}) if source else frozenset())
        identity = decision.state.value.lower() if supported else 'not_assessed'
        page = _PAGE.match(regions.get(ref.region, '')[ref.end:])
        requested = None
        unsupported_sequence = False
        if page:
            raw_space = (page[1] or '').casefold()
            space = ('pdf' if raw_space == 'pdf' else 'printed' if raw_space in
                     {'printed', 'gedrukte', 'imprimée'} else 'bundle' if raw_space in
                     {'bundle', 'bundel', 'liasse'} else 'unspecified')
            tail = regions.get(ref.region, '')[ref.end + page.end():]
            unsupported_sequence = bool(re.match(r'^\s*(?:[-–—−]|[,;]\s*\d|(?:and|en|et|to|tot|à)\s+\d)', tail, re.I))
            requested = {'space': space, 'label': page[2], 'kind': 'sequence' if unsupported_sequence else 'single'}
        mapped = []
        if source and entry and requested and not unsupported_sequence and requested['space'] != 'unspecified':
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
        image_page = bool(source and pdf_page and pdf_page in source.get('image_only_pages', []))
        image_page = image_page or bool(source and source.get('image_only'))
        page_spaces = {"pdf": {"state": "mapped" if pdf_page else "unmapped", "value": pdf_page}}
        for page_space in ("printed", "bundle"):
            labels = {p['label'] for p in entry['pages'] if p['space'] == page_space and p['pdf_page'] == pdf_page} if entry and pdf_page else set()
            page_spaces[page_space] = {"state": "mapped" if len(labels) == 1 else "conflicting" if labels else "unmapped",
                                       "value": next(iter(labels)) if len(labels) == 1 else None}
        findings.append({
            'reference_id': f'ref-{index:04d}', 'literal': ref.raw, 'region': ref.region,
            'offsets': {'start': ref.start, 'end': ref.end}, 'number': ref.number,
            'identity': identity, 'identity_reason': (decision.reason.value if decision.reason else None)
                         if supported else 'UNSUPPORTED_REFERENCE_DIALECT',
            'requested_page': requested,
            'source_id': source['document_id'] if source else None,
            'version_id': source['version_id'] if source else None,
            'source_sha256': source['sha256'] if source else None,
            'page_mapping': 'mapped' if pdf_page else 'conflicting' if len(targets) > 1 else 'unmapped',
            'pdf_page': pdf_page, 'page_spaces': page_spaces,
            'page_mapping_reason': 'page_sequence_requires_review' if unsupported_sequence else None,
            'printed_page': requested['label'] if pdf_page and requested and requested['space'] == 'printed' else None,
            'bundle_page': requested['label'] if pdf_page and requested and requested['space'] == 'bundle' else None,
            'mapping_basis': mapped if pdf_page else [],
            'source_page': {'version_id': version, 'pdf_page': pdf_page} if pdf_page else None,
            'ocr_crop': geometry.get('crop') if geometry else None,
            'ocr_uncertainty': 'requires_human_confirmation' if geometry else
                               'image_only_no_usable_ocr' if image_page else 'not_assessed',
            'fidelity': 'ocr_unreliable' if geometry or image_page else 'not_assessed',
            'support': 'not_assessed',
            'technical_check': 'checked' if identity == 'resolved' and pdf_page else 'unresolved',
        })
    checked = sum(f['technical_check'] == 'checked' for f in findings)
    return {'algorithm': ALGORITHM, 'findings': findings,
            'coverage': {'detected': len(findings),
                         'unsupported_references': len(getattr(discovery, 'unsupported_references', ())), 'checked': checked,
                         'unresolved': len(findings) - checked,
                         'unprocessed_regions': len(discovery.unscanned_parts),
                         'unprocessed_parts': list(discovery.unscanned_parts),
                         'text_coverage_complete': discovery.text_coverage_complete,
                         'reference_recall_measured': False, 'fully_checked': False,
                         'inventory_confirmed_complete': complete,
                         'limits': ['English Exhibit labels are detected for review only; no identity or pinpoint verification.',
                                    'Explicit Stuk/Pièce numbers only; ranges and implicit references are not expanded.',
                                    'Checked means identity and pinpoint checks, not quote fidelity or semantic support.',
                                    'Printed/bundle labels require explicit reviewer mappings; plain p. is ambiguous.']}}
