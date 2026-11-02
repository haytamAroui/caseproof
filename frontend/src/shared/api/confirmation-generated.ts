/* Generated from Python InventoryConfirmation. Do not edit. */

export type BundleSignature = string;
export type Label = "stuk" | "piece";
export type Number = string;
export type Label1 = string;
export type PdfPage = number;
export type Rationale = string;
export type Space = "printed" | "bundle";
/**
 * @maxItems 128
 */
export type Pages = PageConfirmation[];
export type SourceVersionId = string | null;
/**
 * @maxItems 512
 */
export type Entries = IdentityConfirmation[];
export type Citation = string;
export type Kind = "detector_miss" | "unsupported_notation";
export type Rationale1 = string;
export type ReviewState = "review_needed";
export type Version = 1;
/**
 * @maxItems 64
 */
export type Exceptions = InventoryReviewException[];
export type InventoryComplete = boolean;
export type RequestId = string;

export interface InventoryConfirmation {
  bundle_signature: BundleSignature;
  entries: Entries;
  exceptions?: Exceptions;
  inventory_complete: InventoryComplete;
  request_id: RequestId;
}
export interface IdentityConfirmation {
  label: Label;
  number: Number;
  pages?: Pages;
  source_version_id?: SourceVersionId;
}
export interface PageConfirmation {
  label: Label1;
  pdf_page: PdfPage;
  rationale: Rationale;
  space: Space;
}
/**
 * Versioned, source-anchored human observation, not a verified identity.
 */
export interface InventoryReviewException {
  citation: Citation;
  kind: Kind;
  rationale: Rationale1;
  review_state?: ReviewState;
  version?: Version;
}
