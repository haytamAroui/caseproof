/* Generated from Python DossierView. Do not edit. */

export type BriefId = string;
export type CaseId = string;
export type Fidelity =
  | "not_assessed"
  | "ocr_unreliable"
  | "representation_conflict"
  | "translation_review_required"
  | "multiple_matches"
  | "exact_match"
  | "quote_not_found";
export type Identity = "not_assessed" | "not_in_inventory" | "source_missing" | "ambiguous" | "resolved";
export type Literal = string;
export type PageMapping = "mapped" | "unmapped" | "conflicting";
export type ReferenceId = string;
export type Support = "not_assessed" | "supported" | "qualified" | "contradicted";
/**
 * @maxItems 10000
 */
export type Findings = FindingView[];
export type Schema = "caseproof-dossier-v1";
export type SnapshotHash = string;

export interface DossierView {
  brief_id: BriefId;
  case_id: CaseId;
  coverage: Coverage;
  findings: Findings;
  schema: Schema;
  snapshot_hash: SnapshotHash;
  [k: string]: unknown;
}
export interface Coverage {
  [k: string]: unknown;
}
export interface FindingView {
  fidelity: Fidelity;
  identity: Identity;
  literal: Literal;
  page_mapping: PageMapping;
  reference_id: ReferenceId;
  support: Support;
  [k: string]: unknown;
}
