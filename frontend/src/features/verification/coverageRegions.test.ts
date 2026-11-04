import { describe, expect, it } from 'vitest';
import { coverageRegions } from './coverageRegions';

describe('DOCX coverage ledger', () => {
  it('keeps unprocessed and unsupported regions separate and bounded', () => {
    const row = {
      part: 'word/header1.xml',
      kind: 'HEADER',
      status: 'UNPROCESSED_REGION',
      reason: 'TEXT_NOT_YET_SCANNED',
    };
    const unsupported = {
      ...row,
      part: 'word/document.xml#structured',
      status: 'UNSUPPORTED_REGION',
    };
    const parsed = coverageRegions({
      docx_regions: { coverage_unknown: false, regions: [row, unsupported] },
    });
    expect(parsed.regions).toEqual([row, unsupported]);
    expect(parsed.unknown).toBe(false);
    expect(
      coverageRegions({
        docx_regions: {
          coverage_unknown: false,
          regions: Array(1001).fill(row),
        },
      }).limited,
    ).toBe(true);
  });
  it('never turns absent or malformed data into complete coverage', () => {
    expect(coverageRegions({}).unknown).toBe(true);
    const result = coverageRegions({
      docx_regions: {
        coverage_unknown: false,
        regions: [null, { part: 'bad' }],
      },
    });
    expect(result.invalid).toBe(true);
    expect(result.regions).toEqual([]);
    expect(coverageRegions({ docx_regions: { regions: 'bad' } }).unknown).toBe(
      true,
    );
  });
});

describe('source-page coverage ledger', () => {
  it('retains unavailable processing and rejects invalid page identities', async () => {
    const { coveragePages } = await import('./coverageRegions');
    const row = {
      version_id: 'source',
      original_sha256: 'a'.repeat(64),
      pdf_page: 1,
      method: 'FAILED',
      reason: 'ocr_unavailable',
    };
    const result = coveragePages({
      source_pages: [row, { ...row, pdf_page: 0 }],
      source_pages_total: 2,
    });
    expect(result.pages).toEqual([
      {
        versionId: 'source',
        sha256: 'a'.repeat(64),
        page: 1,
        method: 'FAILED',
        reason: 'ocr_unavailable',
      },
    ]);
    expect(result.invalid).toBe(true);
    expect(result.unknown).toBe(false);
    expect(
      coveragePages({ source_pages: [row], source_pages_total: null }).unknown,
    ).toBe(true);
  });
});
