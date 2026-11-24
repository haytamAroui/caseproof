import stateValidator from './clearbrief-review-generated-validator';
import receiptValidator from './clearbrief-receipt-generated-validator';
import commandValidator from './clearbrief-command-generated-validator';
import { ContractError } from './contracts';
import type { ClearbriefReviewState } from './clearbrief-review-generated';
import type { ClearbriefReviewReceipt } from './clearbrief-receipt-generated';
import type { ReviewBody } from './clearbrief-command-generated';

export type { ClearbriefReviewState, ClearbriefReviewReceipt, ReviewBody };

export function parseClearbriefState(
  value: unknown,
  expected: { caseId: string; briefId: string },
): ClearbriefReviewState {
  if (!stateValidator(value)) throw new ContractError();
  if (
    value.schema !== 'caseproof-clearbrief-review-v1' ||
    value.case_id !== expected.caseId ||
    value.brief_version_id !== expected.briefId ||
    value.blocker_inventory.snapshot_hash !== value.snapshot_hash ||
    value.release_authorized !== false
  )
    throw new ContractError();
  return value;
}

export function assertClearbriefCommand(value: unknown): ReviewBody {
  if (
    !commandValidator(value) ||
    value.rationale.trim() === '' ||
    !/^[0-9a-f]{64}$/.test(value.snapshot_hash)
  )
    throw new ContractError();
  return value;
}

export function parseClearbriefReceipt(
  value: unknown,
  expected: { snapshot: string },
): ClearbriefReviewReceipt {
  if (!receiptValidator(value)) throw new ContractError();
  if (
    value.schema !== 'caseproof-clearbrief-review-receipt-v1' ||
    value.snapshot_hash !== expected.snapshot ||
    value.release_authorized !== false
  )
    throw new ContractError();
  return value;
}
