import {
  ApiClient,
  ApiError,
  ContractError,
  parseDossier,
} from '../../shared/api';
import type { DossierView } from '../../shared/api';

export interface ReportScope {
  caseId: string;
  briefId: string;
  snapshot: string;
}
export interface OpenedReport {
  report: DossierView;
  mode: 'current' | 'historical_read_only';
}
export async function readReport(
  api: ApiClient,
  scope: ReportScope,
  signal: AbortSignal,
): Promise<OpenedReport> {
  const base = `/v2/matters/${encodeURIComponent(scope.caseId)}/briefs/${encodeURIComponent(scope.briefId)}/dossier`;
  let report: DossierView;
  let mode: OpenedReport['mode'] = 'current';
  try {
    report = parseDossier(
      await api.get(
        `${base}?snapshot_hash=${encodeURIComponent(scope.snapshot)}`,
        signal,
      ),
    );
  } catch (error) {
    // Only a confirmed stale response permits the read-only historical path.
    // Authorization denials and service failures never trigger a fallback.
    if (!(error instanceof ApiError) || error.status !== 409) throw error;
    const response = await api.get(
      `${base}/history/${encodeURIComponent(scope.snapshot)}`,
      signal,
    );
    if (!response || typeof response !== 'object') throw new ContractError();
    const historical = response as Record<string, unknown>;
    if (
      historical.mode !== 'historical_read_only' ||
      historical.currentness !== 'not_asserted' ||
      historical.source_availability !== 'not_assessed'
    )
      throw new ContractError();
    report = parseDossier(historical.report);
    mode = 'historical_read_only';
  }
  if (
    report.case_id !== scope.caseId ||
    report.brief_id !== scope.briefId ||
    report.snapshot_hash !== scope.snapshot
  )
    throw new ContractError();
  return { report, mode };
}
