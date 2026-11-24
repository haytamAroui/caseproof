/* Generated from Python ConditionMatchesView. Do not edit. */

export type AnchorId = string;
export type ConditionId = string;
export type End = number;
export type Excerpt = string;
export type ExcerptSha256 = string;
export type OriginalSha256 = string;
export type PdfPage = number | null;
export type Piece = string;
export type SourceId = string;
export type Term = string;
export type VersionId = string;
/**
 * @maxItems 600
 */
export type Found = ConditionFoundView[];
export type Label = string;
/**
 * @maxItems 64
 */
export type PiecesNotRead = string[];
/**
 * @maxItems 64
 */
export type PiecesRead = string[];
export type Question = string;
export type Reason = string;
export type Sentence = string;
export type Start = number;
export type Status = "UNVERIFIED" | "UNDETERMINED";
/**
 * @maxItems 200
 */
export type Anchors = ConditionAnchorView[];
export type BriefVersionId = string;
export type Anchors1 = number;
export type Conditions = number;
export type SourcesNotRead = number;
export type SourcesRead = number;
export type Revision = number;
export type Schema = "caseproof-condition-matches-v1";
export type Scope = string;
export type SpecSha256 = string | null;

/**
 * Condition anchors of ONE brief version. Routing for the lawyer, never a verdict.
 */
export interface ConditionMatchesView {
  anchors: Anchors;
  brief_version_id: BriefVersionId;
  coverage: ConditionCoverageView;
  revision: Revision;
  schema: Schema;
  scope: Scope;
  spec_sha256?: SpecSha256;
}
export interface ConditionAnchorView {
  anchor_id: AnchorId;
  condition_id: ConditionId;
  end: End;
  found: Found;
  label: Label;
  pieces_not_read: PiecesNotRead;
  pieces_read: PiecesRead;
  question: Question;
  reason: Reason;
  sentence: Sentence;
  start: Start;
  status: Status;
}
export interface ConditionFoundView {
  excerpt: Excerpt;
  excerpt_sha256: ExcerptSha256;
  original_sha256: OriginalSha256;
  pdf_page?: PdfPage;
  piece: Piece;
  source_id: SourceId;
  term: Term;
  version_id: VersionId;
}
export interface ConditionCoverageView {
  anchors: Anchors1;
  by_status: ByStatus;
  conditions: Conditions;
  sources_not_read: SourcesNotRead;
  sources_read: SourcesRead;
}
export interface ByStatus {
  [k: string]: number;
}
