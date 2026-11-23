import { describe, expect, it } from 'vitest';
import { ContractError } from './contracts';
import {
  assertClearbriefCommand,
  parseClearbriefReceipt,
  parseClearbriefState,
} from './clearbriefReview';

const sha = 'c'.repeat(64);
const state = (over: Record<string, unknown> = {}) => ({
  schema: 'caseproof-clearbrief-review-v1',
  case_id: 'c',
  brief_version_id: 'b',
  snapshot_hash: sha,
  revision: 0,
  decisions: [],
  blocker_inventory: {
    schema: 'caseproof-blocker-inventory-v1',
    snapshot_hash: sha,
    items: [],
    verdict: 'not_computed',
    release_authorized: false,
    waiver_policy: 'not_decided',
    note: 'n',
  },
  release_authorized: false,
  ...over,
});

describe('clearbrief review contract', () => {
  it('accepts a bound state and refuses release authorisation or another brief', () => {
    expect(
      parseClearbriefState(state(), { caseId: 'c', briefId: 'b' }).revision,
    ).toBe(0);
    expect(() =>
      parseClearbriefState(state({ release_authorized: true }), {
        caseId: 'c',
        briefId: 'b',
      }),
    ).toThrow(ContractError);
    expect(() =>
      parseClearbriefState(state(), { caseId: 'c', briefId: 'x' }),
    ).toThrow(ContractError);
  });
  it('refuses a blank reason and a receipt for another snapshot', () => {
    const cmd = {
      snapshot_hash: sha,
      observation_id: 'legal:r1',
      request_id: '12345678-1234-4234-8234-123456789abc',
      expected_revision: 0,
      disposition: 'dismissed',
      rationale: '  ',
    };
    expect(() => assertClearbriefCommand(cmd)).toThrow(ContractError);
    expect(
      assertClearbriefCommand({ ...cmd, rationale: 'x' }).disposition,
    ).toBe('dismissed');
    const receipt = {
      schema: 'caseproof-clearbrief-review-receipt-v1',
      snapshot_hash: sha,
      revision: 1,
      replayed: false,
      release_authorized: false,
    };
    expect(parseClearbriefReceipt(receipt, { snapshot: sha }).revision).toBe(1);
    expect(() =>
      parseClearbriefReceipt(receipt, { snapshot: 'd'.repeat(64) }),
    ).toThrow(ContractError);
  });
});
