import { describe, expect, it } from 'vitest';
import { parseMatters } from './matters';
const row = {
  case_id: '11111111-1111-4111-8111-111111111111',
  case_revision: 1,
  state: 'open',
};
const envelope = (matters: unknown[]) => ({
  schema: 'caseproof-workspace-matters-v1',
  matters,
});
describe('bounded signed catalog projection', () => {
  it('preserves descriptive states without granting capabilities', () => {
    expect(parseMatters(envelope([row])).matters).toEqual([row]);
    expect(parseMatters(envelope([])).matters).toEqual([]);
    expect(
      parseMatters(envelope([{ ...row, state: 'future-descriptive-state' }]))
        .matters[0]?.state,
    ).toBe('future-descriptive-state');
  });
  it('rejects duplicate, foreign-field, malformed, nil and oversized projections', () => {
    for (const rows of [
      [row, row],
      [{ ...row, org_id: 'hidden' }],
      [{ ...row, case_revision: 0 }],
      [{ ...row, case_revision: true }],
      [{ ...row, case_id: 'bad' }],
      [{ ...row, case_id: '00000000-0000-0000-0000-000000000000' }],
      Array(101).fill(row),
    ]) {
      expect(() => parseMatters(envelope(rows))).toThrow();
    }
    expect(() =>
      parseMatters({ ...envelope([]), schema: 'unknown' }),
    ).toThrow();
  });
});
