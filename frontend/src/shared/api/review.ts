import reviewLedgerValidator from './review-ledger-generated-validator';
import excerptValidator from './draft-excerpt-generated-validator';
import reviewCommandValidator from './review-command-generated-validator';
import { ContractError } from './contracts';
import type { ReviewLedgerView } from './review-ledger-generated';
import type { DraftExcerptView } from './draft-excerpt-generated';
import type { VisualDecisionBody } from './review-command-generated';

export type { ReviewLedgerView, DraftExcerptView, VisualDecisionBody };
export function parseReviewLedger(
  value: unknown,
  expected: { caseId: string; briefId: string; snapshot: string },
): ReviewLedgerView {
  if (!reviewLedgerValidator(value)) throw new ContractError();
  if (
    value.schema !== 'caseproof-review-ledger-v1' ||
    value.case_id !== expected.caseId ||
    value.brief_id !== expected.briefId ||
    value.snapshot_hash !== expected.snapshot ||
    new Set(value.decisions.map((row) => row.request_id)).size !==
      value.decisions.length
  )
    throw new ContractError();
  return value;
}
export function parseDraftExcerpt(
  value: unknown,
  expected: {
    caseId: string;
    briefId: string;
    snapshot: string;
    referenceId: string;
  },
): DraftExcerptView {
  if (!excerptValidator(value)) throw new ContractError();
  if (
    value.schema !== 'caseproof-draft-excerpt-v1' ||
    value.case_id !== expected.caseId ||
    value.brief_id !== expected.briefId ||
    value.snapshot_hash !== expected.snapshot ||
    value.reference_id !== expected.referenceId ||
    (value.available &&
      (value.selection_start >= value.selection_end ||
        value.selection_end > value.excerpt.length)) ||
    (!value.available &&
      (value.excerpt !== '' ||
        value.reason !== 'unsupported_or_ambiguous_anchor'))
  )
    throw new ContractError();
  return value;
}
export function assertReviewCommand(value: unknown): VisualDecisionBody {
  if (!reviewCommandValidator(value)) throw new ContractError();
  if (
    new Set(value.reviewed_region_ids ?? []).size !==
      (value.reviewed_region_ids ?? []).length ||
    (value.reviewed_region_ids ?? []).some((id) => !/^[0-9a-f]{64}$/.test(id)) ||
    !/^[0-9a-f]{64}$/.test(value.snapshot_hash) ||
    !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      value.request_id,
    )
  )
    throw new ContractError();
  return value;
}
export function parseReviewWriteReceipt(
  value: unknown,
  command: VisualDecisionBody,
): void {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    throw new ContractError();
  const row = value as Record<string, unknown>;
  if (
    row.request_id !== command.request_id ||
    row.reference_id !== command.reference_id ||
    row.decision !== command.decision ||
    typeof row.reviewer_id !== 'string' ||
    row.reviewer_id.length === 0
  )
    throw new ContractError();
}
