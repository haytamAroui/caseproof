/* Generated from Python ReviewLedgerView. Do not edit. */

export type BriefId = string;
export type CaseId = string;
export type Decision = "CONFIRMED_SUPPORTED" | "CONFIRMED_QUALIFIED" | "CONFIRMED_CONTRADICTED";
export type Rationale = string;
export type ReferenceId = string;
export type RequestId = string;
/**
 * @maxItems 96
 */
export type ReviewedRegionIds = string[];
export type ReviewerId = string;
export type Timestamp = string;
/**
 * @maxItems 10000
 */
export type Decisions = ReviewDecisionView[];
export type Schema = "caseproof-review-ledger-v1";
export type SnapshotHash = string;

export interface ReviewLedgerView {
  brief_id: BriefId;
  case_id: CaseId;
  decisions: Decisions;
  schema: Schema;
  snapshot_hash: SnapshotHash;
}
/**
 * A persisted signed human disposition, never a machine finding.
 */
export interface ReviewDecisionView {
  decision: Decision;
  rationale: Rationale;
  reference_id: ReferenceId;
  request_id: RequestId;
  reviewed_region_ids: ReviewedRegionIds;
  reviewer_id: ReviewerId;
  timestamp: Timestamp;
}
