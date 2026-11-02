import { describe, it, expect } from 'vitest';
import {
  assertReviewCommand, parseDraftExcerpt, parseReviewLedger, parseReviewWriteReceipt,
} from './review';

const scope = { caseId: 'case', briefId: 'brief', snapshot: 'a'.repeat(64) };
const command = {
  snapshot_hash: scope.snapshot,
  reference_id: 'ref-one',
  request_id: '11111111-1111-4111-8111-111111111111',
  decision: 'CONFIRMED_QUALIFIED',
  rationale: 'Inspected preserved original and surrounding context',
  reviewed_region_ids: ['region-one'],
};

const row = {
  reference_id: command.reference_id,
  request_id: command.request_id,
  reviewer_id: 'reviewer',
  decision: command.decision,
  rationale: command.rationale,
  timestamp: '2026-11-02T18:00:00Z',
  reviewed_region_ids: command.reviewed_region_ids,
};
describe('F4 generated Python to AJV/TypeScript reviewer contract parity', () => {
  it('rejects invalid dispositions and duplicate/invalid inspection IDs', () => {
    expect(assertReviewCommand(command).decision).toBe('CONFIRMED_QUALIFIED');
    for (const invalid of [
      { ...command, decision: 'VERIFIED' },
      { ...command, request_id: 'not-a-uuid' },
      { ...command, unexpected: true },
      { ...command, reviewed_region_ids: ['region-one', 'region-one'] },
      { ...command, rationale: '' },
      { ...command, snapshot_hash: 'wrong' },
    ]) expect(() => assertReviewCommand(invalid)).toThrow();
  });
  it('binds reviewed ledger to the exact frozen matter and decision identity', () => {
    const ledger = {
      schema: 'caseproof-review-ledger-v1', case_id: scope.caseId,
      brief_id: scope.briefId, snapshot_hash: scope.snapshot, decisions: [row],
    };
    expect(parseReviewLedger(ledger, scope).decisions).toHaveLength(1);
    for (const invalid of [
      { ...ledger, case_id: 'foreign' },
      { ...ledger, snapshot_hash: 'b'.repeat(64) },
      { ...ledger, decisions: [row, row] },
      { ...ledger, decisions: [{ ...row, decision: 'VERIFIED' }] },
      { ...ledger, decisions: [{ ...row, timestamp: 1234 }] },
    ]) expect(() => parseReviewLedger(invalid, scope)).toThrow();
  });
  it('rejects forged write acknowledgment and unsupported draft anchors', () => {
    const confirmed = assertReviewCommand(command);
    parseReviewWriteReceipt({
      request_id: command.request_id, reference_id: command.reference_id,
      reviewer_id: 'reviewer', decision: command.decision,
    }, confirmed);
    expect(() => parseReviewWriteReceipt({
      request_id: command.request_id, reference_id: command.reference_id,
      reviewer_id: 'reviewer', decision: 'CONFIRMED_SUPPORTED',
    }, confirmed)).toThrow();
    const excerpt = {
      schema: 'caseproof-draft-excerpt-v1', case_id: scope.caseId,
      brief_id: scope.briefId, snapshot_hash: scope.snapshot,
      reference_id: command.reference_id, original_sha256: 'b'.repeat(64),
      available: true, region: 'word/document.xml',
      excerpt: 'Before Stuk 1 after', selection_start: 7, selection_end: 13, reason: null,
    };
    const expected = { ...scope, referenceId: command.reference_id };
    expect(parseDraftExcerpt(excerpt, expected).excerpt.slice(7, 13)).toBe('Stuk 1');
    expect(() => parseDraftExcerpt({ ...excerpt, selection_end: 9999 }, expected)).toThrow();
    expect(() => parseDraftExcerpt({ ...excerpt, reference_id: 'foreign' }, expected)).toThrow();
    expect(() => parseDraftExcerpt({
      ...excerpt, available: false, reason: 'unsupported_or_ambiguous_anchor',
    }, expected)).toThrow();
  });
});
