import { useEffect, useRef, useState } from 'react';
import type { ApiClient } from '../../shared/api';

export function OriginalDraftDownload({
  api,
  caseId,
  briefId,
  snapshot,
  historical,
  sha256,
  length,
}: {
  api: ApiClient;
  caseId: string;
  briefId: string;
  snapshot: string;
  historical: boolean;
  sha256: string;
  length: number;
}) {
  const pending = useRef<AbortController | null>(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(
    () => () => {
      pending.current?.abort();
    },
    [],
  );
  async function download() {
    if (pending.current) return;
    const controller = new AbortController();
    pending.current = controller;
    setBusy(true);
    setMessage('Checking access and original bytes…');
    const base = `/v2/matters/${encodeURIComponent(caseId)}/briefs/${encodeURIComponent(briefId)}/dossier`;
    const path = historical
      ? `${base}/history/${snapshot}/sources/${encodeURIComponent(briefId)}/original`
      : `${base}/sources/${encodeURIComponent(briefId)}/original?snapshot_hash=${snapshot}`;
    try {
      const bytes = await api.preservedOriginal(
        path,
        { sha256, snapshot, length },
        controller.signal,
      );
      if (controller.signal.aborted) return;
      const url = URL.createObjectURL(
        new Blob([bytes.slice().buffer], {
          type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        }),
      );
      try {
        const link = document.createElement('a');
        link.href = url;
        link.download = 'caseproof-preserved-original.docx';
        link.click();
      } finally {
        URL.revokeObjectURL(url);
      }
      setMessage(
        'Download started. The saved file is outside the application session.',
      );
    } catch {
      if (!controller.signal.aborted)
        setMessage(
          'The preserved original is unavailable or access has changed.',
        );
    } finally {
      pending.current = null;
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  return (
    <div>
      <button
        type="button"
        className="button"
        disabled={busy}
        onClick={() => void download()}
      >
        Download preserved original DOCX
      </button>
      <p role="status">{message}</p>
    </div>
  );
}
