"""Execute DOCX detection on pinned author-labelled synthetic examples.

This measures the actual parser/detector, not legal gold or representative-client
accuracy. Expected references never appear as extra labels in the input DOCX.
"""
from __future__ import annotations

import io
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

from docx import Document

from domains.disputes.dossier_verification import ALGORITHM
from infrastructure.parsers.docx_reference_discovery import discover_docx_references
from scripts.audit_m0_trilingual import DEFAULT_CORPUS

# Manually enumerated occurrences in the 18 new v3 brief texts. English lettered
# Exhibit references deliberately remain in the denominator despite no support.
EXPECTED = {
    'NL_INCOMPLETE_20': [('stuk', '99')], 'NL_OFFSET_21': [('stuk', '21')],
    'NL_MISMATCH_22': [('stuk', '22')], 'NL_SCAN_23': [('stuk', '23')],
    'FR_DUP_24': [('piece', '24')], 'FR_CLEAN_25': [('piece', '25')],
    'FR_ALIAS_26': [('piece', '26')], 'FR_NOQUOTE_27': [('piece', '27')],
    'EN_MISSING_28': [('exhibit', 'Z')], 'EN_OFFSET_29': [('exhibit', 'F')],
    'EN_CLEAN_30': [('exhibit', 'G')], 'EN_NOQUOTE_31': [('exhibit', 'H')],
    'MIX_TRANSLATION_32': [('piece', '32')],
    'MIX_UNCONFIRMED_33': [('stuk', '33'), ('piece', '33')],
    'EN_WRONG_PRINTED_34': [('exhibit', 'I')],
    'FR_SOURCE_MISSING_35': [('piece', '35')], 'FR_MISSING_36': [('piece', '88')],
    'EN_SCAN_37': [('exhibit', 'J')],
}


def evaluate(fixtures_dir: Path | None = None):
    corpus_bytes = DEFAULT_CORPUS.read_bytes()
    corpus = json.loads(corpus_bytes)
    if fixtures_dir is not None:
        fixtures_dir.mkdir(parents=True, exist_ok=True)
    cases = corpus['cases'][corpus['legacy_case_count']:]
    if {case['id'] for case in cases} != set(EXPECTED):
        raise ValueError('evaluation labels must be explicitly updated for changed corpus')
    cohorts = {}
    rows = []
    for case in cases:
        document = Document()
        document.add_paragraph(case['brief_text'])
        output = io.BytesIO()
        document.save(output)
        docx_bytes = output.getvalue()
        if fixtures_dir is not None:
            (fixtures_dir / (case['id'] + '.docx')).write_bytes(docx_bytes)
        discovery = discover_docx_references(docx_bytes)
        expected = Counter(EXPECTED[case['id']])
        actual = Counter(('stuk' if ref.label.startswith('stuk') else 'piece', ref.number)
                         for ref in discovery.references)
        unsupported = Counter(('exhibit', ref.number) for ref in discovery.unsupported_references)
        flagged = sum((expected & unsupported).values())
        tp, fp, fn = sum((expected & actual).values()), sum((actual - expected).values()), sum((expected - actual).values())
        cohort = cohorts.setdefault(case['language'], {'tp': 0, 'fp': 0, 'fn': 0, 'cases': 0, 'flagged_unsupported': 0})
        for key, value in [('tp', tp), ('fp', fp), ('fn', fn), ('cases', 1), ('flagged_unsupported', flagged)]:
            cohort[key] += value
        rows.append({'case_id': case['id'], 'docx_sha256': sha256(docx_bytes).hexdigest(),
                     'brief_utf8_sha256': sha256(case['brief_text'].encode()).hexdigest(), 'tp': tp, 'fp': fp, 'fn': fn,
                     'missing': list((expected - actual).elements()), 'flagged_unsupported': flagged,
                     'coverage_complete_claimed': discovery.coverage_complete})
    for cohort in cohorts.values():
        cohort['recall'] = cohort['tp'] / (cohort['tp'] + cohort['fn'])
        cohort['precision'] = (cohort['tp'] / (cohort['tp'] + cohort['fp'])
                               if cohort['tp'] + cohort['fp'] else None)
    return {'schema': 'caseproof-synthetic-docx-detection-eval-v1',
            'corpus': corpus['schema_version'], 'corpus_sha256': sha256(corpus_bytes).hexdigest(),
            'dossier_algorithm': ALGORITHM, 'detection_rules': 'numbered-belgian-v1+unsupported-exhibit-v1', 'synthetic_only': True,
            'independent_gold': False, 'representative_client_accuracy_accepted': False,
            'cohorts': cohorts, 'cases': rows,
            'limitations': ['Author-supplied labels; no independent adjudication',
                            'Reference detection only; no OCR or semantic-support accuracy measurement',
                            'English Exhibit references are flagged for manual review; unsupported verification remains counted separately']}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--fixtures-dir', type=Path)
    args = parser.parse_args()
    result = json.dumps(evaluate(args.fixtures_dir), ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result + '\n')
    print(result)
