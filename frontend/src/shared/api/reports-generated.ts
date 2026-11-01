/* Generated from Python ReportCatalogView. Do not edit. */

export type CaseId = string;
export type NextCursor = string | null;
/**
 * @maxItems 20
 */
export type Reports =
  | []
  | [ReportLinkView]
  | [ReportLinkView, ReportLinkView]
  | [ReportLinkView, ReportLinkView, ReportLinkView]
  | [ReportLinkView, ReportLinkView, ReportLinkView, ReportLinkView]
  | [ReportLinkView, ReportLinkView, ReportLinkView, ReportLinkView, ReportLinkView]
  | [ReportLinkView, ReportLinkView, ReportLinkView, ReportLinkView, ReportLinkView, ReportLinkView]
  | [ReportLinkView, ReportLinkView, ReportLinkView, ReportLinkView, ReportLinkView, ReportLinkView, ReportLinkView]
  | [
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView
    ]
  | [
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView
    ]
  | [
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView
    ]
  | [
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView
    ]
  | [
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView
    ]
  | [
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView
    ]
  | [
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView
    ]
  | [
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView
    ]
  | [
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView
    ]
  | [
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView
    ]
  | [
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView
    ]
  | [
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView
    ]
  | [
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView,
      ReportLinkView
    ];
export type BriefId = string;
export type CreatedAt = string;
export type SnapshotHash = string;
export type Schema = "caseproof-workspace-reports-v1";

export interface ReportCatalogView {
  case_id: CaseId;
  next_cursor: NextCursor;
  reports: Reports;
  schema: Schema;
}
export interface ReportLinkView {
  brief_id: BriefId;
  created_at: CreatedAt;
  snapshot_hash: SnapshotHash;
}
