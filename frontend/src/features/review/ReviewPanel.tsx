import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { ApiClient, FindingView } from '../../shared/api';
import {
  assertReviewCommand,
  parseReviewLedger,
  parseReviewWriteReceipt,
} from '../../shared/api/review';
import type { VisualDecisionBody } from '../../shared/api/review';
import { ApiError } from '../../shared/api';
import { useSession, useSessionController } from '../../shared/session';
import { Button, Notice, UnsavedChanges } from '../../shared/ui';

type Scope = { caseId: string; briefId: string; snapshot: string };
type ReviewDecision = VisualDecisionBody['decision'];
const dispositions: { id: ReviewDecision; label: string }[] = [
  { id: 'CONFIRMED_SUPPORTED', label: 'Confirm supported after inspection' },
  { id: 'CONFIRMED_QUALIFIED', label: 'Qualify the support' },
  { id: 'CONFIRMED_CONTRADICTED', label: 'Confirm contradiction' },
];

function requiredRegions(finding: FindingView): string[] | null {
  const raw = finding.visual_assessment;
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
  const values = (raw as Record<string, unknown>).regions;
  if (!Array.isArray(values) || values.length > 96) return null;
  const ids = values.map((region) =>
    region && typeof region === 'object' && !Array.isArray(region)
      ? (region as Record<string, unknown>).region_id
      : null,
  );
  if (ids.some((id) => typeof id !== 'string' || !/^[0-9a-f]{64}$/.test(id)))
    return null;
  if (new Set(ids).size !== ids.length) return null;
  return ids as string[];
}

