import validate from './matters-generated-validator';
import type { MatterCatalogView } from './matters-generated';
import { ContractError } from './contracts';

export function parseMatters(value: unknown): MatterCatalogView {
  if (!validate(value)) throw new ContractError();
  if (
    value.matters.some(
      (m) => m.case_id === '00000000-0000-0000-0000-000000000000',
    )
  )
    throw new ContractError();
  if (
    new Set(value.matters.map((m) => m.case_id)).size !== value.matters.length
  )
    throw new ContractError();
  return value;
}
