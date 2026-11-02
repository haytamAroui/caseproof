import organizationsValidator from './organizations-generated-validator';
import createdValidator from './created-generated-validator';
import intakeValidator from './intake-generated-validator';
import { ContractError } from './contracts';
import type { IntakeView } from './intake-generated';
export type {
  IntakeView,
  IdentityConfirmation,
  PageConfirmation,
  InventoryReviewException,
} from './intake-generated';
export type { InventoryConfirmation } from './confirmation-generated';
const uuid = (s: string) =>
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(s) &&
  !/^0{8}-0{4}-0{4}-0{4}-0{12}$/.test(s);
export function parseOrganizations(value: unknown) {
  if (
    !organizationsValidator(value) ||
    value.schema !== 'caseproof-workspace-create-orgs-v1' ||
    value.organizations.some((o) => !uuid(o.org_id)) ||
    new Set(value.organizations.map((o) => o.org_id)).size !==
      value.organizations.length
  )
    throw new ContractError();
  return value;
}
export function parseCreated(value: unknown, request: string) {
  if (
    !createdValidator(value) ||
    value.schema !== 'caseproof-workspace-created-v1' ||
    value.request_id !== request ||
    !uuid(value.case_id)
  )
    throw new ContractError();
  return value;
}
export function parseIntake(value: unknown, caseId: string): IntakeView {
  if (
    !intakeValidator(value) ||
    value.schema !== 'caseproof-workspace-intake-v1' ||
    value.case_id !== caseId ||
    !uuid(caseId)
  )
    throw new ContractError();
  const sources = value.sources;
  if (
    sources.some((s) => !uuid(s.version_id) || !uuid(s.document_id)) ||
    new Set(sources.map((s) => s.version_id)).size !== sources.length ||
    new Set(sources.map((s) => s.filename)).size !== sources.length
  )
    throw new ContractError();
  if (
    value.readback_complete &&
    (sources.length !== 4 ||
      !value.brief_id ||
      !value.bundle_signature ||
      sources.filter(
        (s) => s.role === 'draft' && s.version_id === value.brief_id,
      ).length !== 1 ||
      sources.filter((s) => s.role === 'inventory').length !== 1)
  )
    throw new ContractError();
  if (
    value.entries.some(
      (e) =>
        e.source_version_id &&
        !sources.some(
          (s) => s.role === 'exhibit' && s.version_id === e.source_version_id,
        ),
    )
  )
    throw new ContractError();
  return value;
}
