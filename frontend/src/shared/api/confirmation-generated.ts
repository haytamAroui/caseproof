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
export type InventoryComplete = boolean;
export type RequestId = string;

export interface InventoryConfirmation {
  bundle_signature: BundleSignature;
  entries: Entries;
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
