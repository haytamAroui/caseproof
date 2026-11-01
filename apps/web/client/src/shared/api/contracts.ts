import validate from './generated-validator';
import type { DossierView } from './generated';
export class ContractError extends Error {
  constructor() {
    super(
      'The report format changed. Reload after the application is updated.',
    );
  }
}
export function parseDossier(value: unknown): DossierView {
  if (!validate(value)) throw new ContractError();
  const ids = value.findings.map((f) => f.reference_id);
  if (new Set(ids).size !== ids.length) throw new ContractError();
  return value;
}
export type { DossierView, FindingView } from './generated';
