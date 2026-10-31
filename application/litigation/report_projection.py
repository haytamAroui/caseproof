"""Versioned report serialization shared by delivery adapters; no reassessment."""
from __future__ import annotations

import json
from typing import Any


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def render_dossier_export(report: dict[str, Any], format: str) -> str:
    """Single canonical serializer shared by REST and MCP."""
    if format == 'json':
        return canonical(report)
    if format != 'markdown':
        raise ValueError('unsupported dossier export format')
    text = '# CaseProof scoped dossier report\n\n' + canonical(report['coverage']) + '\n\n'
    text += 'Verification contract\n' + canonical(report.get('verification_contract', {})) + '\n\n'
    text += 'Abstentions\n' + canonical(report.get('abstentions', [])) + '\n\n'
    text += 'Literal and translation assessments\n' + canonical([{k: f.get(k) for k in ('reference_id', 'identity_reason', 'quoted_text', 'draft_language', 'source_language', 'translation_review_required', 'literal_assessment', 'source_text_context', 'source_text_context_partial')} for f in report['findings']]) + '\n\n'
    text += '\n'.join(f"- {f['reference_id']}: {f['literal']} — {f['identity']}; {f['page_mapping']}; {f['fidelity']}; {f['support']}"
                      for f in report['findings'])
    text += '\n\nVisual assessments\n' + canonical([{
        'reference_id': f['reference_id'], 'assessment': {
            **f.get('visual_assessment', {}), 'regions': [{k: v for k, v in r.items()
                if k != 'crop_base64'} for r in f.get('visual_assessment', {}).get('regions', [])]}}
        for f in report['findings']])
    text += '\n\nHuman decisions\n' + canonical(report['human_decisions'])

    return text

