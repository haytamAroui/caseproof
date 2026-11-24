/* Generated from Python LegalReferencesView. Do not edit. */

export type BriefVersionId = string;
export type Corpus = "configured" | "not_configured";
export type CorpusArticles = number;
/**
 * @maxItems 500
 */
export type CorpusFailures = string[];
export type CorpusPackSha256 = string | null;
export type Analysed = string;
export type Detected = number;
/**
 * @maxItems 20
 */
export type NotAnalysed =
  | []
  | [string]
  | [string, string]
  | [string, string, string]
  | [string, string, string, string]
  | [string, string, string, string, string]
  | [string, string, string, string, string, string]
  | [string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string, string, string, string]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ];
export type Note = string;
export type ActCode = string | null;
export type Article = string | null;
export type ClaimSupport = "not_assessed";
export type CorpusKey = string | null;
export type CorpusSourceUri = string | null;
export type CorpusTextSha256 = string | null;
export type CorpusVersion = string | null;
export type End = number;
export type Language = string | null;
export type ObservationId = string;
export type Quote = string | null;
export type RawText = string;
export type Reason = string;
export type ReferenceId = string;
export type Start = number;
export type Status = "PASS" | "FAIL" | "UNVERIFIED" | "UNDETERMINED";
/**
 * @maxItems 10000
 */
export type References = LegalReferenceView[];
export type Schema = "caseproof-legal-references-v1";
export type SnapshotHash = string;
export type ArticleKey = string;
/**
 * @maxItems 1000
 */
export type CitedBy = string[];
/**
 * @maxItems 200
 */
export type Facts = (string | boolean)[][];
/**
 * @maxItems 200
 */
export type InputHashes = string[][];
/**
 * @maxItems 200
 */
export type Missing = string[];
export type ObservationId1 = string;
export type Reason1 = string;
export type Reference = string;
export type RuleId = string;
export type RuleVersion = string;
export type Scope = string;
export type Status1 = "PASS" | "FAIL" | "UNVERIFIED" | "UNDETERMINED";
/**
 * @maxItems 200
 */
export type Subresults = string[][];
/**
 * @maxItems 10000
 */
export type Suitability = SuitabilityRowView[];

/**
 * Cited-article results of ONE frozen run. Observations, not verdicts.
 */
export interface LegalReferencesView {
  brief_version_id: BriefVersionId;
  corpus: Corpus;
  corpus_articles: CorpusArticles;
  corpus_failures: CorpusFailures;
  corpus_pack_sha256?: CorpusPackSha256;
  coverage: LegalCoverageView;
  note: Note;
  references: References;
  schema: Schema;
  snapshot_hash: SnapshotHash;
  suitability: Suitability;
}
export interface LegalCoverageView {
  analysed: Analysed;
  by_status: ByStatus;
  detected: Detected;
  not_analysed: NotAnalysed;
}
export interface ByStatus {
  [k: string]: number;
}
/**
 * One cited article checked against the matter's chosen corpus.
 *
 * status says corpus presence and quotation integrity only. It is never
 * applicability, correct reading or support for the claim.
 */
export interface LegalReferenceView {
  act_code?: ActCode;
  article?: Article;
  claim_support: ClaimSupport;
  corpus_key?: CorpusKey;
  corpus_source_uri?: CorpusSourceUri;
  corpus_text_sha256?: CorpusTextSha256;
  corpus_version?: CorpusVersion;
  end: End;
  language?: Language;
  observation_id: ObservationId;
  quote?: Quote;
  raw_text: RawText;
  reason: Reason;
  reference_id: ReferenceId;
  start: Start;
  status: Status;
}
/**
 * A lawyer-defined rule on declared facts. Never a machine legal conclusion.
 */
export interface SuitabilityRowView {
  article_key: ArticleKey;
  cited_by: CitedBy;
  facts: Facts;
  input_hashes: InputHashes;
  missing: Missing;
  observation_id: ObservationId1;
  reason: Reason1;
  reference: Reference;
  rule_id: RuleId;
  rule_version: RuleVersion;
  scope: Scope;
  status: Status1;
  subresults: Subresults;
}
