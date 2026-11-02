import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router';
import { ApiClient, parseIntake } from '../../shared/api';
import type { IntakeView } from '../../shared/api';
import { useSessionController } from '../../shared/session';
import { Button, Notice, UnsavedChanges } from '../../shared/ui';
import { slots, prepareFiles } from './files';
export function IntakeScreen({ api }: { api: ApiClient }) {
  const { caseId = '' } = useParams();
  if (
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(
      caseId,
    )
  )
    return <Notice error>This matter link is invalid.</Notice>;
  return <IntakeForm key={caseId} caseId={caseId} api={api} />;
}
function IntakeForm({ api, caseId }: { api: ApiClient; caseId: string }) {
  const session = useSessionController();
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false),
    [message, setMessage] = useState('');
  const [receipt, setReceipt] = useState<IntakeView | null>(null);
  const abort = useRef<AbortController | null>(null),
    lock = useRef(false);
  useEffect(() => () => abort.current?.abort(), []);
  const query = useQuery({
    queryKey: ['intake', caseId],
    queryFn: async ({ signal }) =>
      parseIntake(
        await api.get(`/v2/workspace/intake/matters/${caseId}`, signal),
        caseId,
      ),
  });
  const data = receipt ?? (query.isError ? undefined : query.data);
  return (
    <section className="intake">
      <UnsavedChanges dirty={dirty} />
      <nav className="catalog-actions">
        <Link to="/">Permitted matters</Link>
        <Link to={`/matters/${caseId}`}>Preserved reports</Link>
      </nav>
      <h1>Preserve the source bundle</h1>
      <Notice>
        Development intake accepts one DOCX draft, one UTF-8 text inventory and
        two PDF exhibits, including scans. Maximum 5 MiB per file, 12 MB
        combined and 64 pages per PDF. The inventory is limited to 1 MiB and 512
        distinct Stuk/Pièce identities. All four files are checked before any
        original is written. Preservation does not confirm inventory or verify
        claims.
      </Notice>
      {query.isPending && <Notice>Reading current source state…</Notice>}
      {query.isError && receipt && (
        <Notice error>
          The previous receipt is historical. Current authorization and source
          availability could not be refreshed; do not treat it as current proof.
        </Notice>
      )}
      {query.isError && (
        <Notice error>
          Current intake could not be read. Reconnect if needed, then refresh.
          To recover an interrupted transfer, reselect the exact four originals;
          registration and readback reconcile their immutable identity.
        </Notice>
      )}
      <Button
        disabled={busy || query.isFetching}
        onClick={() => {
          setReceipt(null);
          void query.refetch();
        }}
      >
        Refresh source state
      </Button>
      {data && data.sources.length > 0 && (
        <section aria-label="Registered original status">
          <h2>Registered originals and signed readback</h2>
          <Notice>
            Each original is registered, but registration alone does not prove
            that its bytes are preserved. Unknown includes missing or masked
            storage. A mismatch cannot be considered preserved. Processing is
            separate from source identity and may need OCR review.
          </Notice>
          <ul className="matter-list">
            {data.sources.map((s) => (
              <li key={s.version_id}>
                <strong>{s.filename}</strong>
                <p>
                  {s.role} · registered · readback{' '}
                  {s.readback ??
                    (data.readback_complete ? 'verified' : 'unknown')}
                  {' · '}processing {s.processing.replaceAll('_', ' ')}
                  {s.page_count != null ? ` · ${s.page_count} PDF pages` : ''}
                </p>
                {s.processing === 'partial' && (
                  <p>Some pages still require OCR or processing review.</p>
                )}
                {s.processing === 'unavailable' && (
                  <p>
                    Processing has not been established. Do not assume OCR
                    completed.
                  </p>
                )}
                <details>
                  <summary>Registered original provenance</summary>
                  <p>
                    Version <code>{s.version_id}</code>
                  </p>
                  <p>
                    SHA-256 <code>{s.sha256}</code>
                  </p>
                </details>
              </li>
            ))}
          </ul>
        </section>
      )}
      {data?.readback_complete && !query.isError ? (
        <>
          <Notice>
            All originals passed fresh authorized hash readback. Processing and
            inventory confirmation remain separate.
          </Notice>
          <Link to={`/matters/${caseId}/inventory`}>
            Review inventory and page mappings
          </Link>
        </>
      ) : (
        <form
          noValidate
          onSubmit={async (event) => {
            event.preventDefault();
            if (lock.current) return;
            const form = event.currentTarget,
              fd = new FormData(form);
            const files = slots.map((_, i) => fd.get(`file-${i}`));
            const missing = files.findIndex(
              (f) => !(f instanceof File) || !f.size,
            );
            if (missing >= 0) {
              setMessage(
                'Choose all four originals before preserving the bundle.',
              );
              (
                form.elements.namedItem(`file-${missing}`) as HTMLElement
              ).focus();
              return;
            }
            const control = new AbortController();
            abort.current = control;
            lock.current = true;
            setBusy(true);
            setMessage('Reading and hashing all four originals…');
            const epoch = session.getSnapshot().epoch;
            try {
              const prepared = await prepareFiles(
                files as File[],
                control.signal,
              );
              session.assert(epoch);
              setMessage(
                'Validating formats, preserving originals and verifying signed readback…',
              );
              const command = {
                request_id: crypto.randomUUID(),
                files: prepared,
              };
              parseIntake(
                await api.post(
                  `/v2/workspace/intake/matters/${caseId}/reservations`,
                  command,
                  control.signal,
                ),
                caseId,
              );
              const result = parseIntake(
                await api.post(
                  `/v2/workspace/intake/matters/${caseId}/sources`,
                  { request_id: crypto.randomUUID(), files: prepared },
                  control.signal,
                ),
                caseId,
              );
              session.assert(epoch);
              if (!result.readback_complete)
                throw Error('No complete readback receipt');
              setDirty(false);
              setReceipt(result);
              setMessage('Original preservation acknowledged by the backend.');
              form.reset();
            } catch {
              if (session.getSnapshot().epoch === epoch)
                setMessage(
                  control.signal.aborted
                    ? 'Transfer stopped. Server outcome may be partial. Refresh or reselect the exact originals to reconcile; existing originals will not be overwritten.'
                    : 'No completed intake receipt was received. Check file names, formats and limits. If transfer was interrupted, reselect the exact originals and reconcile.',
                );
            } finally {
              lock.current = false;
              if (session.getSnapshot().epoch === epoch) setBusy(false);
            }
          }}
        >
          {slots.map((slot, i) => (
            <label key={slot.label}>
              {slot.label}
              <input
                name={`file-${i}`}
                type="file"
                onChange={() => setDirty(true)}
                accept={slot.accept}
                disabled={busy}
                aria-describedby="intake-status"
              />
            </label>
          ))}
          <div className="catalog-actions">
            <Button type="submit" disabled={busy}>
              {busy
                ? 'Preserving originals…'
                : 'Preserve or reconcile originals'}
            </Button>
            {busy && (
              <Button onClick={() => abort.current?.abort()}>
                Stop transfer
              </Button>
            )}
          </div>
        </form>
      )}
      <div id="intake-status">{message && <Notice>{message}</Notice>}</div>
    </section>
  );
}
