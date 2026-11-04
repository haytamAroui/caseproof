/* Generated from Python DocxLocatorIdentity. Do not edit. */

export type ContentHash = string;
export type ExactText = string;
export type OccurrenceIndex = number;
export type ParagraphId = string | null;
export type Prefix = string;
export type SourceVersionId = string;
export type Suffix = string;

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
