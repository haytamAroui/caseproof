/* Generated from Python ClearbriefReviewState. Do not edit. */

export type ObservationId = string;
export type Reason = string;
export type ReviewDisposition = string;
/**
 * @maxItems 20000
 */
export type Items = BlockerItemView[];
export type Note = string;
export type ReleaseAuthorized = false;
export type Schema = "caseproof-blocker-inventory-v1";
export type SnapshotHash = string;
export type Verdict = "not_computed";
export type WaiverPolicy = "not_decided";
export type BriefVersionId = string;
export type CaseId = string;
export type ActorId = string;
export type Disposition = "confirmed_candidate" | "dismissed" | "needs_information";
export type ObservationId1 = string;
export type Rationale = string;
/**
 * @maxItems 10000
 */
export type Decisions = ClearbriefDecisionView[];
export type ReleaseAuthorized1 = false;
export type Revision = number;
export type Schema1 = "caseproof-clearbrief-review-v1";
export type SnapshotHash1 = string;

export interface ClearbriefReviewState {
  blocker_inventory: BlockerInventoryView;
  brief_version_id: BriefVersionId;
  case_id: CaseId;
  decisions: Decisions;
  release_authorized: ReleaseAuthorized1;
  revision: Revision;
  schema: Schema1;
  snapshot_hash: SnapshotHash1;
}
/**
 * Open items only. Not readiness and not permission to file.
 */
export interface BlockerInventoryView {
  items: Items;
  note: Note;
  release_authorized: ReleaseAuthorized;
  schema: Schema;
  snapshot_hash: SnapshotHash;
  verdict: Verdict;
  waiver_policy: WaiverPolicy;
}
export interface BlockerItemView {
  observation_id: ObservationId;
  reason: Reason;
  review_disposition: ReviewDisposition;
}
/**
 * A signed reviewer statement about one observation. Never semantic truth.
 */
export interface ClearbriefDecisionView {
  actor_id: ActorId;
  disposition: Disposition;
  observation_id: ObservationId1;
  rationale: Rationale;
}
