import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { ApiClient, parseDossier } from '../../shared/api';
import { useSession } from '../../shared/session';
import { Button, Notice } from '../../shared/ui';

type Scope = { caseId: string; briefId: string; snapshot: string };
type Operation = {
  request_id: string;
  state: 'reserved' | 'active';
  version_id: string | null;
  created_at: string;
};
const id = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
function parseOperations(raw: unknown): {
  operations: Operation[];
  currentDraft: string;
} {
  if (
    !raw ||
    typeof raw !== 'object' ||
    !('operations' in raw) ||
    !Array.isArray(raw.operations) ||
    raw.operations.length > 20 ||
    !('current_draft_version_id' in raw) ||
    typeof raw.current_draft_version_id !== 'string' ||
    !id.test(raw.current_draft_version_id)
  )
    throw Error('Invalid recovery response');
  const operations = raw.operations.map((value: unknown) => {
    if (!value || typeof value !== 'object') throw Error('Invalid operation');
    const row = value as Record<string, unknown>;
    if (
      typeof row.request_id !== 'string' ||
      !id.test(row.request_id) ||
      (row.state !== 'active' && row.state !== 'reserved') ||
      typeof row.created_at !== 'string' ||
      (row.state === 'active'
        ? typeof row.version_id !== 'string' || !id.test(row.version_id)
        : row.version_id !== null)
    )
      throw Error('Invalid operation');
    return row as Operation;
  });
  return { operations, currentDraft: raw.current_draft_version_id };
}
export function CorrectionRecovery({
  api,
  scope,
  referenceId,
  onResume,
  onReady,
}: {
  api: ApiClient;
  scope: Scope;
  referenceId: string;
  onResume?: (requestId: string | null) => void;
  onReady?: (ready: boolean) => void;
}) {
  const session = useSession();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState('');
  const base = `/v2/matters/${encodeURIComponent(scope.caseId)}/briefs/${encodeURIComponent(scope.briefId)}/dossier`;
  const query = useQuery({
    queryKey: [
      'correction-operations',
      session.epoch,
      scope.caseId,
      scope.briefId,
      scope.snapshot,
      referenceId,
    ],
    queryFn: async ({ signal }) =>
      parseOperations(
        await api.get(
          `${base}/snapshots/${encodeURIComponent(scope.snapshot)}/references/${encodeURIComponent(referenceId)}/correction-operations`,
          signal,
        ),
      ),
    enabled: session.connected,
    retry: false,
  });
  useEffect(() => {
    const reserved =
      query.data?.operations.filter((item) => item.state === 'reserved') ?? [];
    onReady?.(
      query.isSuccess &&
        (reserved.length === 0 ||
          reserved.some((item) => item.request_id === selected)),
    );
  }, [query.data, query.isSuccess, selected, onReady]);
  async function recheck(version: string) {
    setBusy(true);
    setError('');
    try {
      const latest = await query.refetch();
      if (!latest.isSuccess || latest.data?.currentDraft !== version)
        throw Error('Superseded draft');
      const report = parseDossier(
        await api.post(
          `/v2/matters/${encodeURIComponent(scope.caseId)}/briefs/${encodeURIComponent(version)}/dossier/recheck`,
          {},
        ),
      );
      if (
        report.case_id !== scope.caseId ||
        report.brief_id !== version ||
        !/^[0-9a-f]{64}$/.test(report.snapshot_hash)
      )
        throw Error('Mismatch');
      navigate(
        `/matters/${encodeURIComponent(scope.caseId)}/briefs/${encodeURIComponent(version)}?snapshot=${report.snapshot_hash}`,
      );
    } catch {
      setError(
        'Unable to recheck the activated draft. Reopen the authorized draft history.',
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-label="Correction operation recovery">
      <h4>Correction operation history</h4>
      {query.isPending && <p>Checking authorized operations…</p>}
      {query.isError && (
        <Notice error>
          Operation history is unavailable. Do not start another correction
          until it is checked.
        </Notice>
      )}
      {query.data?.operations.length === 0 && (
        <p>No previous correction operation for this reference.</p>
      )}
      {query.data?.operations.map((operation) => (
        <div key={operation.request_id}>
          <p>
            {operation.state === 'active' ? 'Activated' : 'Reserved'} ·{' '}
            {operation.created_at} · {operation.request_id}
          </p>
          {operation.state === 'reserved' && onResume && (
            <label>
              <input
                type="radio"
                name="recovery-operation"
                checked={selected === operation.request_id}
                onChange={() => {
                  setSelected(operation.request_id);
                  onResume(operation.request_id);
                }}
              />
              Resume this operation using the identical replacement text
            </label>
          )}
          {operation.state === 'active' &&
            operation.version_id !== query.data?.currentDraft && (
              <p>
                Superseded version · historical read only. Recheck unavailable.
              </p>
            )}
          {operation.state === 'active' &&
            operation.version_id === query.data?.currentDraft && (
              <Button
                disabled={busy}
                onClick={() => void recheck(operation.version_id!)}
              >
                Recheck activated draft
              </Button>
            )}
        </div>
      ))}
      {error && <Notice error>{error}</Notice>}
    </section>
  );
}
