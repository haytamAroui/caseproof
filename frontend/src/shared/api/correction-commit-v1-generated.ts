/* Generated from Python CorrectionCommitBody. Do not edit. */

export type After = string;
export type Before = string;
export type ContentHash = string;
export type ExactText = string;
export type OccurrenceIndex = number;
export type ParagraphId = string | null;
export type Prefix = string;
export type SourceVersionId = string;
export type Suffix = string;
export type OriginalSha256 = string;
export type ParagraphIndex = number;
export type ReferenceId = string;
export type RequestId = string;
export type SnapshotHash = string;

export interface CorrectionCommitBody {
  after: After;
  before: Before;
  locator_identity?: DocxLocatorIdentity | null;
  original_sha256: OriginalSha256;
  paragraph_index: ParagraphIndex;
  reference_id: ReferenceId;
  request_id: RequestId;
  snapshot_hash: SnapshotHash;
}
/**
 * Version-bound identity for an exact editable DOCX paragraph.
 */
export interface DocxLocatorIdentity {
  content_hash: ContentHash;
  exact_text: ExactText;
  occurrence_index: OccurrenceIndex;
  paragraph_id?: ParagraphId;
  prefix: Prefix;
  source_version_id: SourceVersionId;
  suffix: Suffix;
}
