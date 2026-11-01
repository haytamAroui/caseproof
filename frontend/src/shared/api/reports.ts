import validate from './reports-generated-validator';
import { ContractError } from './contracts';
export function parseReports(
  value: unknown,
  caseId: string,
  after: string | null,
) {
  if (!validate(value) || value.case_id !== caseId) throw new ContractError();
  if (value.reports.some((r) => !Number.isFinite(Date.parse(r.created_at))))
    throw new ContractError();
  const hashes = value.reports.map((r) => r.snapshot_hash);
  if (
    new Set(hashes).size !== hashes.length ||
    hashes.some(
      (h, i) =>
        (after !== null && h <= after) || (i > 0 && h <= hashes[i - 1]!),
    ) ||
    (value.next_cursor !== null &&
      (hashes.length !== 20 || value.next_cursor !== hashes.at(-1)))
  )
    throw new ContractError();
  return value;
}
