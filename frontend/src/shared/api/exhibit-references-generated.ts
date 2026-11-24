/* Generated from Python ExhibitReferencesView. Do not edit. */

export type BriefVersionId = string;
export type ConfirmationId = string | null;
export type Detected = number;
/**
 * @maxItems 600
 */
export type EntriesNotDetectedInBrief = string[];
export type InventoryEntries = number;
export type Located = number;
export type InventoryComplete = boolean;
export type InventoryConfirmed = boolean;
export type Note = string;
export type End = number;
export type Filename = string | null;
export type Label = "stuk" | "piece";
export type Number = string;
export type PageCount = number | null;
export type Label1 = string;
export type PdfPage = number;
export type Space = "printed" | "bundle";
/**
 * @maxItems 128
 */
export type Pages = ExhibitPageView[];
export type Readback = ("verified" | "unknown" | "integrity_mismatch") | null;
export type Sha256 = string | null;
export type SourceVersionId = string | null;
export type PageCited = boolean;
export type RawText = string;
export type Reason = string;
export type ReferenceId = string;
export type DraftQuote = string;
export type OmittedSourcePrefix = string;
export type PdfPage1 = number | null;
export type ReservationCue = string;
export type SourceExcerpt = string;
export type Start = number;
export type Status = "UNVERIFIED" | "UNDETERMINED";
export type ClaimCue = string;
export type ClaimExcerpt = string;
export type MatchedValueKey = string;
export type PassageCue = string;
export type PdfPage2 = number | null;
export type SourceExcerpt1 = string;
/**
 * @maxItems 10000
 */
export type References = ExhibitReferenceView[];
export type Schema = "caseproof-exhibit-references-v1";
export type SnapshotHash = string;

/**
 * Exhibit mentions mapped to the confirmed inventory. Located never means content verified.
 */
export interface ExhibitReferencesView {
  brief_version_id: BriefVersionId;
  confirmation_id?: ConfirmationId;
  coverage: ExhibitCoverageView;
  inventory_complete: InventoryComplete;
  inventory_confirmed: InventoryConfirmed;
  note: Note;
  references: References;
  schema: Schema;
  snapshot_hash: SnapshotHash;
}
export interface ExhibitCoverageView {
  by_status: ByStatus;
  detected: Detected;
  entries_not_detected_in_brief: EntriesNotDetectedInBrief;
  inventory_entries: InventoryEntries;
  located: Located;
}
export interface ByStatus {
  [k: string]: number;
}
export interface ExhibitReferenceView {
  end: End;
  entry?: ExhibitEntryView | null;
  page_cited: PageCited;
  raw_text: RawText;
  reason: Reason;
  reference_id: ReferenceId;
  reservation_cue_flag?: ReservationCueFlagView | null;
  start: Start;
  status: Status;
  status_cue_flag?: StatusCueFlagView | null;
}
/**
 * The confirmed inventory identity, passed through as recorded.
 */
export interface ExhibitEntryView {
  filename?: Filename;
  label: Label;
  number: Number;
  page_count?: PageCount;
  pages: Pages;
  readback?: Readback;
  sha256?: Sha256;
  source_version_id?: SourceVersionId;
}
export interface ExhibitPageView {
  label: Label1;
  pdf_page: PdfPage;
  space: Space;
}
/**
 * Targeted FR/NL/EN omitted opening reservation cue. Appraisal cue only.
 */
export interface ReservationCueFlagView {
  draft_quote: DraftQuote;
  omitted_source_prefix: OmittedSourcePrefix;
  pdf_page?: PdfPage1;
  reservation_cue: ReservationCue;
  source_excerpt: SourceExcerpt;
}
/**
 * Targeted FR/NL lexical flag ('signé' vs 'envoyé pour signature'). Appraisal cue only.
 */
export interface StatusCueFlagView {
  claim_cue: ClaimCue;
  claim_excerpt: ClaimExcerpt;
  matched_value_key: MatchedValueKey;
  passage_cue: PassageCue;
  pdf_page?: PdfPage2;
  source_excerpt: SourceExcerpt1;
}
