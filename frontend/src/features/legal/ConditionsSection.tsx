import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiError, type ApiClient } from '../../shared/api';
import {
  assertConditionsSave,
  parseConditionMatches,
  parseConditionsState,
} from '../../shared/api/conditions';
import { useSession } from '../../shared/session';
import { Button, Notice } from '../../shared/ui';

const split = (v: string) =>
  v
    .split(/[\n,;]+/)
    .map((x) => x.trim())
    .filter((x) => x !== '');

/** Lawyer-defined conditions: literal words, retrieval and routing only. Never a verdict. */
export function ConditionsSection(props: {
  api: ApiClient;
  caseId: string;
  briefId: string;
}) {
  const { api, caseId, briefId } = props;
  const session = useSession();
  const stateUrl = `/v2/matters/${encodeURIComponent(caseId)}/conditions`;
  const state = useQuery({
    queryKey: ['conditions', session.epoch, caseId],
    enabled: session.connected,
    retry: false,
    queryFn: async ({ signal }) =>
      parseConditionsState(await api.get(stateUrl, signal)),
  });
  const revision = state.data?.revision ?? -1;
  const matches = useQuery({
    queryKey: ['condition-matches', session.epoch, caseId, briefId, revision],
    enabled: session.connected && state.isSuccess,
    retry: false,
    queryFn: async ({ signal }) =>
      parseConditionMatches(
        await api.get(
          `/v2/matters/${encodeURIComponent(caseId)}/briefs/${encodeURIComponent(briefId)}/conditions`,
          signal,
        ),
        { briefId },
      ),
  });
  const [form, setForm] = useState({
    id: '',
    label: '',
    question: '',
    trigger: '',
    evidence: '',
    pieces: '',
  });
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);

  async function save(next: NonNullable<typeof state.data>['conditions']) {
    if (busy || !state.data) return;
    setBusy(true);
    setMsg('Saving…');
    try {
      const body = assertConditionsSave({
        expected_revision: state.data.revision,
        conditions: next,
      });
      const sent = await api.post(stateUrl, body);
      const saved = parseConditionsState(sent);
      const fresh = await state.refetch();
      setMsg(
        fresh.data &&
          fresh.data.revision === saved.revision &&
          fresh.data.spec_sha256 === saved.spec_sha256
          ? `Saved as revision ${saved.revision} and read back from the store.`
          : 'The acknowledgement arrived but the stored revision differs. Reload and check.',
      );
    } catch (error) {
      setMsg(
        error instanceof ApiError && error.status === 409
          ? 'The conditions changed since you loaded them. Reload and edit again.'
          : error instanceof ApiError && error.status === 422
            ? 'Refused: each word needs 2 to 80 characters and ids must be unique lowercase.'
            : 'Not saved. Nothing is recorded unless the store shows it.',
      );
    } finally {
      setBusy(false);
    }
  }

  const current = state.data?.conditions ?? [];
  return (
    <>
      <h2>Conditions defined by the lawyer</h2>
      {state.isPending ? (
        <Notice>Loading conditions…</Notice>
      ) : state.isError ? (
        <Notice error>
          Conditions are unavailable. Nothing can be shown or saved.
        </Notice>
      ) : (
        <>
          <Notice>{state.data.note}</Notice>
          <p className="small">
            Revision {state.data.revision}
            {state.data.spec_sha256 && (
              <>
                , spec <code>{state.data.spec_sha256}</code>
              </>
            )}
            .
          </p>
          <ul className="matter-list legal-list" aria-label="Conditions">
            {current.map((c) => (
              <li key={c.id}>
                <strong>{c.label}</strong> <code>{c.id}</code>
                <span className="small">
                  When the brief says: {c.trigger.join(', ')}. Look in the
                  pieces for: {c.evidence.join(', ')}
                  {c.pieces.length > 0
                    ? ` (pieces: ${c.pieces.join(', ')})`
                    : ' (all readable pieces)'}
                  .
                </span>
                <Button
                  disabled={busy || current.length === 1}
                  onClick={() => {
                    void save(current.filter((x) => x.id !== c.id));
                  }}
                >
                  Remove
                </Button>
              </li>
            ))}
          </ul>
          <form
            aria-label="Add a condition"
            onSubmit={(e) => {
              e.preventDefault();
              void save([
                ...current,
                {
                  id: form.id.trim(),
                  label: form.label.trim(),
                  question: form.question.trim(),
                  trigger: split(form.trigger),
                  evidence: split(form.evidence),
                  pieces: split(form.pieces),
                },
              ]);
            }}
          >
            {(
              [
                ['id', 'Identifier (lowercase, digits, dashes)'],
                ['label', 'Label'],
                ['question', 'Question for the lawyer (optional)'],
                [
                  'trigger',
                  'Words in the brief that trigger it (comma separated)',
                ],
                ['evidence', 'Words to find in the pieces (comma separated)'],
                ['pieces', 'Only these pieces (optional, e.g. Pièce 1)'],
              ] as const
            ).map(([k, label]) => (
              <label key={k}>
                {label}
                <input
                  value={form[k]}
                  onChange={(e) => {
                    setForm({ ...form, [k]: e.target.value });
                  }}
                />
              </label>
            ))}
            <Button type="submit" disabled={busy}>
              Save condition
            </Button>
          </form>
          <div aria-live="polite">{msg}</div>
        </>
      )}
      {matches.isError ? (
        <Notice error>
          Condition matches are unavailable. No cached result is shown.
        </Notice>
      ) : matches.data ? (
        <>
          <Notice>{matches.data.scope}</Notice>
          <p className="small">
            Anchors: {matches.data.coverage.anchors}; sources read:{' '}
            {matches.data.coverage.sources_read}; not read:{' '}
            {matches.data.coverage.sources_not_read}.
          </p>
          <ul className="matter-list legal-list" aria-label="Condition anchors">
            {matches.data.anchors.map((a) => (
              <li key={a.anchor_id}>
                <strong>
                  {a.status === 'UNVERIFIED'
                    ? 'No passage found in the pieces read'
                    : 'Cannot be decided'}
                </strong>{' '}
                <code>{a.status}</code>
                <span className="small">
                  {a.label}: {a.sentence}
                </span>
                <span className="small">
                  Reason: <code>{a.reason}</code>. Pieces read:{' '}
                  {a.pieces_read.join(', ') || 'none'}
                  {a.pieces_not_read.length > 0 &&
                    `; not read: ${a.pieces_not_read.join(', ')}`}
                </span>
                {a.found.map((f) => (
                  <span className="small" key={f.excerpt_sha256 + f.piece}>
                    {f.piece}
                    {f.pdf_page
                      ? `, PDF p.${f.pdf_page}`
                      : ', page not mapped'}{' '}
                    (word “{f.term}”): {f.excerpt}
                  </span>
                ))}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </>
  );
}
