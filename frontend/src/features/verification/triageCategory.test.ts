import { describe, expect, it } from 'vitest';
import type { FindingView } from '../../shared/api';
import {
  collectReportFailureBanners,
  countByTriageCategory,
  matchesFailureBanner,
  triageCategoryOf,
  type FilterableFailureBannerKind,
} from './triageCategory';

const cleanFinding: FindingView = {
  reference_id: 'ref-1',
  literal: 'Pièce 1, p. 2',
  identity: 'resolved',
  page_mapping: 'mapped',
  fidelity: 'exact_match',
  support: 'not_assessed',
};

describe('triageCategoryOf', () => {
  it('projects resolved + mapped + exact_match findings to correspondance even when human support is not_assessed', () => {
    expect(triageCategoryOf(cleanFinding)).toBe('correspondance');
    expect(triageCategoryOf({ ...cleanFinding, support: 'supported' })).toBe(
      'correspondance',
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

  it('routes cross-language translations, multiple matches, and qualified support to appreciation', () => {
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

  it('guarantees exact 1:1 count parity between every filterable banner and matchesFailureBanner', () => {
    const findings: FindingView[] = [
      cleanFinding,
      { ...cleanFinding, reference_id: 'r2', identity: 'not_assessed' },
      { ...cleanFinding, reference_id: 'r3', identity: 'source_missing' },
      { ...cleanFinding, reference_id: 'r4', page_mapping: 'conflicting' },
      { ...cleanFinding, reference_id: 'r5', page_mapping: 'unmapped' },
      { ...cleanFinding, reference_id: 'r6', fidelity: 'ocr_unreliable' },
      {
        ...cleanFinding,
        reference_id: 'r7',
        fidelity: 'representation_conflict',
      },
      { ...cleanFinding, reference_id: 'r8', fidelity: 'quote_not_found' },
      {
        ...cleanFinding,
        reference_id: 'r9',
        fidelity: 'translation_review_required',
      },
    ];
    const banners = collectReportFailureBanners({
      findings,
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
        source_pages: [
          {
            version_id: 'v1',
            original_sha256: 'a'.repeat(64),
            pdf_page: 2,
            method: 'FAILED',
            reason: 'corrupt',
          },
        ],
        source_pages_total: 1,
      },
    });
    expect(banners.map((b) => [b.kind, b.count, b.filterable])).toEqual([
      ['inventory_unconfirmed', 1, true],
      ['pagination_unmapped', 2, true],
      ['ocr_unreliable', 2, true],
      ['failed_source_pages', 1, false],
      ['partial_coverage', 1, false],
    ]);
    for (const banner of banners.filter((b) => b.filterable)) {
      const matched = findings.filter((f) =>
        matchesFailureBanner(f, banner.kind as FilterableFailureBannerKind),
      );
      expect(matched.length).toBe(banner.count);
    }
  });
});
