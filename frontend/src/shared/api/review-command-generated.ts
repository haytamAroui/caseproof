/* Generated from Python VisualDecisionBody. Do not edit. */

export type Decision =
  'CONFIRMED_SUPPORTED' | 'CONFIRMED_QUALIFIED' | 'CONFIRMED_CONTRADICTED';
export type Rationale = string;
export type ReferenceId = string;
export type RequestId = string;
/**
 * @maxItems 96
 */
export type ReviewedRegionIds = string[];
export type SnapshotHash = string;

export interface VisualDecisionBody {
  decision: Decision;
  rationale: Rationale;
  reference_id: ReferenceId;
  request_id: RequestId;
  reviewed_region_ids?: ReviewedRegionIds;
  snapshot_hash: SnapshotHash;
}
