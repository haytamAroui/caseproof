/* Generated from Python ClearbriefReviewReceipt. Do not edit. */

export type ReleaseAuthorized = false;
export type Replayed = boolean;
export type Revision = number;
export type Schema = "caseproof-clearbrief-review-receipt-v1";
export type SnapshotHash = string;

export interface ClearbriefReviewReceipt {
  release_authorized: ReleaseAuthorized;
  replayed: Replayed;
  revision: Revision;
  schema: Schema;
  snapshot_hash: SnapshotHash;
}