/** Browser collects intent only; signed backend is sole review authority. */
export function ReviewPanel({
  api,
  scope,
  finding,
  inspected,
  onNext,
}: {
  api: ApiClient;
  scope: Scope;
  finding: FindingView;
  inspected: boolean;
  onNext?: (() => void) | undefined;
}) {
  const session = useSession();
  const controller = useSessionController();
  const base = `/v2/matters/${encodeURIComponent(scope.caseId)}/briefs/${encodeURIComponent(scope.briefId)}/dossier`;
  const ledger = useQuery({
    queryKey: [
      'review-ledger',
      session.epoch,
      scope.caseId,
      scope.briefId,
      scope.snapshot,
    ],
    queryFn: async ({ signal }) =>
      parseReviewLedger(
        await api.get(
          `${base}/reviews?snapshot_hash=${scope.snapshot}`,
          signal,
        ),
        scope,
      ),
    enabled: session.connected,
  });
  // A reviewer must choose explicitly: no preselected affirmative result.
  const [decision, setDecision] = useState<ReviewDecision | null>(null);
  const [rationale, setRationale] = useState('');
  const [confirmed, setConfirmed] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<
    'idle' | 'unknown' | 'rejected' | 'saved'
  >('idle');
  const [message, setMessage] = useState('');
  const [submitted, setSubmitted] = useState<VisualDecisionBody | null>(null);
  const regions = requiredRegions(finding);
  const rows =
    ledger.data?.decisions.filter(
      (row) => row.reference_id === finding.reference_id,
    ) ?? [];
  const saved =
    submitted &&
    ledger.data?.decisions.some(
      (row) =>
        row.request_id === submitted?.request_id &&
        row.reference_id === submitted.reference_id &&
        row.decision === submitted.decision &&
        row.rationale === submitted.rationale &&
        JSON.stringify(row.reviewed_region_ids) ===
          JSON.stringify(submitted.reviewed_region_ids ?? []),
    );
  const dirty = Boolean(rationale.trim()) && outcome !== 'saved' && !saved;

  async function reconcile() {
    try {
      const result = await ledger.refetch();
      if (result.isError || !result.data)
        throw new Error('Ledger could not be reopened');
      const current = submitted;
      if (
        current &&
        result.data.decisions.some(
          (row) =>
            row.request_id === current.request_id &&
            row.reference_id === current.reference_id &&
            row.decision === current.decision &&
            row.rationale === current.rationale &&
            JSON.stringify(row.reviewed_region_ids) ===
              JSON.stringify(current.reviewed_region_ids ?? []),
        )
      ) {
        setOutcome('saved');
        setMessage(
          'The exact decision is persisted in the authorized review ledger.',
        );
      } else {
        setOutcome('unknown');
        setMessage(
          'No matching receipt was found. The outcome remains unresolved. Only the identical request can be retried.',
        );
      }
    } catch {
      setOutcome('unknown');
      setMessage(
        'Review receipt could not be checked. Do not submit a changed decision.',
      );
    }
  }
  async function send(command: VisualDecisionBody) {
    if (busy) return;
    const epoch = controller.getSnapshot().epoch;
    setBusy(true);
    setMessage('Submitting the unchanged authorized decision…');
    try {
      const response = await api.post(`${base}/reviews`, command, undefined, {
        snapshot: scope.snapshot,
        idempotencyKey: command.request_id,
      });
      controller.assert(epoch);
      parseReviewWriteReceipt(response, command);
      const updated = await ledger.refetch();
      if (
        updated.isError ||
        !updated.data ||
        !updated.data.decisions.some(
          (row) =>
            row.request_id === command.request_id &&
            row.reference_id === command.reference_id &&
            row.decision === command.decision &&
            row.rationale === command.rationale &&
            JSON.stringify(row.reviewed_region_ids) ===
              JSON.stringify(command.reviewed_region_ids ?? []),
        )
      ) {
        setOutcome('unknown');
        setMessage(
          'The acknowledgement was received, but the durable ledger is not confirmed. Reconcile before proceeding.',
        );
      } else {
        setOutcome('saved');
        setMessage(
          'Decision saved and confirmed from the current signed ledger.',
        );
      }
    } catch (error) {
      if (
        error instanceof ApiError &&
        (error.status === 409 || error.status === 412)
      ) {
        setOutcome('rejected');
        setMessage(
          'The snapshot or review revision changed. Reopen the current report before any new decision.',
        );
      } else {
        setOutcome('unknown');
        setMessage(
          'The write outcome is unknown. Check the durable receipt; no automatic retry was attempted.',
        );
      }
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="review-panel" aria-label="Human review">
      <UnsavedChanges dirty={dirty} />
      <h3>Human decision and durable receipt</h3>
      <Notice>
        Machine findings remain unchanged. This is a separately attributable
        human decision, not a legal certification.
      </Notice>
      {ledger.isPending ? (
        <Notice>Reading current human review ledger…</Notice>
      ) : ledger.isError ? (
        <Notice error>
          Review ledger unavailable. A decision cannot be safely saved.
        </Notice>
      ) : (
        <div>
          {rows.length === 0 ? (
            <p>No recorded human decision for this reference.</p>
          ) : (
            <ul aria-label="Saved review history">
              {rows.map((row) => (
                <li key={row.request_id}>
                  {row.decision.replaceAll('_', ' ')} — {row.rationale}{' '}
                  <small>
                    Reviewer {row.reviewer_id}, {row.timestamp}, request{' '}
                    {row.request_id}
                  </small>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {regions === null && (
        <Notice error>
          Visual region metadata is missing or unsupported. Do not attest the
          source in this view.
        </Notice>
      )}
      {regions && regions.length > 0 && (
        <fieldset>
          <legend>
            Explicitly inspected source regions ({confirmed.length}/
            {regions.length})
          </legend>
          {regions.map((id, index) => (
            <label key={id}>
              <input
                type="checkbox"
                checked={confirmed.includes(id)}
                disabled={!inspected || Boolean(submitted)}
                onChange={(event) =>
                  setConfirmed((old) =>
                    event.target.checked
                      ? [...old, id]
                      : old.filter((r) => r !== id),
                  )
                }
              />
              Region {index + 1} — {id.slice(0, 12)}
            </label>
          ))}
        </fieldset>
      )}
      {!inspected && (
        <Notice>
          Open and inspect the preserved original reference page before
          recording a decision.
        </Notice>
      )}
      <fieldset disabled={busy || Boolean(submitted)}>
        <legend>Disposition — none selected by default</legend>
        {decision === null && (
          <p role="status">Not assessed. Select a disposition only after examining the preserved source and relevant context.</p>
        )}
        {dispositions.map(({ id, label }) => (
          <label key={id}>
            <input
              type="radio"
              name={`disposition-${finding.reference_id}`}
              value={id}
              checked={decision === id}
              onChange={() => setDecision(id)}
            />
            {label}
          </label>
        ))}
      </fieldset>
      <label>
        Rationale (required, visible to authorized reviewers)
        <textarea
          rows={3}
          maxLength={2000}
          value={rationale}
          disabled={busy || Boolean(submitted)}
          onChange={(event) => setRationale(event.target.value)}
        />
      </label>
      {message && (
        <Notice error={outcome === 'unknown' || outcome === 'rejected'}>
          {message}
        </Notice>
      )}
      <div className="catalog-actions">
        <Button
          disabled={
            busy ||
            ledger.isPending ||
            ledger.isError ||
            !inspected ||
            regions === null ||
            confirmed.length !== regions.length ||
            !rationale.trim() ||
            decision === null ||
            Boolean(submitted) ||
            (decision === 'CONFIRMED_SUPPORTED' &&
              (finding.page_mapping !== 'mapped' ||
                finding.identity !== 'resolved'))
          }
          onClick={() => {
            try {
              const command = assertReviewCommand({
                snapshot_hash: scope.snapshot,
                reference_id: finding.reference_id,
                request_id: crypto.randomUUID(),
                decision,
                rationale: rationale.trim(),
                reviewed_region_ids: [...confirmed].sort(),
              });
              setSubmitted(command);
              void send(command);
            } catch {
              setMessage(
                'The decision could not be validated. No write was sent.',
              );
            }
          }}
        >
          Save human decision
        </Button>
        {submitted && outcome !== 'saved' && (
          <>
            <Button disabled={busy} onClick={() => void reconcile()}>
              Reconcile durable receipt
            </Button>
            {outcome === 'unknown' && (
              <Button
                disabled={busy || ledger.isError || !inspected}
                onClick={() => {
                  if (submitted) void send(submitted);
                }}
              >
                Retry identical request
              </Button>
            )}
          </>
        )}
      </div>
      {(outcome === 'saved' || saved) && (
        <div role="status">
          <p>Saved. Your decision is confirmed from the durable ledger.</p>
          {onNext && <Button onClick={onNext}>Save &amp; Next finding</Button>}
        </div>
      )}
    </section>
  );
}
