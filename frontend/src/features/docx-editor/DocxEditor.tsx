import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';
import type { ApiClient } from '../../shared/api';
import { useSession } from '../../shared/session';
import { Notice } from '../../shared/ui';
import './DocxEditor.css';

type Block = {
  part: string;
  paragraph_index: number;
  kind: 'body' | 'table' | 'textbox' | 'story' | 'unsupported';
  text: string;
  text_sha256: string;
  editable: boolean;
};
type Blocks = {
  original_sha256: string;
  snapshot_hash: string;
  total: number;
  editable_count: number;
  blocks: Block[];
  has_more: boolean;
};
type Revision = {
  part: string;
  revision_id: number;
  kind: 'inserted' | 'deleted';
  author: string;
  timestamp: string;
  text_sha256: string;
};
type Edit = {
  part: string;
  paragraph_index: number;
  expected_text_sha256: string;
  before: string;
  after: string;
  track_changes: boolean;
};
type Decision = {
  part: string;
  revision_id: number;
  action: 'accept' | 'reject';
};
type Command = {
  snapshot_hash: string;
  original_sha256: string;
  timestamp: string;
  edits: Edit[];
  decisions: Decision[];
};
type Preview = {
  derivative_sha256: string;
  derivative_byte_length: number;
  operations_count: number;
};
const sha = /^[0-9a-f]{64}$/;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function object(x: unknown): Record<string, unknown> {
  if (!x || typeof x !== 'object' || Array.isArray(x))
    throw Error('The editor response is not a verified object.');
  return x as Record<string, unknown>;
}
function parseBlocks(
  x: unknown,
  scope: { briefId: string; snapshot: string },
): Blocks {
  const v = object(x);
  if (
    v.schema !== 'caseproof-docx-editor-blocks-v1' ||
    v.brief_version_id !== scope.briefId ||
    v.snapshot_hash !== scope.snapshot ||
    typeof v.original_sha256 !== 'string' ||
    !sha.test(v.original_sha256) ||
    !Number.isInteger(v.total) ||
    !Number.isInteger(v.editable_count) ||
    typeof v.has_more !== 'boolean' ||
    !Array.isArray(v.blocks) ||
    v.blocks.length > 20
  )
    throw Error('The editor source version could not be validated.');
  const blocks = v.blocks.map((raw: unknown) => {
    const row = object(raw);
    if (
      typeof row.part !== 'string' ||
      !/^word\/(?:document|header[0-9]+|footer[0-9]+|footnotes|endnotes)\.xml$/.test(row.part) ||
      typeof row.paragraph_index !== 'number' ||
      !Number.isInteger(row.paragraph_index) ||
      row.paragraph_index < 0 ||
      row.paragraph_index > 2999 ||
      !['body', 'table', 'textbox', 'story', 'unsupported'].includes(String(row.kind)) ||
      typeof row.text !== 'string' ||
      row.text.length > 20000 ||
      typeof row.text_sha256 !== 'string' ||
      !sha.test(row.text_sha256) ||
      typeof row.editable !== 'boolean'
    )
      throw Error('One or more editor blocks are invalid.');
    return row as unknown as Block;
  });
  return {
    original_sha256: v.original_sha256,
    snapshot_hash: v.snapshot_hash as string,
    total: v.total as number,
    editable_count: v.editable_count as number,
    blocks,
    has_more: v.has_more,
  };
}
function parseRevisions(x: unknown, briefId: string, snapshot: string, original: string): Revision[] {
  const v = object(x);
  if (
    v.schema !== 'caseproof-docx-editor-revisions-v1' ||
    v.brief_version_id !== briefId ||
    v.snapshot_hash !== snapshot ||
    v.original_sha256 !== original ||
    !Array.isArray(v.revisions) ||
    v.revisions.length > 3000
  )
    throw Error('Word revision data does not match the current draft.');
  return v.revisions.map((entry: unknown) => {
    const r = object(entry);
    if (
      typeof r.part !== 'string' ||
      !/^word\/(?:document|header[0-9]+|footer[0-9]+|footnotes|endnotes)\.xml$/.test(r.part) ||
      typeof r.revision_id !== 'number' ||
      !Number.isInteger(r.revision_id) ||
      r.revision_id < 0 ||
      !['inserted', 'deleted'].includes(String(r.kind)) ||
      typeof r.author !== 'string' ||
      typeof r.timestamp !== 'string' ||
      typeof r.text_sha256 !== 'string' ||
      !sha.test(r.text_sha256)
    )
      throw Error('Word revision identity is invalid.');
    return r as unknown as Revision;
  });
}
function parsePreview(x: unknown, command: Command, briefId: string): Preview {
  const v = object(x);
  if (
    v.schema !== 'caseproof-docx-editor-preview-v1' ||
    v.brief_version_id !== briefId ||
    v.snapshot_hash !== command.snapshot_hash ||
    v.original_sha256 !== command.original_sha256 ||
    typeof v.derivative_sha256 !== 'string' ||
    !sha.test(v.derivative_sha256) ||
    typeof v.derivative_byte_length !== 'number' ||
    !Number.isInteger(v.derivative_byte_length) ||
    v.derivative_byte_length < 1 ||
    v.derivative_byte_length > 5_242_880 ||
    v.operations_count !== command.edits.length + command.decisions.length ||
    v.committed !== false ||
    v.activated !== false ||
    v.requires_document_scoped_review_and_import !== true ||
    v.requires_recheck !== true
  )
    throw Error('The candidate receipt cannot be trusted.');
  return {
    derivative_sha256: v.derivative_sha256,
    derivative_byte_length: v.derivative_byte_length,
    operations_count: v.operations_count as number,
  };
}
const keyFor = (b: { part: string; paragraph_index: number }) =>
  `${b.part}#${b.paragraph_index}`;
