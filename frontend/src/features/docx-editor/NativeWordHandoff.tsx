import { useEffect, useRef, useState } from 'react';
import type { ChangeEvent } from 'react';
import { useNavigate } from 'react-router';
import type { ApiClient } from '../../shared/api';

const SHA = /^[0-9a-f]{64}$/;
const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const DOCX_LIMIT = 5_242_880;

type Binding = {
  snapshot_hash: string;
  original_sha256: string;
  candidate_sha256: string;
  byte_length: number;
};
type Preview = Binding & {
  schema: string;
  brief_version_id: string;
  changed_package_parts: number;
  removed_package_parts: number;
  command_sha256: string;
  activated: false;
  evidence_status: 'unverified';
};
type Props = {
  api: ApiClient;
  caseId: string;
  briefId: string;
  snapshot: string;
  originalSha256: string;
  originalByteLength: number;
  onActivated: (versionId: string) => void;
};
function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    throw Error('Unexpected Word candidate response.');
  return value as Record<string, unknown>;
}
const hex = (data: Uint8Array) =>
  Array.from(data, (b) => b.toString(16).padStart(2, '0')).join('');
async function sha256(bytes: Uint8Array) {
  return hex(
    new Uint8Array(
      await crypto.subtle.digest('SHA-256', new Uint8Array(bytes)),
    ),
  );
}
function saveLocal(bytes: Uint8Array, name: string) {
  const url = URL.createObjectURL(
    new Blob([new Uint8Array(bytes)], {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }),
  );
  try {
    const link = document.createElement('a');
    link.href = url;
    link.download = name;
    link.click();
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

export function NativeWordHandoff({
  api,
  caseId,
  briefId,
  snapshot,
  originalSha256,
  originalByteLength,
  onActivated,
}: Props) {
  const navigate = useNavigate();
  const [selectedName, setSelectedName] = useState('');
  const [bytes, setBytes] = useState<Uint8Array | null>(null);
  const [binding, setBinding] = useState<Binding | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [rationale, setRationale] = useState('');
  const [reviewRequestId, setReviewRequestId] = useState<string | null>(null);
  const [reviewSaved, setReviewSaved] = useState(false);
  const [commitRequestId, setCommitRequestId] = useState<string | null>(null);
  const [activeVersion, setActiveVersion] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('');
  const controller = useRef<AbortController | null>(null);
  const root = `/v2/matters/${encodeURIComponent(caseId)}/briefs/${encodeURIComponent(briefId)}/dossier/editor/native`;

  useEffect(
    () => () => {
      controller.current?.abort();
      controller.current = null;
    },
    [],
  );

  function changeFile(event: ChangeEvent<HTMLInputElement>) {
    controller.current?.abort();
    const file = event.target.files?.item(0);
    setBytes(null);
    setBinding(null);
    setPreview(null);
    setReviewRequestId(null);
    setReviewSaved(false);
    setCommitRequestId(null);
    setActiveVersion(null);
    setSelectedName('');
    setStatus('');
    if (!file) return;
    if (
      !file.name.toLocaleLowerCase().endsWith('.docx') ||
      file.size < 1 ||
      file.size > DOCX_LIMIT
    ) {
      setStatus(
        'Choose one nonempty DOCX up to 5 MiB; unsupported files are refused.',
      );
      return;
    }
    setSelectedName(file.name);
    void (async () => {
      try {
        const data = new Uint8Array(await file.arrayBuffer());
        if (data.length !== file.size)
          throw Error('File changed during selection.');
        const digest = await sha256(data);
        if (digest === originalSha256)
          throw Error('The original has not been edited.');
        if (!SHA.test(digest)) throw Error('Could not verify DOCX digest.');
        setBytes(data);
        setBinding({
          snapshot_hash: snapshot,
          original_sha256: originalSha256,
          candidate_sha256: digest,
          byte_length: data.byteLength,
        });
        setStatus(
          'DOCX staged in browser memory. Verify changes before review.',
        );
      } catch (error) {
        setBytes(null);
        setStatus(
          error instanceof Error ? error.message : 'Could not read DOCX.',
        );
      }
    })();
  }

  async function originalDownload() {
    if (busy) return;
    const abort = new AbortController();
    controller.current = abort;
    setBusy(true);
    setStatus('Verifying the preserved original draft…');
    try {
      const source = await api.preservedOriginal(
        `/v2/matters/${encodeURIComponent(caseId)}/briefs/${encodeURIComponent(briefId)}/dossier/sources/${encodeURIComponent(briefId)}/original?snapshot_hash=${snapshot}`,
        { sha256: originalSha256, snapshot, length: originalByteLength },
        abort.signal,
      );
      saveLocal(source, 'caseproof-preserved-source-for-word.docx');
      setStatus(
        'Original downloaded. Open it in Microsoft Word and use its full editing and Track Changes interface.',
      );
    } catch (error) {
      setStatus(
        error instanceof Error ? error.message : 'Original unavailable.',
      );
    } finally {
      controller.current = null;
      setBusy(false);
    }
  }

  async function checkCandidate() {
    if (!bytes || !binding || busy) return;
    const abort = new AbortController();
    controller.current = abort;
    setBusy(true);
    setPreview(null);
    setReviewSaved(false);
    setReviewRequestId(null);
    setCommitRequestId(null);
    setStatus(
      'Inspecting the Word-authored DOCX against the immutable source…',
    );
    try {
      const result = record(
        await api.nativeWordUpload(
          `${root}/preview`,
          binding,
          bytes,
          abort.signal,
        ),
      );
      if (
        result.schema !== 'caseproof-native-docx-preview-v1' ||
        result.brief_version_id !== briefId ||
        result.snapshot_hash !== snapshot ||
        result.original_sha256 !== originalSha256 ||
        result.candidate_sha256 !== binding.candidate_sha256 ||
        result.byte_length !== binding.byte_length ||
        result.activated !== false ||
        result.evidence_status !== 'unverified' ||
        typeof result.command_sha256 !== 'string' ||
        !SHA.test(result.command_sha256) ||
        !Number.isSafeInteger(result.changed_package_parts) ||
        Number(result.changed_package_parts) < 1 ||
        !Number.isSafeInteger(result.removed_package_parts)
      ) {
        throw Error('Native Word preview is not bound to the current source.');
      }
      setPreview(result as unknown as Preview);
      setStatus(
        'Word-native candidate validated. Compare it with the original before accepting legal responsibility for all changes.',
      );
    } catch (error) {
      setStatus(
        error instanceof Error ? error.message : 'Word candidate rejected.',
      );
    } finally {
      controller.current = null;
      setBusy(false);
    }
  }

  async function saveReview() {
    if (
      !binding ||
      !preview ||
      busy ||
      rationale.trim().length < 10 ||
      activeVersion
    )
      return;
    const id = reviewRequestId ?? crypto.randomUUID();
    setReviewRequestId(id); // Same durable request ID on lost acknowledgement.
    setBusy(true);
    setStatus('Saving the exact human document-wide approval…');
    try {
      const reply = record(
        await api.post(
          `${root}/review`,
          { ...binding, review_request_id: id, rationale: rationale.trim() },
          undefined,
          { snapshot, idempotencyKey: id },
        ),
      );
      if (
        reply.schema !== 'caseproof-native-docx-review-v1' ||
        reply.review_request_id !== id ||
        reply.candidate_sha256 !== preview.candidate_sha256 ||
        reply.command_sha256 !== preview.command_sha256 ||
        reply.saved !== true ||
        reply.activated !== false
      ) {
        throw Error('Document-wide review receipt could not be verified.');
      }
      setReviewSaved(true);
      setStatus(
        'Signed whole-document review saved. No edited draft is active.',
      );
    } catch (error) {
      setStatus(
        (error instanceof Error ? error.message : 'Review unavailable.') +
          ' Retry the same review request ID; do not create a new approval.',
      );
    } finally {
      setBusy(false);
    }
  }

  function finishVersion(reply: unknown) {
    const value = record(reply);
    if (
      value.schema !== 'caseproof-native-docx-commit-v1' ||
      value.state !== 'active' ||
      value.requires_recheck !== true ||
      typeof value.version_id !== 'string' ||
      !UUID.test(value.version_id)
    ) {
      throw Error('DOCX version activation receipt was not verified.');
    }
    setActiveVersion(value.version_id);
    onActivated(value.version_id);
    setStatus(
      'Word-authored version activated after trusted storage readback. Recheck is mandatory.',
    );
  }

  async function commit() {
    if (
      !bytes ||
      !binding ||
      !reviewSaved ||
      !reviewRequestId ||
      busy ||
      activeVersion
    )
      return;
    const id = commitRequestId ?? crypto.randomUUID();
    setCommitRequestId(id); // Never replace after a lost response.
    const abort = new AbortController();
    controller.current = abort;
    setBusy(true);
    setStatus('Reserving and verifying the approved Word DOCX version…');
    try {
      finishVersion(
        await api.nativeWordUpload(
          `${root}/commit`,
          binding,
          bytes,
          abort.signal,
          { requestId: id, reviewId: reviewRequestId },
        ),
      );
    } catch (error) {
      setStatus(
        (error instanceof Error ? error.message : 'Commit outcome unknown.') +
          ' Reconcile the same request ID before any new operation.',
      );
    } finally {
      controller.current = null;
      setBusy(false);
    }
  }

  async function reconcile() {
    if (
      !binding ||
      !commitRequestId ||
      !reviewRequestId ||
      busy ||
      activeVersion
    )
      return;
    setBusy(true);
    setStatus('Reading the exact durable DOCX edit status…');
    try {
      const value = record(
        await api.post(`${root}/status`, {
          ...binding,
          review_request_id: reviewRequestId,
          request_id: commitRequestId,
        }),
      );
      if (value.schema !== 'caseproof-native-docx-status-v1')
        throw Error('Unexpected Word edit recovery response.');
      if (
        value.state === 'active' &&
        typeof value.version_id === 'string' &&
        UUID.test(value.version_id)
      ) {
        setActiveVersion(value.version_id);
        onActivated(value.version_id);
        setStatus('Activation reconciled. Recheck the new draft.');
      } else if (value.state === 'reserved') {
        setStatus(
          'DOCX is reserved. Retry the identical commit to finish storage readback.',
        );
      } else if (value.state === 'absent') {
        setStatus(
          'No commit exists yet. The saved review can be submitted using the same request ID.',
        );
      } else throw Error('Unknown edit status; do not alter the file.');
    } catch (error) {
      setStatus(
        error instanceof Error
          ? error.message
          : 'Could not verify Word commit status.',
      );
    } finally {
      setBusy(false);
    }
  }

  async function recheckActivatedWordDraft() {
    if (!activeVersion || busy) return;
    setBusy(true);
    setStatus('Rechecking the activated DOCX; prior decisions remain stale…');
    try {
      const report = record(
        await api.post(
          `/v2/matters/${encodeURIComponent(caseId)}/briefs/${encodeURIComponent(activeVersion)}/dossier/recheck`,
          {},
        ),
      );
      if (
        report.case_id !== caseId ||
        report.brief_id !== activeVersion ||
        typeof report.snapshot_hash !== 'string' ||
        !SHA.test(report.snapshot_hash)
      ) throw Error('Recheck did not bind to the activated draft.');
      void navigate(
        `/matters/${encodeURIComponent(caseId)}/briefs/${encodeURIComponent(activeVersion)}?snapshot=${report.snapshot_hash}`,
      );
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Recheck unavailable.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      className="docx-word-handoff"
      aria-label="Full Microsoft Word editing and signed import"
    >
      <div className="docx-word-heading">
        <div>
          <p className="docx-eyebrow">Full Word interface · native Office</p>
          <h2>Author in Microsoft Word, verify in CaseProof</h2>
          <p>
            Use real Word typography, tables, textboxes, comments, images and
            Track Changes. CaseProof never rewrites the selected DOCX or treats
            the document as evidence until a separate signed review.
          </p>
        </div>
      </div>
      <div className="docx-word-actions">
        <button disabled={busy} onClick={() => void originalDownload()}>
          1. Download preserved DOCX for Word
        </button>
        <label htmlFor="word-edited-docx">2. Choose Word-edited DOCX</label>
        <input
          id="word-edited-docx"
          type="file"
          accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          disabled={busy || Boolean(activeVersion)}
          onChange={changeFile}
        />
        <button
          disabled={!bytes || !binding || busy || Boolean(activeVersion)}
          onClick={() => void checkCandidate()}
        >
          3. Inspect imported Word document
        </button>
      </div>
      {selectedName && (
        <p>
          Selected file: <strong>{selectedName}</strong>
        </p>
      )}
      {status && (
        <p role="status" className="docx-editor-status">
          {status}
        </p>
      )}
      {preview && (
        <div className="docx-word-review">
          <p>
            <strong>{preview.changed_package_parts}</strong> modified DOCX
            package parts; <strong>{preview.removed_package_parts}</strong>{' '}
            removed. All changes require human review.
          </p>
          <p className="docx-mono">
            Candidate SHA-256: {preview.candidate_sha256}
          </p>
          <label htmlFor="native-word-rationale">
            Human full-document review rationale
          </label>
          <textarea
            id="native-word-rationale"
            rows={3}
            maxLength={2000}
            value={rationale}
            disabled={busy || reviewSaved || Boolean(activeVersion)}
            onChange={(event) => {
              setRationale(event.target.value);
              setReviewRequestId(null);
              setReviewSaved(false);
              setCommitRequestId(null);
            }}
          />
          <div className="docx-word-actions">
            <button
              disabled={
                busy ||
                reviewSaved ||
                Boolean(activeVersion) ||
                rationale.trim().length < 10
              }
              onClick={() => void saveReview()}
            >
              {reviewRequestId
                ? 'Retry exact approval'
                : '4. Save whole-document review'}
            </button>
            <button
              disabled={busy || !reviewSaved || Boolean(activeVersion)}
              onClick={() => void commit()}
            >
              {commitRequestId
                ? 'Retry identical commit'
                : '5. Commit reviewed Word DOCX'}
            </button>
            <button
              disabled={busy || !commitRequestId || Boolean(activeVersion)}
              onClick={() => void reconcile()}
            >
              Reconcile signed commit
            </button>
          </div>
          {reviewSaved && (
            <p role="status">
              Document-wide approval saved. The candidate has not been activated
              until the commit succeeds.
            </p>
          )}
          {activeVersion && (
            <button
              disabled={busy}
              onClick={() => void recheckActivatedWordDraft()}
            >
              6. Recheck activated draft
            </button>
          )}
          {activeVersion && (
            <p className="docx-mono">
              Activated DOCX version: {activeVersion}. Run the mandatory
              recheck.
            </p>
          )}
        </div>
      )}
      <p className="docx-word-note">
        No browser Word-like renderer or external office service is implied.
        This is the real Microsoft Word authoring experience with a signed
        CaseProof import. Microsoft Word and LibreOffice fidelity must be
        accepted by practitioners before legal production release.
      </p>
    </section>
  );
}
