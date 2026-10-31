"""Finite-policy held-out risk bound; never a per-field truth probability.

Hoeffding + union bound across a predeclared finite set of thresholds. Sampling
units must be independently adjudicated documents, not correlated word crops.
No default calibration artifact is shipped or enabled for legal documents.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CalibrationDocument:
    document_sha256: str
    minimum_score: float
    any_accepted_error: bool


def calibrate(documents: tuple[CalibrationDocument, ...], *, thresholds: tuple[float, ...],
              training_hashes: frozenset[str], evaluation_hashes: frozenset[str],
              target_risk: float, delta: float, independently_adjudicated: bool) -> dict[str, object]:
    if (not independently_adjudicated or not documents or not thresholds or len(thresholds) > 100
            or len(set(thresholds)) != len(thresholds) or not 0 < target_risk < 1 or not 0 < delta < 1
            or any(not math.isfinite(t) or not 0 <= t <= 1 for t in thresholds)):
        raise ValueError('invalid or unadjudicated calibration protocol')
    hashes = [d.document_sha256 for d in documents]
    if (len(hashes) != len(set(hashes)) or set(hashes) & (training_hashes | evaluation_hashes)
            or training_hashes & evaluation_hashes):
        raise ValueError('document split leakage')
    for d in documents:
        if (len(d.document_sha256) != 64 or any(c not in '0123456789abcdef' for c in d.document_sha256)
                or not math.isfinite(d.minimum_score) or not 0 <= d.minimum_score <= 1
                or type(d.any_accepted_error) is not bool):
            raise ValueError('invalid calibration document')
    candidates = []
    for threshold in sorted(thresholds):
        accepted = [d for d in documents if d.minimum_score >= threshold]
        n = len(accepted)
        errors = sum(d.any_accepted_error for d in accepted)
        upper = min(1., errors/n + math.sqrt(math.log(len(thresholds)/delta)/(2*n))) if n else 1.
        candidates.append({'threshold': threshold, 'accepted_documents': n,
                           'error_documents': errors, 'risk_upper_bound': upper})
    eligible = [c for c in candidates if c['accepted_documents'] and c['risk_upper_bound'] <= target_risk]
    return {'schema': 'caseproof.document-risk-calibration.v1',
            'status': 'eligible_under_assumptions' if eligible else 'insufficient_evidence',
            'selected': eligible[0] if eligible else None, 'candidates': candidates,
            'target_risk': target_risk, 'delta': delta,
            'assumptions': 'Independent representative adjudicated documents; fixed score and finite thresholds.',
            'shift_policy': 'Changed corpus, engine or score invalidates calibration; abstain.',
            'per_field_probability': None}
