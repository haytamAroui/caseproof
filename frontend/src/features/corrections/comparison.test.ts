import { describe, expect, it } from 'vitest';
import type { DossierView, FindingView } from '../../shared/api';
import { comparisonCounts } from './comparison';

function finding(values: Partial<FindingView>): FindingView {
  return {
    reference_id: 'ref',
    literal: 'Stuk 1',
    identity: 'resolved',
    page_mapping: 'mapped',
    fidelity: 'exact_match',
    support: 'not_assessed',
    ...values,
  };
}

describe('independent report comparison counts', () => {
  it('keeps dimensions and uncertainty separate without pairing references', () => {
    const report = {
      findings: [
        finding({ reference_id: 'a' }),
        finding({
          reference_id: 'b',
          identity: 'ambiguous',
          page_mapping: 'unmapped',
          fidelity: 'ocr_unreliable',
        }),
        finding({
          reference_id: 'c',
          fidelity: 'representation_conflict',
          support: 'qualified',
        }),
      ],
    } as DossierView;
    expect(comparisonCounts(report)).toEqual({
      references: 3,
      identityResolved: 2,
      pageMapped: 2,
      exactText: 1,
      fidelityUnassessed: 0,
      ocrUnreliable: 1,
      representationConflict: 1,
      supportUnassessed: 2,
    });
  });
});
