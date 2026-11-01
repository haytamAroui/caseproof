import validate from './viewer-generated-validator';
import { ContractError } from './contracts';
export function parseViewer(
  value: unknown,
  scope: {
    caseId: string;
    briefId: string;
    snapshot: string;
    referenceId: string;
  },
) {
  if (
    !validate(value) ||
    value.case_id !== scope.caseId ||
    value.brief_id !== scope.briefId ||
    value.snapshot_hash !== scope.snapshot ||
    value.reference_id !== scope.referenceId ||
    (value.page_mapping !== 'mapped' && value.pdf_page !== null)
  )
    throw new ContractError();
  return value;
}
