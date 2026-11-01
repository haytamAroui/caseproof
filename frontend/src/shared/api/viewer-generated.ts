/* Generated from Python ViewerContext. Do not edit. */

export type BriefId = string;
export type ByteLength = number;
export type CaseId = string;
export type GeometryPolicy = "derived_pdf_text_only_legacy_raster_not_projected";
export type LegacyRegionCount = number;
export type OriginalSha256 = string;
export type PageMapping = "mapped" | "unmapped" | "conflicting";
export type PdfPage = number | null;
export type ReferenceId = string;
export type Schema = "caseproof-viewer-v1";
export type SnapshotHash = string;
export type VersionId = string;

export interface ViewerContext {
  brief_id: BriefId;
  byte_length: ByteLength;
  case_id: CaseId;
  geometry_policy: GeometryPolicy;
  legacy_region_count: LegacyRegionCount;
  original_sha256: OriginalSha256;
  page_mapping: PageMapping;
  pdf_page: PdfPage;
  reference_id: ReferenceId;
  schema: Schema;
  snapshot_hash: SnapshotHash;
  version_id: VersionId;
}
