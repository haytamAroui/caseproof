import validate from './generated-validator';

const pageLabel =
  /^(?:[0-9]{1,6}|m{0,3}(?:cm|cd|d?c{0,3})(?:xc|xl|l?x{0,3})(?:ix|iv|v?i{0,3})|M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3}))$/;
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
  for (const finding of value.findings) {
    const spaces = finding.page_spaces;
    if (spaces === undefined || spaces === null) continue;
    if (!spaces || typeof spaces !== 'object' || Array.isArray(spaces))
      throw new ContractError();
    const rows = spaces as Record<string, unknown>;
    if (Object.keys(rows).sort().join(',') !== 'bundle,pdf,printed')
      throw new ContractError();
    for (const space of ['pdf', 'printed', 'bundle'] as const) {
      const raw = rows[space];
      if (!raw || typeof raw !== 'object' || Array.isArray(raw))
        throw new ContractError();
      const row = raw as Record<string, unknown>;
      if (
        Object.keys(row).sort().join(',') !== 'state,value' ||
        !['mapped', 'unmapped', 'conflicting'].includes(String(row.state))
      )
        throw new ContractError();
      if (row.state !== 'mapped' && row.value !== null)
        throw new ContractError();
      if (
        row.state === 'mapped' &&
        (space === 'pdf'
          ? !Number.isInteger(row.value) ||
            (row.value as number) < 1 ||
            (row.value as number) > 100000
          : typeof row.value !== 'string' ||
            !row.value ||
            !pageLabel.test(row.value))
      )
        throw new ContractError();
    }
    const physical = rows.pdf as Record<string, unknown>;
    if ((finding.page_mapping === 'mapped') !== (physical.state === 'mapped'))
      throw new ContractError();
  }
  return value;
}
export type { DossierView, FindingView } from './generated';
