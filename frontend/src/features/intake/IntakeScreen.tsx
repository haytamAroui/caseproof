import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router';
import { ApiClient, ApiError, parseIntake } from '../../shared/api';
import type { IntakeView } from '../../shared/api';
import { useSessionController } from '../../shared/session';
import { Button, Notice, UnsavedChanges } from '../../shared/ui';
import capacity from '../../shared/api/capacity-policy.json';
import {
  IntakeValidationError,
  slots,
  prepareFiles,
  type IntakeFileIssue,
} from './files';
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
  const [fileIssues, setFileIssues] = useState<IntakeFileIssue[]>([]);
  const [validCheckedFiles, setValidCheckedFiles] = useState<string[]>([]);
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
        two PDF exhibits, including scans. Development policy {capacity.schema}:
        maximum {Math.floor(capacity.max_source_bytes / 1048576)} MiB per file,{' '}
        {capacity.max_intake_bytes.toLocaleString('en-GB')} bytes combined and{' '}
        {capacity.max_pdf_pages_per_source} physical pages per PDF. Inventory:{' '}
        {Math.floor(capacity.max_inventory_bytes / 1048576)} MiB and{' '}
        {capacity.max_inventory_identities} distinct Stuk/Pièce identities. This
        is not an approved 150- or 200-page full-journey pilot limit. All four
        files are checked before any originals are written. Preservation does
        not confirm inventory or verify claims.
      </Notice>
      <Notice>
        Signed development mode sends original document bytes and review/source
        metadata over HTTPS from this local application to configured Supabase
        Auth, private Storage and database services. This is not offline or
        zero-egress. The isolated OCR worker does not restrict the API or
        browser network paths. Do not upload confidential client files before
        the data owner has approved processing rights, location, retention,
        backups, access and contractual terms.
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
            setFileIssues([]);
            setValidCheckedFiles([]);
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
              setFileIssues([]);
              setValidCheckedFiles([]);
              setMessage('Original preservation acknowledged by the backend.');
              form.reset();
            } catch (error) {
              if (session.getSnapshot().epoch === epoch) {
                if (
                  error instanceof IntakeValidationError ||
                  (error instanceof ApiError && error.fileErrors.length > 0)
                ) {
                  setFileIssues(error.fileErrors);
                  setValidCheckedFiles(error.validFiles);
                  setMessage(
                    'No completed intake receipt was received. One or more files failed fail-closed intake validation; replace the rejected file(s) while keeping valid files selected.',
                  );
                } else {
                  setMessage(
                    control.signal.aborted
                      ? 'Transfer stopped. Server outcome may be partial. Refresh or reselect the exact originals to reconcile; existing originals will not be overwritten.'
                      : 'No completed intake receipt was received. Check file names, formats and limits. If transfer was interrupted, reselect the exact originals and reconcile.',
                  );
                }
              }
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
      <div id="intake-status">
        {message && <Notice error={fileIssues.length > 0}>{message}</Notice>}
        {fileIssues.length > 0 && (
          <section className="draft-context" aria-label="Rejected intake files">
            <h2>Files rejected during preflight (no originals written)</h2>
            <ul className="matter-list">
              {fileIssues.map((issue) => (
                <li key={`${issue.role}:${issue.filename}:${issue.code}`}>
                  <strong>{issue.filename}</strong> ({issue.role}) ·{' '}
                  <code>{issue.code}</code> — {issue.message}
                </li>
              ))}
            </ul>
            {validCheckedFiles.length > 0 && (
              <p className="small">
                Valid files passed preflight and can be kept as selected:{' '}
                {validCheckedFiles.join(', ')}.
              </p>
            )}
          </section>
        )}
      </div>
    </section>
  );
}
