/* Generated from Python LegalPassageView. Do not edit. */

export type ArticleText = string | null;
export type BriefExcerpt = string;
/**
 * @minItems 2
 * @maxItems 2
 */
export type CitationSpan = [number, number];
export type CorpusKey = string | null;
export type CorpusSourceUri = string | null;
export type CorpusTextSha256 = string | null;
export type CorpusVersion = string | null;
export type Note = string;
export type ObservationId = string;
export type Reason = string;
export type Schema = "caseproof-legal-passage-v1";
export type SnapshotHash = string;
export type Status = "PASS" | "FAIL" | "UNVERIFIED" | "UNDETERMINED";

/**
 * The lawyer's sentence beside the exact stored article text.
 */
export interface LegalPassageView {
  article_text?: ArticleText;
  brief_excerpt: BriefExcerpt;
  citation_span: CitationSpan;
  corpus_key?: CorpusKey;
  corpus_source_uri?: CorpusSourceUri;
  corpus_text_sha256?: CorpusTextSha256;
  corpus_version?: CorpusVersion;
  note: Note;
  observation_id: ObservationId;
  reason: Reason;
  schema: Schema;
  snapshot_hash: SnapshotHash;
  status: Status;
}
