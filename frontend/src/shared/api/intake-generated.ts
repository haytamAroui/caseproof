/* Generated from Python IntakeView. Do not edit. */

export type BriefId = string | null;
export type BundleSignature = string | null;
export type CaseId = string;
export type ConfirmationId = string | null;
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
export type ReadbackComplete = boolean;
export type Schema = "caseproof-workspace-intake-v1";
export type ByteLength = number;
export type DocumentId = string;
export type Filename = string;
export type MediaType = string;
export type PageCount = number | null;
export type Processing = "preserved" | "text_extracted" | "partial" | "unavailable";
export type Role = "draft" | "inventory" | "exhibit";
export type Sha256 = string;
export type VersionId = string;
/**
 * @maxItems 32
 */
export type Sources = SourceView[];

export interface IntakeView {
  brief_id?: BriefId;
  bundle_signature?: BundleSignature;
  case_id: CaseId;
  confirmation_id?: ConfirmationId;
  entries: Entries;
  inventory_complete: InventoryComplete;
  readback_complete: ReadbackComplete;
  schema: Schema;
  sources: Sources;
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
export interface SourceView {
  byte_length: ByteLength;
  document_id: DocumentId;
  filename: Filename;
  media_type: MediaType;
  page_count?: PageCount;
  processing: Processing;
  role: Role;
  sha256: Sha256;
  version_id: VersionId;
}