const revisionKey = (r: { part: string; revision_id: number }) =>
  `${r.part}#revision-${r.revision_id}`;

export function DocxEditor({ api }: { api: ApiClient }) {
  const { caseId = '', briefId = '' } = useParams();
  const [params] = useSearchParams();
  const snapshot = params.get('snapshot') ?? '';
  const session = useSession();
  const valid = uuid.test(caseId) && uuid.test(briefId) && sha.test(snapshot);
  const root = `/v2/matters/${encodeURIComponent(caseId)}/briefs/${encodeURIComponent(briefId)}/dossier/editor`;
  const [page, setPage] = useState(0);
  const [edits, setEdits] = useState<Record<string, Edit>>({});
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const [tracking, setTracking] = useState(true);
  const [prepared, setPrepared] = useState<{ command: Command; receipt: Preview } | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const request = useRef<AbortController | null>(null);

  useEffect(
    () => () => {
      request.current?.abort();
      request.current = null;
    },
    [],
  );

  const source = useQuery({
    queryKey: ['docx-editor-blocks', session.epoch, caseId, briefId, snapshot, page],
    queryFn: async ({ signal }) => {
      const response = await api.get(
        `${root}/blocks?snapshot_hash=${snapshot}&offset=${page * 20}&limit=20`,
        signal,
      );
      return parseBlocks(response, { briefId, snapshot });
    },
    enabled: valid && session.connected,
  });

  const revisions = useQuery({
    queryKey: ['docx-editor-revisions', session.epoch, caseId, briefId, snapshot],
    queryFn: ({ signal }) =>
      api.get(`${root}/revisions?snapshot_hash=${snapshot}`, signal),
    enabled: valid && session.connected && source.isSuccess,
  });
  const parsedRevisions = (() => {
    if (!source.data || !revisions.data) return [] as Revision[];
    try {
      return parseRevisions(revisions.data, briefId, snapshot, source.data.original_sha256);
    } catch {
      return [] as Revision[];
    }
  })();
  const revisionMismatch = revisions.isSuccess && source.data !== undefined &&
    (() => {
      try {
        parseRevisions(revisions.data, briefId, snapshot, source.data.original_sha256);
        return false;
      } catch {
        return true;
      }
    })();

  const changed = Object.values(edits).filter((edit) => edit.after !== edit.before);
  const selectedRevisions = Object.values(decisions);
  const mixed = changed.length > 0 && selectedRevisions.length > 0;
  const ready =
    !busy && !mixed && !revisionMismatch && source.isSuccess &&
    ((changed.length > 0 && changed.length <= 40) ||
      (selectedRevisions.length > 0 && selectedRevisions.length <= 40));

  function setBlock(block: Block, after: string) {
    setPrepared(null);
    setNotice('');
    setEdits((previous) => {
      const next = { ...previous };
      const key = keyFor(block);
      if (after === block.text) delete next[key];
      else
        next[key] = {
          part: block.part,
          paragraph_index: block.paragraph_index,
          expected_text_sha256: block.text_sha256,
          before: block.text,
          after,
          track_changes: tracking,
        };
      return next;
    });
  }
  function setRevision(revision: Revision, action: '' | 'accept' | 'reject') {
    setPrepared(null);
    setDecisions((previous) => {
      const next = { ...previous };
      if (!action) delete next[revisionKey(revision)];
      else next[revisionKey(revision)] = {
        part: revision.part, revision_id: revision.revision_id, action,
      };
      return next;
    });
  }
  async function preview() {
    if (!ready || !source.data) return;
    setBusy(true);
    setPrepared(null);
    setNotice('');
    const command: Command = {
      snapshot_hash: snapshot,
      original_sha256: source.data.original_sha256,
      timestamp: new Date().toISOString().slice(0, 19) + '+00:00',
      edits: changed,
      decisions: selectedRevisions,
    };
    try {
      const received = await api.post(`${root}/preview`, command, undefined, { snapshot });
      setPrepared({ command, receipt: parsePreview(received, command, briefId) });
      setNotice('Source-bound candidate prepared. No change has been committed.');
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'The editor preview was refused.');
    } finally {
      setBusy(false);
    }
  }
  async function download() {
    if (!prepared || busy) return;
    setBusy(true);
    setNotice('Checking and downloading the exact prepared candidate…');
    const controller = new AbortController();
    request.current = controller;
    let url: string | null = null;
    try {
      const bytes = await api.editorCandidate(
        `${root}/candidate`,
        prepared.command,
        {
          sha256: prepared.receipt.derivative_sha256,
          byte_length: prepared.receipt.derivative_byte_length,
        },
        controller.signal,
      );
      const file = new Blob([new Uint8Array(bytes)], {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });
      url = URL.createObjectURL(file);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'caseproof-uncommitted-edited-candidate.docx';
      link.click();
      setNotice('Candidate downloaded and SHA-256 checked. It is NOT a reviewed or activated draft. Use a separately authorized import and recheck.');
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Candidate download failed.');
    } finally {
      if (url) {
        const value = url;
        setTimeout(() => URL.revokeObjectURL(value), 1000);
      }
      request.current = null;
      setBusy(false);
    }
  }

  if (!valid)
    return <Notice error>Provide a valid matter, draft version and snapshot.</Notice>;
  if (source.isPending) return <Notice>Opening source-bound document blocks…</Notice>;
  if (source.isError) return <Notice error>{source.error.message}</Notice>;

  return (
    <section className="docx-editor" aria-label="Structured Word candidate editor">
      <header className="docx-editor-heading">
        <div>
          <p className="docx-eyebrow">CaseProof · DOCX candidate workspace</p>
          <h1>Edit the preserved draft</h1>
          <p>Word paragraphs, ordinary tables, supported textboxes and textual tracked changes. No source document is overwritten.</p>
          <Link to={`/matters/${caseId}/briefs/${briefId}?snapshot=${snapshot}`}>
            Return to evidence review
          </Link>
        </div>
      </header>
      <div className="docx-ribbon" role="group" aria-label="Candidate editing tools">
        <label>
          <input
            type="checkbox"
            checked={tracking}
            onChange={(event) => {
              setTracking(event.target.checked);
              setPrepared(null);
              setEdits((old) =>
                Object.fromEntries(Object.entries(old).map(([key, edit]) => [
                  key, { ...edit, track_changes: event.target.checked },
                ])),
              );
            }}
          />
          Track changes in Word
        </label>
        <button disabled={!ready} onClick={() => void preview()}>
          {busy ? 'Checking…' : 'Preview edits'}
        </button>
        <button disabled={!prepared || busy} onClick={() => void download()}>
          Download DOCX candidate
        </button>
        <button
          disabled={busy || (!changed.length && !selectedRevisions.length)}
          onClick={() => {
            setEdits({});
            setDecisions({});
            setPrepared(null);
            setNotice('Unsaved local changes discarded.');
          }}
        >
          Discard local edits
        </button>
      </div>
      <div className="docx-scope-note" role="note">
        <strong>Candidate only.</strong> This is a structured text editor, not a
        pixel-faithful Word renderer. Complex structures abstain. Download does
        not commit, approve, activate or recheck a legal document.
      </div>
      {notice && <p className="docx-editor-status" role="status">{notice}</p>}
      <div className="docx-editor-layout">
        <aside className="docx-editor-sidebar" aria-label="Document summary">
          <h2>Source identity</h2>
          <p><strong>{source.data.total}</strong> blocks · <strong>{source.data.editable_count}</strong> text-editable</p>
          <p className="docx-mono">SHA-256: {source.data.original_sha256}</p>
          <p className="docx-mono">Snapshot: {snapshot}</p>
          <p>{changed.length} staged replacements · {selectedRevisions.length} revision decisions</p>
          {mixed && (
            <Notice error>Text replacements and revision decisions must be prepared separately.</Notice>
          )}
          {changed.length > 40 && <Notice error>At most 40 edits per candidate.</Notice>}
          <h2>Review boundary</h2>
          <p>A new document-wide authorization, durable import and independent recheck are required before this candidate becomes a CaseProof version.</p>
        </aside>
        <section className="docx-editor-document" aria-label="Editable DOCX text blocks">
          <div className="docx-editor-toolbar">
            <h2>Document text</h2>
            <span>Blocks {page * 20 + 1}–{Math.min((page + 1) * 20, source.data.total)}</span>
          </div>
          {source.data.blocks.map((block) => (
            <article key={keyFor(block)} className="docx-block">
              <header>
                <span className="docx-kind">{block.kind}</span>
                <small>{block.part} · Paragraph {block.paragraph_index + 1}</small>
                {!block.editable && <span className="docx-unsupported">Unsupported for editing</span>}
              </header>
              <label htmlFor={`edit-${keyFor(block)}`}>Source-bound paragraph</label>
              <textarea
                id={`edit-${keyFor(block)}`}
                value={edits[keyFor(block)]?.after ?? block.text}
                disabled={!block.editable || busy}
                maxLength={20000}
                rows={Math.min(10, Math.max(2, Math.ceil(block.text.length / 90)))}
                onChange={(event) => setBlock(block, event.target.value)}
              />
              {edits[keyFor(block)] && (
                <p className="docx-changed">Locally modified · {tracking ? 'Tracked replacement' : 'Direct replacement'}</p>
              )}
            </article>
          ))}
          <nav aria-label="Document block pagination" className="docx-page-nav">
            <button disabled={page === 0 || busy} onClick={() => setPage((p) => p - 1)}>
              Previous blocks
            </button>
            <span>Page {page + 1} of {Math.max(1, Math.ceil(source.data.total / 20))}</span>
            <button disabled={!source.data.has_more || busy} onClick={() => setPage((p) => p + 1)}>
              Next blocks
            </button>
          </nav>
        </section>
        <aside className="docx-editor-revisions" aria-label="Native Word revision review">
          <h2>Tracked changes</h2>
          {revisions.isPending && <p>Reading revision identities…</p>}
          {revisions.isError && <Notice error>Revision inventory unavailable.</Notice>}
          {revisionMismatch && <Notice error>Revision receipt does not match this document.</Notice>}
          {!revisions.isPending && !revisions.isError && !revisionMismatch &&
            parsedRevisions.length === 0 && <p>No native textual revisions identified.</p>}
          {!revisionMismatch && parsedRevisions.map((row) => (
            <div key={revisionKey(row)} className="docx-revision">
              <strong>{row.kind === 'inserted' ? 'Insertion' : 'Deletion'} #{row.revision_id}</strong>
              <small>{row.part}</small>
              <small>{row.author} · {row.timestamp}</small>
              <label>
                Decision
                <select
                  value={decisions[revisionKey(row)]?.action ?? ''}
                  disabled={busy}
                  onChange={(event) =>
                    setRevision(row, event.target.value as '' | 'accept' | 'reject')
                  }
                >
                  <option value="">Keep unresolved</option>
                  <option value="accept">Accept</option>
                  <option value="reject">Reject</option>
                </select>
              </label>
            </div>
          ))}
        </aside>
      </div>
      {prepared && (
        <section className="docx-preview-receipt" aria-label="Candidate preview receipt">
          <h2>Prepared derivative</h2>
          <p>{prepared.receipt.operations_count} operation(s), {prepared.receipt.derivative_byte_length.toLocaleString()} bytes</p>
          <p className="docx-mono">{prepared.receipt.derivative_sha256}</p>
          <p><strong>Not committed.</strong> Source SHA-256 and frozen snapshot remain unchanged.</p>
        </section>
      )}
    </section>
  );
}

export function ScopedDocxEditor({ api }: { api: ApiClient }) {
  const { caseId = '', briefId = '' } = useParams();
  const [params] = useSearchParams();
  const session = useSession();
  const key = `${session.epoch}:${caseId}:${briefId}:${params.get('snapshot') ?? ''}`;
  return <DocxEditor key={key} api={api} />;
}
