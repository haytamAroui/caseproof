import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiError, type ApiClient } from '../../shared/api';
import {
  assertClearbriefCommand,
  parseClearbriefReceipt,
  parseClearbriefState,
} from '../../shared/api/clearbriefReview';
import { useSession } from '../../shared/session';
import { Button, Notice } from '../../shared/ui';

const CHOICES = [
  ['confirmed_candidate', 'I confirm this finding exists as shown'],
  ['dismissed', 'I dismiss this finding'],
  ['needs_information', 'More information is needed'],
] as const;

export function ReviewBox({
  api,
  caseId,
  briefId,
  snapshot,
  observationId,
}: {
  api: ApiClient;
  caseId: string;
  briefId: string;
  snapshot: string;
  observationId: string;
}) {
  const session = useSession();
  const base = `/v2/matters/${encodeURIComponent(caseId)}/briefs/${encodeURIComponent(briefId)}/review`;
  const state = useQuery({
    queryKey: ['clearbrief-review', session.epoch, caseId, briefId],
    enabled: session.connected,
    queryFn: async ({ signal }) =>
      parseClearbriefState(await api.get(base, signal), { caseId, briefId }),
  });
  const [choice, setChoice] =
    useState<(typeof CHOICES)[number][0]>('needs_information');
  const [why, setWhy] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const mine = state.data?.decisions.filter(
    (d) => d.observation_id === observationId,
  );
  const stale =
    state.data !== undefined && state.data.snapshot_hash !== snapshot;
  async function submit() {
    if (busy || !state.data || stale) return;
    setBusy(true);
    setMsg('Saving…');
    try {
      const command = assertClearbriefCommand({
        snapshot_hash: snapshot,
        observation_id: observationId,
        request_id: crypto.randomUUID(),
        expected_revision: state.data.revision,
        disposition: choice,
        rationale: why.trim(),
      });
      parseClearbriefReceipt(
        await api.post(base, command, undefined, {
          snapshot,
          idempotencyKey: command.request_id,
        }),
        { snapshot },
      );
      const fresh = await state.refetch();
      const ok = fresh.data?.decisions.some(
        (d) =>
          d.observation_id === observationId &&
          d.disposition === command.disposition &&
          d.rationale === command.rationale,
      );
      setMsg(
        ok
          ? 'Saved and confirmed from the signed review ledger.'
          : 'The acknowledgement arrived but the ledger does not show it. Do not retry with a changed statement; reload and check.',
      );
      if (ok) setWhy('');
    } catch (error) {
      setMsg(
        error instanceof ApiError &&
          (error.status === 409 || error.status === 412)
          ? 'The review changed or the draft was rechecked. Reload and decide again.'
          : 'Not saved. Nothing is recorded unless the ledger shows it.',
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="legal-review" role="group" aria-label="Reviewer statement">
      <h4>Reviewer statement</h4>
      <p className="small">
        A person&apos;s statement about this finding. It does not change the
        status above and does not approve filing.
      </p>
      {state.isError && (
        <Notice error>
          The review ledger is unavailable. Nothing can be recorded.
        </Notice>
      )}
      {stale && (
        <Notice error>
          The ledger is bound to a different check. Reload before deciding.
        </Notice>
      )}
      {mine?.map((d, i) => (
        <p className="small" key={i}>
          Recorded: <code>{d.disposition}</code>. Reason: {d.rationale}
        </p>
      ))}
      <label>
        Statement
        <select
          value={choice}
          onChange={(e) => setChoice(e.target.value as typeof choice)}
        >
          {CHOICES.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </label>
      <label>
        Reason (required)
        <textarea
          value={why}
          maxLength={2000}
          onChange={(e) => setWhy(e.target.value)}
        />
      </label>
      <Button
        onClick={() => {
          void submit();
        }}
        disabled={busy || why.trim() === '' || !state.data || stale}
      >
        Record statement
      </Button>
      <p role="status">{msg}</p>
    </div>
  );
}
