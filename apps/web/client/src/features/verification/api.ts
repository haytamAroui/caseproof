import { ApiClient, ContractError, parseDossier } from '../../shared/api';
export interface ReportScope {
  caseId: string;
  briefId: string;
  snapshot: string;
}
export async function readReport(
  api: ApiClient,
  scope: ReportScope,
  signal: AbortSignal,
) {
  const path = `/v2/matters/${encodeURIComponent(scope.caseId)}/briefs/${encodeURIComponent(scope.briefId)}/dossier?snapshot_hash=${encodeURIComponent(scope.snapshot)}`;
  const report = parseDossier(await api.get(path, signal));
  if (
    report.case_id !== scope.caseId ||
    report.brief_id !== scope.briefId ||
    report.snapshot_hash !== scope.snapshot
  )
    throw new ContractError();
  return report;
}
