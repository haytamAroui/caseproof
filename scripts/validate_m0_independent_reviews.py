"""Check review-packet completeness; never authenticate people or approve M0.

Use completed, genuinely independent submissions. Passing this checker means
ready for credential/evidence verification and owner decision, not signoff.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

STATES = {
    'identity': {'resolved', 'not_assessed', 'ambiguous', 'not_in_inventory', 'source_missing'},
    'page': {'mapped', 'unmapped', 'conflicting'},
    'fidelity': {'exact_match', 'mismatch', 'ocr_unreliable', 'translation_review_required',
                 'not_applicable', 'not_assessed'},
    'semantic_support': {'not_assessed', 'confirmed_supported', 'confirmed_qualified', 'confirmed_contradicted'},
}


def validate(packet, submissions, adjudications=None):
    issues = []
    cases = {row['id']: row for row in packet['cases']}
    coverage = defaultdict(list)
    seen_people = set()
    adjudications = adjudications or []
    for index, submission in enumerate([*submissions, *adjudications]):
        prefix = f'submission[{index}]'
        reviewer = submission.get('reviewer', {})
        person = (reviewer.get('real_name', '').strip().casefold(), reviewer.get('organization', '').strip().casefold())
        valid = True
        def reject(reason, label=prefix):
            nonlocal valid
            issues.append(label + ': ' + reason)
            valid = False
        if submission.get('schema') != 'caseproof-m0-review-submission-v1':
            reject('wrong submission schema')
        if submission.get('corpus_sha256') != packet['corpus_sha256']:
            reject('corpus hash mismatch')
        if submission.get('submission_status') != 'COMPLETED':
            reject('submission not completed')
        if not all(person) or person[0] in seen_people:
            reject('missing or duplicate reviewer identity')
        seen_people.add(person[0])
        if reviewer.get('independence_and_conflicts_attested') is not True:
            reject('independence not attested')
        if not reviewer.get('credential_and_signed_attestation_evidence', '').strip():
            reject('signed credential evidence missing')
        try:
            date.fromisoformat(reviewer.get('review_date', ''))
        except (ValueError, TypeError):
            reject('review date missing or invalid')
        languages = set(reviewer.get('languages_competent', []))
        seen_cases = set()
        for row in submission.get('cases', []):
            cid = row.get('id')
            if cid not in cases or cid in seen_cases:
                reject('unknown or duplicate case')
                continue
            seen_cases.add(cid)
            required = {'nl', 'fr', 'en'} if cases[cid]['language'] == 'mixed' else {cases[cid]['language']}
            if not required <= languages:
                reject('case outside declared language competence')
                continue
            if any(str(row.get(key, '')).lower() not in allowed for key, allowed in STATES.items()):
                reject('missing or invalid assessment state')
                continue
            if any(not str(row.get(key, '')).strip() for key in
                   ('source_observations', 'independent_rationale', 'confidence_and_limitations')):
                reject('source observations, rationale or limitations missing')
                continue
        if valid:
            for row in submission.get('cases', []):
                coverage[row['id']].append((person, row, bool(reviewer.get('belgian_legal_qualification', '').strip()),
                                            index >= len(submissions)))
    disagreements = []
    adjudicated = []
    for cid in cases:
        rows = [r for r in coverage[cid] if not r[3]]
        decisions = [r for r in coverage[cid] if r[3]]
        if len(rows) < 2:
            issues.append(cid + ': fewer than two distinct complete independent assessments')
        if not any(qualified for _, _, qualified, _ in [*rows, *decisions]):
            issues.append(cid + ': Belgian procedural competence not recorded')
        if len({tuple(str(row.get(key, '')).lower() for key in STATES) for _, row, _, _ in rows}) > 1:
            disagreements.append(cid)
            if len(decisions) != 1 or not decisions[0][2]:
                issues.append(cid + ': disagreement requires one separately recorded competent adjudication')
            else:
                adjudicated.append(cid)
    return {'schema': 'caseproof-independent-review-completeness-v1',
            'corpus_sha256': packet['corpus_sha256'], 'case_count': len(cases),
            'complete_assessments': {cid: sum(not row[3] for row in coverage[cid]) for cid in cases},
            'disagreements': disagreements, 'adjudicated_cases': adjudicated, 'issues': issues,
            'ready_for_owner_review': not issues, 'credentials_independently_verified': False,
            'm0_approved': False,
            'limitation': 'Completeness checks cannot authenticate people, signatures, source rights or legal judgments.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--submission', type=Path, action='append', default=[])
    parser.add_argument('--adjudication', type=Path, action='append', default=[])
    args = parser.parse_args()
    result = validate(json.loads(args.packet.read_text()), [json.loads(p.read_text()) for p in args.submission],
                      [json.loads(p.read_text()) for p in args.adjudication])
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['ready_for_owner_review'] else 1)
