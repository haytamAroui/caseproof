/* Generated from Python OrganizationView. Do not edit. */

export type Name = string;
export type OrgId = string;
/**
 * @maxItems 100
 */
export type Organizations = Organization[];
export type Schema = "caseproof-workspace-create-orgs-v1";

export interface OrganizationView {
  organizations: Organizations;
  schema: Schema;
}
export interface Organization {
  name: Name;
  org_id: OrgId;
}
