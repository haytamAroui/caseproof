/* Generated from Python DraftExcerptView. Do not edit. */

export type Available = boolean;
export type BriefId = string;
export type CaseId = string;
export type Excerpt = string;
export type OriginalSha256 = string;
export type Reason = 'unsupported_or_ambiguous_anchor' | null;
export type ReferenceId = string;
export type Region = string | null;
export type Schema = 'caseproof-draft-excerpt-v1';
export type SelectionEnd = number;
export type SelectionStart = number;
export type SnapshotHash = string;

/**
 * Bounded plain-text excerpt from the exact signed preserved DOCX.
 */
export interface DraftExcerptView {
  available: Available;
  brief_id: BriefId;
  case_id: CaseId;
  excerpt: Excerpt;
  original_sha256: OriginalSha256;
  reason?: Reason;
  reference_id: ReferenceId;
  region?: Region;
  schema: Schema;
  selection_end: SelectionEnd;
  selection_start: SelectionStart;
  snapshot_hash: SnapshotHash;
}
