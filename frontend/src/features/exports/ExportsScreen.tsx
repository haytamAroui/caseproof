import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useParams, useSearchParams } from 'react-router';
import type { ApiClient } from '../../shared/api';
import { useSession } from '../../shared/session';
import { Button, Notice } from '../../shared/ui';
import {
  downloadArtifact,
  exportsPath,
  parseRelease,
  parseReleaseList,
  parseReleasePreview,
  parseReleaseStatus,
} from './api';
import type { ExportFormat, ReleaseRecord, ReleaseScope } from './api';

const uuid =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const sha = /^[0-9a-f]{64}$/;
const formats: ExportFormat[] = ['json', 'markdown', 'docx'];

export function ExportsScreen({ api }: { api: ApiClient }) {
  const { caseId = '' } = useParams();
  const [params] = useSearchParams();
  const briefId = params.get('brief') ?? '';
  const snapshot = params.get('snapshot') ?? '';
  const scope: ReleaseScope = { caseId, briefId, snapshot };
  const valid = uuid.test(caseId) && uuid.test(briefId) && sha.test(snapshot);
  const session = useSession();
  const [selected, setSelected] = useState<ReleaseRecord | null>(null);
  const [format, setFormat] = useState<ExportFormat>('docx');
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState('');
  const [unknown, setUnknown] = useState(false);
  // The same operation id survives a lost POST acknowledgement within this
  // screen. We never silently mint a new id and retry a consequential write.
  const requestId = useRef<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  useEffect(() => () => abort.current?.abort(), []);
  const base = exportsPath(scope);
  const preview = useQuery({
    queryKey: ['release-preview', session.epoch, caseId, briefId, snapshot],
    queryFn: async ({ signal }) =>
      parseReleasePreview(
        await api.get(`${base}/preview?snapshot_hash=${snapshot}`, signal),
        scope,
      ),
    enabled: valid && session.connected,
    retry: false,
  });
  const history = useQuery({
    queryKey: ['release-history', session.epoch, caseId, briefId],
    queryFn: async ({ signal }) =>
      parseReleaseList(await api.get(base, signal), scope),
    enabled: uuid.test(caseId) && uuid.test(briefId) && session.connected,
    retry: false,
  });

  async function commitRelease() {
    if (!valid || !preview.data?.release_ready || working) return;
    const id = requestId.current ?? crypto.randomUUID();
    requestId.current = id;
    const controller = new AbortController();
    abort.current = controller;
    setWorking(true);
    setMessage('');
    try {
      // One exact snapshot command; POST is deliberately never retried.
      const response = await api.post(
        base,
        { release_id: id, snapshot_hash: snapshot },
        controller.signal,
      );
      const parsed = parseRelease(response, scope);
      setSelected(parsed);
      requestId.current = null;
      setUnknown(false);
      setMessage(
        'Frozen reviewed release saved. Verify and download the selected artifact.',
      );
      void history.refetch();
    } catch {
      setUnknown(true);
      setMessage(
        'Release outcome unknown. Reconcile this operation before starting a new release.',
      );
    } finally {
      setWorking(false);
      abort.current = null;
    }
  }
  async function reconcile() {
    if (!requestId.current || working || !valid) return;
    const controller = new AbortController();
    abort.current = controller;
    setWorking(true);
    try {
      const result = parseReleaseStatus(
        await api.get(`${base}/${requestId.current}`, controller.signal),
        scope,
      );
      if (result) {
        setSelected(result);
        requestId.current = null;
        setUnknown(false);
        setMessage('The previously submitted release was found and recovered.');
        void history.refetch();
      } else {
        setMessage(
          'No committed release was found yet. Do not assume an interrupted operation failed.',
        );
      }
    } catch {
      setMessage(
        'Could not reconcile this release. No new release was submitted.',
      );
    } finally {
      setWorking(false);
      abort.current = null;
    }
  }
  async function download() {
    if (!selected || working || !session.connected) return;
    const controller = new AbortController();
    abort.current = controller;
    setWorking(true);
    setMessage('');
    try {
      const bytes = await downloadArtifact(
        api,
        { ...scope, snapshot: selected.snapshot_hash },
        selected,
        format,
        controller.signal,
      );
      if (controller.signal.aborted) throw new Error('Cancelled');
      const mime = selected.manifest.artifacts[format].media_type;
      // The binary transport validates content-type, length, snapshot and
      // SHA-256 against the frozen server-signed manifest before any download.
      const url = URL.createObjectURL(
        new Blob([new Uint8Array(bytes)], { type: mime }),
      );
      const link = document.createElement('a');
      link.href = url;
      link.download = `caseproof-reviewed-${selected.release_id}.${format === 'markdown' ? 'md' : format}`;
      try {
        document.body.append(link);
        link.click();
        setMessage(
          'Verified bytes offered to your browser. The downloaded copy is outside session revocation control.',
        );
      } finally {
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
    } catch {
      setMessage(
        'Download failed integrity, access or transfer validation. No artifact was offered.',
      );
    } finally {
      setWorking(false);
      abort.current = null;
    }
  }
  return (
    <section className="export-workspace" aria-labelledby="exports-title">
      <Link to={uuid.test(caseId) ? `/matters/${caseId}` : '/'}>
        Back to permitted reports
      </Link>
      <header className="page-heading">
        <p className="eyebrow">F6 · M4 reviewed delivery</p>
        <h1 id="exports-title">Reviewed exports and history</h1>
        <p>
          Releases preserve scope and uncertainty. They do not certify legal
          support, accuracy or court filing.
        </p>
      </header>
      {!valid && (
        <Notice error>
          Choose a preserved report with a valid brief version and snapshot
          before releasing an artifact.
        </Notice>
      )}
      {valid && (
        <>
          <p className="small">
            Snapshot <code>{snapshot}</code>
          </p>
          {preview.isPending ? (
            <Notice>
              Checking current export authority and frozen review scope…
            </Notice>
          ) : preview.isError ? (
            <Notice error>
              Release preview unavailable. The draft may be historical, your
              export grant may be missing, or the source universe may have
              changed. Existing releases remain separately listed.
            </Notice>
          ) : (
            <section className="draft-context" aria-label="Release readiness">
              <h2>Preview release scope</h2>
              <p>
                {preview.data.finding_count} detected references;{' '}
                {preview.data.review_count} persisted human decisions.
              </p>
              {preview.data.coverage.text_coverage_complete !== true && (
                <Notice>
                  DOCX coverage is incomplete or unmeasured. Do not interpret a
                  clean list as full verification.
                </Notice>
              )}
              {preview.data.coverage.reference_recall_measured !== true && (
                <Notice>Reference detection recall was not measured.</Notice>
              )}
              {preview.data.limitations.map((text) => (
                <p className="small" key={text}>
                  {text}
                </p>
              ))}
              {!preview.data.release_ready && (
                <Notice error>
                  A saved human review is required before a reviewed release.
                  Complete review in the findings workspace.
                </Notice>
              )}
              <Button
                onClick={() => void commitRelease()}
                disabled={!preview.data.release_ready || working || unknown}
              >
                {working ? 'Processing…' : 'Create frozen reviewed release'}
              </Button>
            </section>
          )}
        </>
      )}
      {unknown && (
        <div className="draft-context">
          <Notice error>
            Unknown release outcome. Preserve the operation identifier and
            reconcile instead of retrying automatically.
          </Notice>
          <Button disabled={working} onClick={() => void reconcile()}>
            Reconcile previous release
          </Button>
        </div>
      )}
      {message && <Notice>{message}</Notice>}
      <section className="draft-context" aria-label="Export history">
        <h2>Frozen release history</h2>
        {history.isPending ? (
          <Notice>Loading authorized release history…</Notice>
        ) : history.isError ? (
          <Notice error>
            Release history is unavailable or access was revoked.
          </Notice>
        ) : history.data.length === 0 ? (
          <Notice>No reviewed releases exist for this brief.</Notice>
        ) : (
          <ul>
            {history.data.map((release) => (
              <li key={release.release_id}>
                <Button
                  aria-pressed={selected?.release_id === release.release_id}
                  onClick={() => {
                    setSelected(release);
                    setMessage('');
                  }}
                >
                  Select release {release.release_id.slice(0, 8)}
                </Button>
                <span className="small">
                  {' '}
                  Snapshot {release.snapshot_hash.slice(0, 12)}… ·{' '}
                  {release.manifest.review_count} decisions
                  {release.snapshot_hash === snapshot
                    ? ' · selected snapshot'
                    : ' · historical release'}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
      {selected && (
        <section className="draft-context" aria-label="Selected release">
          <h2>Selected frozen release</h2>
          <p>
            Snapshot <code>{selected.snapshot_hash}</code>
          </p>
          <p>
            Manifest <code>{selected.manifest.manifest_sha256}</code>
          </p>
          <p>
            {selected.manifest.finding_count} references;{' '}
            {selected.manifest.review_count} human decisions.
          </p>
          <p>Referenced preserved originals:</p>
          <ul>
            {selected.manifest.sources.map((source) => (
              <li key={source.version_id}>
                {source.role}: <code>{source.version_id}</code> — SHA-256{' '}
                <code>{source.sha256}</code>
              </li>
            ))}
          </ul>
          <h3>Frozen reference destinations</h3>
          {selected.manifest.reference_links.length === 0 ? (
            <Notice>
              No mapped source destinations were recorded for this release.
              Unknown page locations remain unassessed.
            </Notice>
          ) : (
            <ul aria-label="Frozen reference destinations">
              {selected.manifest.reference_links.map((target) => (
                <li key={target.reference_id}>
                  <Link to={target.viewer_path}>
                    Inspect preserved reference {target.reference_id}
                  </Link>
                  <span className="small">
                    {' '}
                    · {target.pdf_page === null
                      ? 'Physical PDF page not mapped'
                      : 'Physical PDF page ' + target.pdf_page}
                    {' '}· version <code>{target.source_version_id}</code>
                  </span>
                </li>
              ))}
            </ul>
          )}
          {selected.manifest.limitations.map((text) => (
            <p className="small" key={text}>
              {text}
            </p>
          ))}
          <Link
            to={`/matters/${caseId}/briefs/${briefId}?snapshot=${selected.snapshot_hash}`}
          >
            Inspect preserved findings and source navigation
          </Link>
          <label>
            Output format
            <select
              value={format}
              onChange={(e) => setFormat(e.target.value as ExportFormat)}
            >
              {formats.map((kind) => (
                <option value={kind} key={kind}>
                  {kind === 'docx'
                    ? 'Annotated DOCX'
                    : kind === 'markdown'
                      ? 'Markdown'
                      : 'JSON'}
                </option>
              ))}
            </select>
          </label>
          <p className="small">
            Length{' '}
            {selected.manifest.artifacts[format].byte_length.toLocaleString()}{' '}
            bytes; SHA-256{' '}
            <code>{selected.manifest.artifacts[format].sha256}</code>
          </p>
          <Button disabled={working} onClick={() => void download()}>
            Verify SHA-256 and download {format.toUpperCase()}
          </Button>
        </section>
      )}
    </section>
  );
}
