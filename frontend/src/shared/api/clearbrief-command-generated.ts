/* Generated from Python ReviewBody. Do not edit. */

export type Disposition = "confirmed_candidate" | "dismissed" | "needs_information";
export type ExpectedRevision = number;
export type ObservationId = string;
export type Rationale = string;
export type RequestId = string;
export type SnapshotHash = string;

export interface ReviewBody {
  disposition: Disposition;
  expected_revision: ExpectedRevision;
  observation_id: ObservationId;
  rationale: Rationale;
  request_id: RequestId;
  snapshot_hash: SnapshotHash;
}
