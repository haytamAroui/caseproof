import { useEffect, useRef, useState } from 'react';
import type { ApiClient } from '../../shared/api';
import { boundedInspection } from '../../shared/pdf/lifecycle';
import type { DocumentInspection } from '../../shared/pdf/geometry';
import { Notice } from '../../shared/ui';

/** Authorized source inspection without inventing a finding or a page mapping. */
export function CoverageSource({
  api,
  caseId,
  briefId,
  snapshot,
  historical,
  versionId,
  sha256,
  length,
  page,
  onClose,
}: {
  api: ApiClient;
  caseId: string;
  briefId: string;
  snapshot: string;
  historical: boolean;
  versionId: string;
  sha256: string;
  length: number;
  page: number;
  onClose: () => void;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [status, setStatus] = useState('Opening the authorized original…');
  useEffect(() => {
    const controller = new AbortController();
    const pixels = canvas.current;
    let engine: DocumentInspection | undefined;
    const base = `/v2/matters/${encodeURIComponent(caseId)}/briefs/${encodeURIComponent(briefId)}/dossier`;
    const path = historical
      ? `${base}/history/${snapshot}/sources/${encodeURIComponent(versionId)}/original`
      : `${base}/sources/${encodeURIComponent(versionId)}/original?snapshot_hash=${snapshot}`;
    void (async () => {
      try {
        const bytes = await api.preservedOriginal(
          path,
          { sha256, snapshot, length },
          controller.signal,
        );
        if (controller.signal.aborted || !pixels) return;
        const { PdfInspection } = await import('../../shared/pdf/engine');
        if (controller.signal.aborted) return;
        engine = new PdfInspection();
        await boundedInspection(engine.open(bytes), controller.signal, () => {
          void engine?.close();
        });
        if (page > engine.pages) throw new Error('Page unavailable');
        await boundedInspection(
          engine.render(
            pixels,
            page,
            1,
            0,
            Math.max(1, Math.min(devicePixelRatio || 1, 3)),
            600,
          ),
          controller.signal,
          () => {
            void engine?.close();
          },
        );
        if (!controller.signal.aborted)
          setStatus(
            `Original PDF page ${page} rendered. This is coverage navigation, not a mapped reference or review.`,
          );
      } catch {
        if (!controller.signal.aborted)
          setStatus(
            'This preserved source page could not be opened or authorized.',
          );
      }
    })();
    return () => {
      controller.abort();
      void engine?.close();
      if (pixels) pixels.width = 0;
    };
  }, [
    api,
    caseId,
    briefId,
    snapshot,
    historical,
    versionId,
    sha256,
    length,
    page,
  ]);
  return (
    <section className="draft-context" aria-label="Coverage original source">
      <h4>Preserved original: PDF page {page}</h4>
      <Notice>{status}</Notice>
      <button type="button" className="button" onClick={onClose}>
        Close coverage original
      </button>
      <div
        className="viewer-scroll"
        tabIndex={0}
        role="region"
        aria-label="Scrollable coverage source page"
      >
        <canvas
          ref={canvas}
          role="img"
          aria-label={`Preserved original PDF page ${page}`}
        />
      </div>
    </section>
  );
}
