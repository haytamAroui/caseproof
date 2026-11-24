import { useState } from 'react';
import type { ApiClient } from '../../shared/api';
import { parseOfflinePackManifest } from '../../shared/api/legal';
import { Button, Notice } from '../../shared/ui';

/** Downloads the offline review pack only if its bytes match the manifest just read. */
export function PackDownload({
  api,
  caseId,
  briefId,
  snapshot,
}: {
  api: ApiClient;
  caseId: string;
  briefId: string;
  snapshot: string;
}) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [bad, setBad] = useState(false);
  const base = `/v2/matters/${encodeURIComponent(caseId)}/briefs/${encodeURIComponent(briefId)}/offline-pack`;
  async function run() {
    if (busy) return;
    setBusy(true);
    setBad(false);
    setMsg('Preparing the pack…');
    const controller = new AbortController();
    try {
      const manifest = parseOfflinePackManifest(
        await api.get(`${base}/manifest`, controller.signal),
        { briefId, snapshot },
      );
      const bytes = await api.offlinePack(
        base,
        {
          sha256: manifest.sha256,
          snapshot: manifest.snapshot_hash,
          length: manifest.byte_length,
        },
        controller.signal,
      );
      const url = URL.createObjectURL(
        new Blob([bytes.slice().buffer], { type: 'application/zip' }),
      );
      try {
        const link = document.createElement('a');
        link.href = url;
        link.download = 'caseproof-offline-legal-review.zip';
        link.click();
      } finally {
        URL.revokeObjectURL(url);
      }
      setMsg(
        `Download started (${manifest.byte_length} bytes, SHA-256 ${manifest.sha256}, review checkpoint ${manifest.checkpoint_sha256}). ${manifest.note}`,
      );
    } catch {
      setBad(true);
      setMsg(
        'The pack could not be prepared or its bytes did not match this check (the review may have changed). Nothing was saved. Reload and try again.',
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      <Button
        onClick={() => {
          void run();
        }}
        disabled={busy}
      >
        Download offline review pack (ZIP)
      </Button>
      {msg && (bad ? <Notice error>{msg}</Notice> : <p role="status">{msg}</p>)}
    </div>
  );
}
