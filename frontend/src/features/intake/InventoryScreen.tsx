import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router';
import {
  ApiClient,
  ApiError,
  parseIntake,
  parseDossier,
} from '../../shared/api';
import type {
  IntakeView,
  IdentityConfirmation,
  PageConfirmation,
} from '../../shared/api';
import { useSessionController } from '../../shared/session';
import { Button, Notice, UnsavedChanges } from '../../shared/ui';
function confirmationFingerprint(
  entries: IdentityConfirmation[],
  complete: boolean,
) {
  return JSON.stringify([
    complete,
    entries.map((e) => [
      e.label,
      e.number,
      e.source_version_id ?? null,
      (e.pages ?? []).map((p) => [p.space, p.label, p.pdf_page, p.rationale]),
    ]),
  ]);
}
export function InventoryScreen({ api }: { api: ApiClient }) {
  const { caseId = '' } = useParams();
  const valid =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(
      caseId,
    );
  const query = useQuery({
    enabled: valid,
    queryKey: ['inventory', caseId],
    queryFn: async ({ signal }) =>
      parseIntake(
        await api.get(`/v2/workspace/intake/matters/${caseId}`, signal),
        caseId,
      ),
  });
  if (!valid) return <Notice error>This matter link is invalid.</Notice>;
  return (
    <section className="intake">
      <Link to={`/matters/${caseId}/sources`}>Back to sources</Link>
      <h1>Confirm inventory</h1>
      <Button
        disabled={query.isFetching}
        onClick={() => {
          void query.refetch();
        }}
      >
        Refresh inventory
      </Button>
      {query.isPending ? (
        <Notice>Reading inventory and current revision…</Notice>
      ) : query.isError ? (
        <>
          <Notice error>
            Inventory is unavailable. No cached confirmation can be submitted.
          </Notice>
          <Button
            onClick={() => {
              void query.refetch();
            }}
          >
            Refresh inventory
          </Button>
        </>
      ) : !query.data.readback_complete ? (
        <Notice>Preserve all originals before confirming inventory.</Notice>
      ) : (
        <InventoryForm
          key={`${caseId}:${query.data.bundle_signature}:${query.data.confirmation_id ?? ''}`}
          api={api}
          data={query.data}
        />
      )}
    </section>
  );
}
function InventoryForm({ api, data }: { api: ApiClient; data: IntakeView }) {
  const session = useSessionController(),
    navigate = useNavigate();
  const [entries, setEntries] = useState<IdentityConfirmation[]>(data.entries);
  const [complete, setComplete] = useState(data.inventory_complete),
    [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [saved, setSaved] = useState(Boolean(data.confirmation_id)),
    [message, setMessage] = useState('');
  const frozen = useRef<{ request: string; fingerprint: string } | null>(null);
  const abort = useRef(new AbortController()),
    lock = useRef(false);
  useEffect(() => {
    const a = abort.current;
    return () => a.abort();
  }, []);
  const [dirty, setDirty] = useState(false);
  function update(index: number, entry: IdentityConfirmation) {
    setDirty(true);
    setSaved(false);
    setEntries((current) => current.map((e, i) => (i === index ? entry : e)));
  }
  const exhibits = data.sources.filter((s) => s.role === 'exhibit');
  const base = `/v2/matters/${data.case_id}/briefs/${data.brief_id}/dossier`;
  async function confirm() {
    if (lock.current) return;
    const fingerprint = confirmationFingerprint(entries, complete);
    if (frozen.current && frozen.current.fingerprint !== fingerprint) {
      setMessage(
        'Reconcile the previous confirmation before changing its contents. Refresh inventory to load the current server revision.',
      );
      return;
    }
    setUncertain(true);
    frozen.current ??= { request: crypto.randomUUID(), fingerprint };
    const request = frozen.current.request,
      epoch = session.getSnapshot().epoch;
    lock.current = true;
    setBusy(true);
    setMessage('Saving confirmation…');
    try {
      await api.post(
        base + '/confirmation',
        {
          request_id: request,
          bundle_signature: data.bundle_signature,
          inventory_complete: complete,
          entries,
        },
        abort.current.signal,
      );
      const current = parseIntake(
        await api.get(
          `/v2/workspace/intake/matters/${data.case_id}`,
          abort.current.signal,
        ),
        data.case_id,
      );
      session.assert(epoch);
      if (
        current.confirmation_id !== request ||
        current.bundle_signature !== data.bundle_signature ||
        current.inventory_complete !== complete ||
        confirmationFingerprint(current.entries, current.inventory_complete) !==
          fingerprint
      )
        throw Error('Confirmation differs');
      frozen.current = null;
      setUncertain(false);
      setDirty(false);
      setSaved(true);
      setMessage(
        'Inventory confirmation saved and freshly read back. Unbound exhibits and uncertain page mappings remain unresolved.',
      );
    } catch (error) {
      if (
        !abort.current.signal.aborted &&
        session.getSnapshot().epoch === epoch
      ) {
        if (error instanceof ApiError && error.status === 422) {
          frozen.current = null;
          setUncertain(false);
          setMessage(
            'The confirmation failed validation. Correct the entries or page mappings before saving again.',
          );
        } else {
          setMessage(
            'Confirmation was rejected, stale or has an unknown outcome. Reconcile the unchanged confirmation, or refresh inventory to inspect the current revision.',
          );
        }
      }
    } finally {
      lock.current = false;
      if (
        !abort.current.signal.aborted &&
        session.getSnapshot().epoch === epoch
      )
        setBusy(false);
    }
  }
  return (
    <>
      <UnsavedChanges dirty={dirty} />
      <Notice>
        Entries are candidates detected in the preserved inventory. Bind each
        exhibit explicitly. Leave a source unbound when missing or ambiguous. A
        completeness declaration describes the inventory, not claim support,
        source authenticity or complete OCR.
      </Notice>
      {!entries.length && (
        <Notice>
          No supported Stuk/Pièce identities were detected. This is not proof
          that the inventory is complete; unsupported English Exhibit labels
          require human review.
        </Notice>
      )}
      <fieldset disabled={busy}>
        <legend>Inventory entries ({entries.length})</legend>
        {entries.map((entry, index) => (
          <fieldset key={`${entry.label}:${entry.number}:${index}`}>
            <legend>
              {entry.label} {entry.number}
            </legend>
            <label>
              Preserved exhibit
              <select
                value={entry.source_version_id ?? ''}
                onChange={(e) =>
                  update(index, {
                    ...entry,
                    source_version_id: e.target.value || null,
                    pages: [],
                  })
                }
              >
                <option value="">Unbound / source missing or ambiguous</option>
                {exhibits.map((s) => (
                  <option key={s.version_id} value={s.version_id}>
                    {s.filename}
                  </option>
                ))}
              </select>
            </label>
            <Button
              onClick={() => {
                setDirty(true);
                setSaved(false);
                setEntries((current) => [
                  ...current,
                  {
                    label: entry.label,
                    number: entry.number,
                    source_version_id: null,
                    pages: [],
                  },
                ]);
              }}
              disabled={entries.length >= 512}
            >
              Add alternative source binding
            </Button>
            {entries.filter(
              (e) => e.label === entry.label && e.number === entry.number,
            ).length > 1 && (
              <Button
                onClick={() => {
                  setDirty(true);
                  setSaved(false);
                  setEntries((current) =>
                    current.filter((_, i) => i !== index),
                  );
                }}
              >
                Remove alternative binding for {entry.label} {entry.number}
              </Button>
            )}
            <PageMappings
              pages={entry.pages ?? []}
              max={
                exhibits.find((s) => s.version_id === entry.source_version_id)
                  ?.page_count ?? 0
              }
              change={(pages) => update(index, { ...entry, pages })}
            />
          </fieldset>
        ))}
      </fieldset>
      <label className="check-label">
        <input
          type="checkbox"
          checked={complete}
          disabled={busy}
          onChange={(e) => {
            setDirty(true);
            setComplete(e.target.checked);
            setSaved(false);
          }}
        />
        I reviewed the inventory and declare it complete for this preserved
        bundle.
      </label>
      <div className="catalog-actions">
        <Button
          onClick={() => {
            void confirm();
          }}
          disabled={busy}
        >
          {busy
            ? 'Saving confirmation…'
            : uncertain
              ? 'Reconcile confirmation'
              : 'Save inventory confirmation'}
        </Button>
        <Button
          disabled={busy || !saved}
          onClick={async () => {
            if (lock.current) return;
            lock.current = true;
            setBusy(true);
            const epoch = session.getSnapshot().epoch;
            try {
              const raw = await api.post(
                base + '/checks',
                {},
                abort.current.signal,
              );
              const report = parseDossier(raw);
              session.assert(epoch);
              if (
                report.case_id !== data.case_id ||
                report.brief_id !== data.brief_id
              )
                throw Error('Wrong check scope');
              await navigate(
                `/matters/${data.case_id}/briefs/${data.brief_id}?snapshot=${report.snapshot_hash}`,
              );
            } catch {
              if (
                !abort.current.signal.aborted &&
                session.getSnapshot().epoch === epoch
              )
                setMessage(
                  'Check could not be opened. Refresh preserved reports before starting another check.',
                );
            } finally {
              lock.current = false;
              if (
                !abort.current.signal.aborted &&
                session.getSnapshot().epoch === epoch
              )
                setBusy(false);
            }
          }}
        >
          Run explicit check
        </Button>
      </div>
      {message && <Notice>{message}</Notice>}
    </>
  );
}
function PageMappings({
  pages,
  max,
  change,
}: {
  pages: PageConfirmation[];
  max: number;
  change: (p: PageConfirmation[]) => void;
}) {
  const [error, setError] = useState('');
  return (
    <section>
      <h2>Printed / bundle page mappings</h2>
      <p>
        Physical PDF pages are separate. Add only mappings you inspected; no
        offset is inferred.
      </p>
      <ul>
        {pages.map((p, i) => (
          <li key={i}>
            {p.space} {p.label} → PDF {p.pdf_page}: {p.rationale}{' '}
            <Button onClick={() => change(pages.filter((_, n) => n !== i))}>
              Remove mapping {i + 1}
            </Button>
          </li>
        ))}
      </ul>
      <div className="mapping-fields">
        <label>
          Page space
          <select name="space">
            <option value="printed">Printed</option>
            <option value="bundle">Bundle</option>
          </select>
        </label>
        <label>
          Page label
          <input name="page-label" inputMode="numeric" maxLength={6} />
        </label>
        <label>
          Physical PDF page
          <input name="pdf-page" type="number" min={1} max={max} />
        </label>
        <label>
          Mapping rationale
          <input name="mapping-rationale" maxLength={500} />
        </label>
        <Button
          disabled={!max || pages.length >= 128}
          onClick={(event) => {
            const area = event.currentTarget.closest('.mapping-fields')!;
            const value = (name: string) =>
              (
                area.querySelector(`[name="${name}"]`) as
                  HTMLInputElement | HTMLSelectElement
              ).value;
            const label = value('page-label'),
              pdf = Number(value('pdf-page')),
              rationale = value('mapping-rationale').trim(),
              space = value('space') as 'printed' | 'bundle';
            if (
              !/^\d{1,6}$/.test(label) ||
              !Number.isInteger(pdf) ||
              pdf < 1 ||
              pdf > max ||
              rationale.length < 3 ||
              pages.some((p) => p.space === space && p.label === label)
            ) {
              setError(
                'Use a unique numeric label, an existing PDF page and a rationale of at least three characters.',
              );
              return;
            }
            change([...pages, { label, pdf_page: pdf, rationale, space }]);
            setError('');
          }}
        >
          Add inspected mapping
        </Button>
      </div>
      {error && <Notice error>{error}</Notice>}
    </section>
  );
}
