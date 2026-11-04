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

describe('finding explanation', () => {
  it('shows supplied reasons without inferring a changed finding or decision', async () => {
    const { findingReasons } = await import('./comparison');
    const result = findingReasons(
      finding({
        identity_reason: 'SOURCE_MISSING',
        page_mapping_reason: null,
        literal_assessment: { reason: 'source_text_unavailable_or_partial' },
        visual_assessment: { reason: 'source_scan_ocr_unavailable' },
        translation_review_required: true,
      }),
    );
    expect(result).toEqual([
      ['Identity', 'SOURCE_MISSING'],
      ['Literal assessment', 'source_text_unavailable_or_partial'],
      ['Visual assessment', 'source_scan_ocr_unavailable'],
      ['Translation', 'Human review required'],
    ]);
    expect(findingReasons(finding({ visual_assessment: ['invalid'] }))).toEqual(
      [],
    );
  });
});
