import { describe, expect, it } from 'vitest';
import type { FindingView } from '../../shared/api';
import {
  collectReportFailureBanners,
  countByTriageCategory,
  triageCategoryOf,
} from './triageCategory';

const cleanFinding: FindingView = {
  reference_id: 'ref-1',
  literal: 'Pièce 1, p. 2',
  identity: 'resolved',
  page_mapping: 'mapped',
  fidelity: 'exact_match',
  support: 'supported',
};

describe('triageCategoryOf', () => {
  it('returns correspondance only when all four dimensions are confirmed clean', () => {
    expect(triageCategoryOf(cleanFinding)).toBe('correspondance');
    expect(triageCategoryOf({ ...cleanFinding, support: 'not_assessed' })).toBe(
      'appreciation',
    );
  });

  it('prioritizes ecart for mismatches, conflicts, and contradictions', () => {
    expect(
      triageCategoryOf({ ...cleanFinding, identity: 'not_in_inventory' }),
    ).toBe('ecart');
    expect(
      triageCategoryOf({ ...cleanFinding, page_mapping: 'conflicting' }),
    ).toBe('ecart');
    expect(
      triageCategoryOf({ ...cleanFinding, fidelity: 'quote_not_found' }),
    ).toBe('ecart');
    expect(
      triageCategoryOf({
        ...cleanFinding,
        fidelity: 'representation_conflict',
      }),
    ).toBe('ecart');
    expect(triageCategoryOf({ ...cleanFinding, support: 'contradicted' })).toBe(
      'ecart',
    );
  });

  it('classifies missing sources, unconfirmed inventory, unmapped pages, and unreliable OCR as impossible', () => {
    expect(
      triageCategoryOf({ ...cleanFinding, identity: 'not_assessed' }),
    ).toBe('impossible');
    expect(
      triageCategoryOf({ ...cleanFinding, identity: 'source_missing' }),
    ).toBe('impossible');
    expect(triageCategoryOf({ ...cleanFinding, identity: 'ambiguous' })).toBe(
      'impossible',
    );
    expect(
      triageCategoryOf({ ...cleanFinding, page_mapping: 'unmapped' }),
    ).toBe('impossible');
    expect(
      triageCategoryOf({ ...cleanFinding, fidelity: 'ocr_unreliable' }),
    ).toBe('impossible');
    expect(
      triageCategoryOf({ ...cleanFinding, fidelity: 'not_assessed' }),
    ).toBe('impossible');
  });

  it('routes cross-language translations and qualified/unassessed support to appreciation', () => {
    expect(
      triageCategoryOf({
        ...cleanFinding,
        fidelity: 'translation_review_required',
      }),
    ).toBe('appreciation');
    expect(
      triageCategoryOf({ ...cleanFinding, fidelity: 'multiple_matches' }),
    ).toBe('appreciation');
    expect(triageCategoryOf({ ...cleanFinding, support: 'qualified' })).toBe(
      'appreciation',
    );
  });

  it('counts all four categories accurately', () => {
    const counts = countByTriageCategory([
      cleanFinding,
      { ...cleanFinding, reference_id: 'ref-2', fidelity: 'quote_not_found' },
      { ...cleanFinding, reference_id: 'ref-3', fidelity: 'ocr_unreliable' },
      {
        ...cleanFinding,
        reference_id: 'ref-4',
        fidelity: 'translation_review_required',
      },
    ]);
    expect(counts).toEqual({
      ecart: 1,
      impossible: 1,
      appreciation: 1,
      correspondance: 1,
    });
  });
});

describe('collectReportFailureBanners', () => {
  it('returns no banners for a fully assessed clean report', () => {
    expect(
      collectReportFailureBanners({
        findings: [cleanFinding],
        coverage: {
          docx_regions: {
            coverage_unknown: false,
            regions: [
              {
                part: 'word/document.xml',
                kind: 'body',
                status: 'scanned',
                reason: 'ok',
              },
            ],
          },
          source_pages: [],
        },
      }),
    ).toEqual([]);
  });

  it('surfaces inventory, pagination, OCR, and partial DOCX coverage banners', () => {
    const banners = collectReportFailureBanners({
      findings: [
        { ...cleanFinding, reference_id: 'r1', identity: 'not_assessed' },
        { ...cleanFinding, reference_id: 'r2', page_mapping: 'conflicting' },
        { ...cleanFinding, reference_id: 'r3', fidelity: 'ocr_unreliable' },
      ],
      coverage: {
        docx_regions: {
          coverage_unknown: false,
          regions: [
            {
              part: 'word/header1.xml',
              kind: 'header',
              status: 'unprocessed',
              reason: 'unsupported_region',
            },
          ],
        },
        source_pages: [],
      },
    });
    expect(banners.map((b) => b.kind)).toEqual([
      'inventory_unconfirmed',
      'pagination_unmapped',
      'ocr_unreliable',
      'partial_coverage',
    ]);
  });
});
