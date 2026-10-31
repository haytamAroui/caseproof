"""Versioned report serialization shared by delivery adapters; no reassessment."""
from __future__ import annotations

import json
import re
from typing import Any


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _section(title: str, value: object) -> str:
    # Evidence and reviewer text are data, including Markdown images/HTML/fences.
    # A dynamically longer fence prevents source content becoming active markup.
    serialized = canonical(value)
    fence = '`' * max(3, 1 + max((len(m) for m in re.findall(r'`+', serialized)), default=0))
    return f'## {title}\n\n{fence}json\n{serialized}\n{fence}\n\n'


def render_dossier_export(report: dict[str, Any], format: str) -> str:
    """Single serializer; user-controlled fields never become active Markdown."""
    if format == 'json':
        return canonical(report)
    if format != 'markdown':
        raise ValueError('unsupported dossier export format')
    text = '# CaseProof scoped dossier report\n\n'
    text += _section('Coverage', report['coverage'])
    text += _section('Verification contract', report.get('verification_contract', {}))
    text += _section('Abstentions', report.get('abstentions', []))
    text += _section('Literal and translation assessments', [
        {k: f.get(k) for k in ('reference_id', 'identity_reason', 'quoted_text', 'draft_language',
                              'source_language', 'translation_review_required', 'literal_assessment',
                              'source_text_context', 'source_text_context_partial')}
        for f in report['findings']])
    text += _section('Independent finding dimensions', [
        {k: f.get(k) for k in ('reference_id', 'literal', 'identity', 'page_mapping', 'fidelity', 'support')}
        for f in report['findings']])
    text += _section('Visual assessments', [{
        'reference_id': f['reference_id'], 'assessment': {
            **f.get('visual_assessment', {}), 'regions': [{k: v for k, v in r.items()
                if k != 'crop_base64'} for r in f.get('visual_assessment', {}).get('regions', [])]}}
        for f in report['findings']])
    text += _section('Human decisions', report['human_decisions'])
    return text
