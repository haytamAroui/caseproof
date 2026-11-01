/* Generated from Python MatterCatalogView. Do not edit. */

export type CaseId = string;
export type CaseRevision = number;
export type State = string;
/**
 * @maxItems 100
 */
export type Matters = MatterView[];
export type Schema = "caseproof-workspace-matters-v1";

export interface MatterCatalogView {
  matters: Matters;
  schema: Schema;
}
export interface MatterView {
  case_id: CaseId;
  case_revision: CaseRevision;
  state: State;
}
