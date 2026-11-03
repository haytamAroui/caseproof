import { useState } from 'react';
import { useNavigate } from 'react-router';
import type { ApiClient, FindingView } from '../../shared/api';
import { ApiError } from '../../shared/api';
import { Button, Notice, UnsavedChanges } from '../../shared/ui';

type Scope = { caseId: string; briefId: string; snapshot: string };
type Preview = { schema: string; committed: false; requires_recheck: true; original_sha256: string; derivative_sha256: string; reference_id: string; paragraph_index: number; before: string; after: string; brief_version_id: string; snapshot_hash: string };
type Commit = { state: string; version_id: string; committed: true; requires_recheck: true };
const sha = /^[0-9a-f]{64}$/;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
function record(x: unknown): Record<string, unknown> {
  if (!x || typeof x !== 'object' || Array.isArray(x)) throw Error('Invalid server response');
  return x as Record<string, unknown>;
}
function previewReceipt(x: unknown, expected: {snapshot_hash: string; original_sha256: string; reference_id: string; paragraph_index: number; before: string; after: string}, briefId: string): Preview {
  const r = record(x);
  if (r.schema !== 'caseproof-docx-correction-preview-v1' || r.committed !== false ||
    r.requires_recheck !== true || r.original_sha256 !== expected.original_sha256 ||
    r.reference_id !== expected.reference_id || r.paragraph_index !== expected.paragraph_index ||
    r.before !== expected.before || r.after !== expected.after ||
    r.brief_version_id !== briefId || r.snapshot_hash !== expected.snapshot_hash ||
    typeof r.derivative_sha256 !== 'string' || !sha.test(r.derivative_sha256))
    throw Error('Unverified correction preview');
  return r as Preview;
}
function commitReceipt(x: unknown): Commit {
  const r = record(x);
  if (r.state !== 'active' || r.committed !== true || r.requires_recheck !== true ||
    typeof r.version_id !== 'string' || !uuid.test(r.version_id))
    throw Error('Activation not confirmed');
  return r as Commit;
}
/** A bounded correction command: never silently infer a DOCX paragraph index from a text excerpt. */
export function CorrectionPanel({ api, scope, finding, originalSha }: {
  api: ApiClient; scope: Scope; finding: FindingView; originalSha: string;
}) {
  const navigate = useNavigate();
  const [paragraph, setParagraph] = useState('');
  const [before, setBefore] = useState(finding.literal);
  const [after, setAfter] = useState('');
  const [preview, setPreview] = useState<Preview | null>(null);
  const [command, setCommand] = useState<Record<string, unknown> | null>(null);
  const [receipt, setReceipt] = useState<Commit | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [unknown, setUnknown] = useState(false);
  const [previousSnapshot, setPreviousSnapshot] = useState<string | null>(null);
  const base = `/v2/matters/${encodeURIComponent(scope.caseId)}/briefs/${encodeURIComponent(scope.briefId)}/dossier`;
  const valid = sha.test(originalSha) && sha.test(scope.snapshot) &&
    /^[0-9]{1,6}$/.test(paragraph) && Number(paragraph) <= 100000 &&
    before.length > 0 && before.length <= 4000 && after.length <= 4000 && before !== after;
  function invalidate() { setPreview(null); setCommand(null); setReceipt(null); setUnknown(false); setMessage(''); }
  const payload = () => ({
    snapshot_hash: scope.snapshot, original_sha256: originalSha,
    reference_id: finding.reference_id, paragraph_index: Number(paragraph), before, after,
  });
  async function requestPreview() {
    if (!valid || busy) return;
    setBusy(true); invalidate();
    try {
      const result = previewReceipt(await api.post(`${base}/corrections/preview`, payload()), payload(), scope.briefId);
      setPreview(result); setMessage('Read-only preview validated. No change was committed.');
    } catch (e) { setMessage(e instanceof ApiError && e.status === 409 ? 'Stale draft. Reopen the current report.' : 'Preview unavailable or unsupported. No commit allowed.'); }
    finally { setBusy(false); }
  }
  async function commit() {
    if (!preview || command || busy || !valid) return;
    const submitted = { ...payload(), request_id: crypto.randomUUID() };
    setCommand(submitted); setBusy(true); setUnknown(false);
    try {
      const result = commitReceipt(await api.post(`${base}/corrections/commit`, submitted));
      setReceipt(result); setMessage('New draft activated. Recheck is required; previous approvals are not transferred.');
    } catch (e) {
      setUnknown(!(e instanceof ApiError && e.status === 409));
      setMessage(e instanceof ApiError && e.status === 409 ?
        'Version conflict. Reopen the current draft before attempting another correction.' :
        'Commit outcome unknown. Do not submit another correction. Reconcile with the authorized draft history.');
    } finally { setBusy(false); }
  }
  async function reconcile() {
    if (!command || busy) return;
    setBusy(true);
    try {
      // Read-only durable lookup: never replay an uncertain consequential write.
      const status = record(await api.post(`${base}/corrections/status`, command));
      if (status.state !== "active") {
        setUnknown(true);
        setMessage(status.state === "reserved" ? "Correction reserved but activation is not confirmed. Contact the workspace administrator for recovery." : "No durable activation found. Do not create another correction until the outcome is investigated.");
        return;
      }
      const result = commitReceipt(status);
      setReceipt(result);
      setUnknown(false);
      setMessage('Exact correction reconciled against the durable activation receipt.');
    } catch {
      setUnknown(true);
      setMessage('Durable outcome still unresolved. Do not create another correction.');
    } finally { setBusy(false); }
  }
  async function recheck() {
    if (!receipt || busy) return;
    setBusy(true);
    try {
      const raw = record(await api.post(`/v2/matters/${encodeURIComponent(scope.caseId)}/briefs/${encodeURIComponent(receipt.version_id)}/dossier/recheck`, {}));
      if (typeof raw.snapshot_hash !== 'string' || !sha.test(raw.snapshot_hash) ||
        raw.brief_id !== receipt.version_id) throw Error('Recheck binding mismatch');
      setPreviousSnapshot(scope.snapshot);
      navigate(`/matters/${encodeURIComponent(scope.caseId)}/briefs/${encodeURIComponent(receipt.version_id)}?snapshot=${raw.snapshot_hash}`);
    } catch { setMessage('Recheck could not be confirmed. Reopen the activated draft from authorized history.'); }
    finally { setBusy(false); }
  }
  return <section className="draft-context" aria-label="Correction preview and recheck">
    <UnsavedChanges dirty={Boolean(preview && !command)} />
    <h3>Propose a bounded DOCX correction</h3>
    <Notice>Only an exact supported paragraph replacement can be applied. Paragraph index must be independently verified against the original DOCX; the excerpt does not establish it.</Notice>
    <fieldset disabled={busy || Boolean(command)}>
      <label>DOCX paragraph index (zero-based)<input type="number" min="0" max="100000" step="1" value={paragraph} onChange={e => { invalidate(); setParagraph(e.target.value); }} /></label>
      <label>Exact original text<textarea maxLength={4000} value={before} onChange={e => { invalidate(); setBefore(e.target.value); }} /></label>
      <label>Replacement text<textarea maxLength={4000} value={after} onChange={e => { invalidate(); setAfter(e.target.value); }} /></label>
    </fieldset>
    <Button disabled={!valid || busy || Boolean(command)} onClick={() => void requestPreview()}>Validate exact preview</Button>
    {preview && <div aria-label="Before and after correction">
      <p>Proposed change (not committed)</p>
      <p><del>{before}</del> <ins>{after}</ins></p>
      <p className="small">Original SHA-256: {preview.original_sha256}</p>
      <p className="small">Derivative SHA-256: {preview.derivative_sha256}</p>
      <Button disabled={busy || Boolean(command)} onClick={() => void commit()}>Explicitly commit and activate new draft</Button>
    </div>}
    {unknown && <><Notice error>Unknown write outcome. Automatic retry is disabled. Reconcile only the identical request.</Notice><Button disabled={busy} onClick={() => void reconcile()}>Reconcile identical operation</Button></>}
    {receipt && <Button disabled={busy} onClick={() => void recheck()}>Recheck activated draft</Button>}
    {previousSnapshot && <p>Previous preserved report: {previousSnapshot}</p>}
    {message && <p role="status">{message}</p>}
  </section>;
}
