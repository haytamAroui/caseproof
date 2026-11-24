import referencesValidator from './legal-references-generated-validator';
import passageValidator from './legal-passage-generated-validator';
import packValidator from './offline-pack-generated-validator';
import type { OfflinePackManifest } from './offline-pack-generated';
import { ContractError } from './contracts';
import type { LegalReferencesView } from './legal-references-generated';
import type { LegalPassageView } from './legal-passage-generated';

export type { LegalReferencesView, LegalPassageView };
const STATUSES = ['PASS', 'FAIL', 'UNVERIFIED', 'UNDETERMINED'] as const;

/** Validate and cross-check a frozen-run legal result. Never upgrades a status. */
export function parseLegalReferences(
  value: unknown,
  expected: { briefId: string },
): LegalReferencesView {
  if (!referencesValidator(value)) throw new ContractError();
  const ids = value.references.map((r) => r.reference_id);
  if (
    value.schema !== 'caseproof-legal-references-v1' ||
    value.brief_version_id !== expected.briefId ||
    new Set(ids).size !== ids.length ||
    value.coverage.detected !== ids.length ||
    STATUSES.some(
      (s) =>
        value.coverage.by_status[s] !==
        value.references.filter((r) => r.status === s).length,
    ) ||
    (value.corpus === 'not_configured' &&
      value.references.some((r) => r.status === 'PASS')) ||
    value.suitability.some(
      (x) => x.status === 'PASS' && x.missing.length > 0,
    ) ||
    value.references.some(
      (r) => r.claim_support !== 'not_assessed' || r.end < r.start,
    )
  )
    throw new ContractError();
  return value;
}

export function parseLegalPassage(
  value: unknown,
  expected: { snapshot: string; referenceId: string },
): LegalPassageView {
  if (!passageValidator(value)) throw new ContractError();
  const [a, b] = value.citation_span;
  if (
    value.schema !== 'caseproof-legal-passage-v1' ||
    value.snapshot_hash !== expected.snapshot ||
    value.observation_id !== `legal:${expected.referenceId}` ||
    a === undefined ||
    b === undefined ||
    a < 0 ||
    a > b ||
    b > Array.from(value.brief_excerpt).length ||
    (value.status === 'PASS' && value.article_text === null) ||
    (value.quote_span !== null &&
      Array.from(value.brief_excerpt)
        .slice(value.quote_span[0], value.quote_span[1])
        .join('') !== value.quote)
  )
    throw new ContractError();
  return value;
}

export type { OfflinePackManifest };
export function parseOfflinePackManifest(
  value: unknown,
  expected: { briefId: string; snapshot: string },
): OfflinePackManifest {
  if (!packValidator(value)) throw new ContractError();
  if (
    value.schema !== 'caseproof-offline-pack-manifest-v1' ||
    value.brief_version_id !== expected.briefId ||
    value.snapshot_hash !== expected.snapshot
  )
    throw new ContractError();
  return value;
}
