import { describe, expect, it } from 'vitest';
import { ContractError } from './contracts';
import { parseExhibitReferences } from './legal';

const sha = 'a'.repeat(64);
const entry = {
  label: 'piece',
  number: '1',
  source_version_id: 'v1',
  filename: 'p1.pdf',
  sha256: sha,
  readback: 'verified',
  page_count: 2,
  pages: [{ space: 'printed', label: 'iv', pdf_page: 2 }],
};
const row = (over: Record<string, unknown> = {}) => ({
  reference_id: 'exhibit-ref-01',
  raw_text: 'Pièce 1',
  start: 0,
  end: 7,
  status: 'UNDETERMINED',
  reason: 'piece_located_in_confirmed_inventory_content_not_compared',
  page_cited: false,
  entry,
  ...over,
});
const view = (over: Record<string, unknown> = {}, rows = [row()]) => ({
  schema: 'caseproof-exhibit-references-v1',
  brief_version_id: 'b',
  snapshot_hash: sha,
  note: 'n',
  inventory_confirmed: true,
  inventory_complete: true,
  confirmation_id: 'c1',
  references: rows,
  coverage: {
    detected: rows.length,
    by_status: { PASS: 0, FAIL: 0, UNVERIFIED: 0, UNDETERMINED: rows.length },
    located: rows.length,
    inventory_entries: 1,
    entries_not_detected_in_brief: [],
  },
  ...over,
});
const want = { briefId: 'b', snapshot: sha };

describe('parseExhibitReferences', () => {
  it('accepts a located row and keeps identity and page spaces', () => {
    const v = parseExhibitReferences(view(), want);
    expect(v.references[0]?.entry?.pages[0]?.space).toBe('printed');
  });
  it('refuses another brief or snapshot', () => {
    expect(() =>
      parseExhibitReferences(view({ brief_version_id: 'x' }), want),
    ).toThrow(ContractError);
    expect(() =>
      parseExhibitReferences(view({ snapshot_hash: 'b'.repeat(64) }), want),
    ).toThrow(ContractError);
  });
  it('refuses a mapping without a confirmed inventory and a PASS', () => {
    expect(() =>
      parseExhibitReferences(
        view({ inventory_confirmed: false, inventory_complete: false }),
        want,
      ),
    ).toThrow(ContractError);
    expect(() =>
      parseExhibitReferences(view({}, [row({ status: 'PASS' })]), want),
    ).toThrow(ContractError);
  });
});
