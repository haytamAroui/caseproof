import stateValidator from './conditions-state-generated-validator';
import saveValidator from './conditions-save-generated-validator';
import matchesValidator from './condition-matches-generated-validator';
import type { ConditionsStateView } from './conditions-state-generated';
import type { ConditionsSaveBody } from './conditions-save-generated';
import type { ConditionMatchesView } from './condition-matches-generated';
import { ContractError } from './contracts';

export type { ConditionsStateView, ConditionsSaveBody, ConditionMatchesView };

export function parseConditionsState(value: unknown): ConditionsStateView {
  if (!stateValidator(value)) throw new ContractError();
  if (
    value.schema !== 'caseproof-conditions-state-v1' ||
    (value.revision === 0) !== (value.spec_sha256 == null) ||
    (value.revision === 0 && value.conditions.length > 0)
  )
    throw new ContractError();
  return value;
}

export function assertConditionsSave(value: unknown): ConditionsSaveBody {
  if (!saveValidator(value)) throw new ContractError();
  const ids = value.conditions.map((c) => c.id);
  if (new Set(ids).size !== ids.length) throw new ContractError();
  return value;
}

/** Never PASS; a "no passage" row needs every targeted piece read. */
export function parseConditionMatches(
  value: unknown,
  expected: { briefId: string },
): ConditionMatchesView {
  if (!matchesValidator(value)) throw new ContractError();
  const ids = value.anchors.map((a) => a.anchor_id);
  if (
    value.schema !== 'caseproof-condition-matches-v1' ||
    value.brief_version_id !== expected.briefId ||
    new Set(ids).size !== ids.length ||
    value.coverage.anchors !== ids.length ||
    (value.revision === 0 && value.anchors.length > 0) ||
    value.anchors.some(
      (a) =>
        (a.status as string) === 'PASS' ||
        a.end < a.start ||
        (a.status === 'UNVERIFIED' &&
          (a.found.length > 0 ||
            a.pieces_not_read.length > 0 ||
            a.pieces_read.length === 0)),
    )
  )
    throw new ContractError();
  return value;
}
