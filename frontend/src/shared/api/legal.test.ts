import { describe, expect, it } from 'vitest';
import { ContractError } from './contracts';
import {
  parseLegalPassage,
  parseLegalReferences,
  parseReservationCues,
} from './legal';

const sha = 'a'.repeat(64);
const ref = (over: Record<string, unknown> = {}) => ({
  reference_id: 'r1',
  observation_id: 'legal:r1',
  raw_text: 'article 8.5 du Code civil',
  start: 0,
  end: 10,
  act_code: 'be-civ',
  article: '8.5',
  language: 'fr',
  status: 'PASS',
  reason: 'article_present_quote_literal',
  corpus_key: 'k',
  corpus_version: 'v1',
  corpus_text_sha256: sha,
  corpus_source_uri: 'urn:x',
  quote: null,
  claim_support: 'not_assessed',
  ...over,
});
const view = (over: Record<string, unknown> = {}, refs = [ref()]) => ({
  schema: 'caseproof-legal-references-v1',
  brief_version_id: 'b',
  snapshot_hash: sha,
  note: 'n',
  corpus: 'configured',
  corpus_pack_sha256: sha,
  corpus_articles: 1,
  corpus_failures: [],
  references: refs,
  coverage: {
    detected: refs.length,
    by_status: {
      PASS: refs.filter((r) => r.status === 'PASS').length,
      FAIL: 0,
      UNVERIFIED: 0,
      UNDETERMINED: 0,
    },
    analysed: 'a',
    not_analysed: ['case law'],
  },
  suitability: [],
  ...over,
});

describe('legal contract', () => {
  it('accepts a consistent result', () => {
    expect(
      parseLegalReferences(view(), { briefId: 'b' }).references,
    ).toHaveLength(1);
  });
  it('refuses another brief, a PASS without corpus and silent claim support', () => {
    expect(() => parseLegalReferences(view(), { briefId: 'x' })).toThrow(
      ContractError,
    );
    expect(() =>
      parseLegalReferences(
        view({ corpus: 'not_configured', corpus_pack_sha256: null }),
        { briefId: 'b' },
      ),
    ).toThrow(ContractError);
    expect(() =>
      parseLegalReferences(view({}, [ref({ claim_support: 'supported' })]), {
        briefId: 'b',
      }),
    ).toThrow(ContractError);
  });
  it('refuses counts that do not add up', () => {
    const v = view();
    v.coverage.by_status.PASS = 0;
    expect(() => parseLegalReferences(v, { briefId: 'b' })).toThrow(
      ContractError,
    );
  });
  it('binds a passage to its snapshot, reference and span', () => {
    const p = {
      schema: 'caseproof-legal-passage-v1',
      observation_id: 'legal:r1',
      snapshot_hash: sha,
      brief_excerpt: 'abcdef',
      citation_span: [1, 3],
      quote: 'cd',
      quote_span: [2, 4],
      other_findings: [],
      article_text: 'text',
      corpus_key: 'k',
      corpus_version: 'v1',
      corpus_text_sha256: sha,
      corpus_source_uri: 'urn:x',
      status: 'PASS',
      reason: 'r',
      note: 'n',
    };
    expect(
      parseLegalPassage(p, { snapshot: sha, referenceId: 'r1' }).article_text,
    ).toBe('text');
    expect(() =>
      parseLegalPassage(p, { snapshot: 'b'.repeat(64), referenceId: 'r1' }),
    ).toThrow(ContractError);
    expect(() =>
      parseLegalPassage(p, { snapshot: sha, referenceId: 'r2' }),
    ).toThrow(ContractError);
    expect(() =>
      parseLegalPassage(
        { ...p, citation_span: [3, 99] },
        { snapshot: sha, referenceId: 'r1' },
      ),
    ).toThrow(ContractError);
  });
});

describe('reservation cues contract', () => {
  const ok = {
    schema: 'caseproof-reservation-cues-v1',
    rules: 'reservation-cue-v1',
    advisory: true,
    note: 'Advisory.',
    snapshot_hash: 'a'.repeat(64),
    brief_version_id: 'b',
    rows: [
      {
        reference_id: 'r1',
        corpus_text_sha256: 'c'.repeat(64),
        cues: [
          {
            kind: 'reservation',
            cue: 'hormis',
            article_context: 'Hormis les cas',
          },
        ],
      },
    ],
  };
  it('accepts advisory rows and refuses a verdict field or a wrong brief', () => {
    expect(parseReservationCues(ok, { briefId: 'b' }).rows).toHaveLength(1);
    expect(() =>
      parseReservationCues({ ...ok, status: 'PASS' }, { briefId: 'b' }),
    ).toThrow();
    expect(() => parseReservationCues(ok, { briefId: 'other' })).toThrow();
    expect(() =>
      parseReservationCues({ ...ok, advisory: false }, { briefId: 'b' }),
    ).toThrow();
  });
});
