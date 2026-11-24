/* Generated from Python OfflinePackManifest. Do not edit. */

export type BriefVersionId = string;
export type ByteLength = number;
export type CheckpointSha256 = string;
export type Media = "application/zip";
export type Note = string;
export type Schema = "caseproof-offline-pack-manifest-v1";
export type Sha256 = string;
export type SnapshotHash = string;

/**
 * Exact digest and size of the offline review pack for one frozen check.
 */
export interface OfflinePackManifest {
  brief_version_id: BriefVersionId;
  byte_length: ByteLength;
  checkpoint_sha256: CheckpointSha256;
  media: Media;
  note: Note;
  schema: Schema;
  sha256: Sha256;
  snapshot_hash: SnapshotHash;
}
