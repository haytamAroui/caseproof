import { describe, expect, it } from 'vitest';
import { ContractError } from './contracts';
import {
  assertConditionsSave,
  parseConditionMatches,
  parseConditionsState,
} from './conditions';

const sha = 'a'.repeat(64);
const cond = {
  id: 'courrier',
  label: 'Courrier',
  question: '',
  trigger: ['courrier'],
  evidence: ['reçu'],
  pieces: [],
};
const anchor = (over: Record<string, unknown> = {}) => ({
  anchor_id: 'condition-anchor-01',
  condition_id: 'courrier',
  label: 'Courrier',
  question: '',
  start: 3,
  end: 10,
  sentence: 'Le courrier.',
  status: 'UNDETERMINED',
  reason: 'condition_passages_found_appraisal_required',
  found: [
    {
      piece: 'Pièce 1',
      source_id: 's',
      version_id: 'v',
      original_sha256: sha,
      pdf_page: 2,
      term: 'reçu',
      excerpt: 'reçu',
      excerpt_sha256: sha,
    },
  ],
  pieces_read: ['Pièce 1'],
  pieces_not_read: [],
  ...over,
});
const matches = (rows = [anchor()]) => ({
  schema: 'caseproof-condition-matches-v1',
  brief_version_id: 'b',
  revision: 1,
  spec_sha256: sha,
  scope: 's',
  anchors: rows,
  coverage: {
    conditions: 1,
    anchors: rows.length,
    sources_read: 1,
    sources_not_read: 0,
    by_status: { PASS: 0, FAIL: 0, UNVERIFIED: 0, UNDETERMINED: rows.length },
  },
});

describe('conditions contracts', () => {
  it('state: revision 0 means no digest and no conditions', () => {
    const base = {
      schema: 'caseproof-conditions-state-v1',
      note: 'n',
    };
    expect(
      parseConditionsState({
        ...base,
        revision: 0,
        spec_sha256: null,
        conditions: [],
      }).revision,
    ).toBe(0);
    expect(() =>
      parseConditionsState({
        ...base,
        revision: 0,
        spec_sha256: null,
        conditions: [cond],
      }),
    ).toThrow(ContractError);
  });
  it('save refuses duplicate ids and unknown fields', () => {
    expect(() =>
      assertConditionsSave({
        expected_revision: 0,
        conditions: [cond, cond],
      }),
    ).toThrow(ContractError);
    expect(() =>
      assertConditionsSave({
        expected_revision: 0,
        conditions: [{ ...cond, verdict: 'PASS' }],
      }),
    ).toThrow(ContractError);
  });
  it('matches: never PASS, and no-passage needs every piece read', () => {
    expect(
      parseConditionMatches(matches(), { briefId: 'b' }).anchors,
    ).toHaveLength(1);
    expect(() =>
      parseConditionMatches(matches([anchor({ status: 'PASS' })]), {
        briefId: 'b',
      }),
    ).toThrow(ContractError);
    expect(() =>
      parseConditionMatches(
        matches([
          anchor({
            status: 'UNVERIFIED',
            reason: 'condition_no_passage_found_in_pieces_read',
            found: [],
            pieces_not_read: ['Pièce 2'],
          }),
        ]),
        { briefId: 'b' },
      ),
    ).toThrow(ContractError);
    expect(() => parseConditionMatches(matches(), { briefId: 'x' })).toThrow(
      ContractError,
    );
  });
});
