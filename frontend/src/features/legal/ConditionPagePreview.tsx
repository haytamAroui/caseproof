import { useEffect, useRef, useState } from 'react';
import type { ApiClient } from '../../shared/api';
import { Button, Notice } from '../../shared/ui';
import {
  boundedInspection,
  InspectionTimeout,
} from '../../shared/pdf/lifecycle';
import type { PdfInspection } from '../../shared/pdf/engine';

interface Found {
  source_id: string;
  version_id: string;
  original_sha256: string;
  pdf_page?: number | null;
  piece: string;
}

/**
 * Opens the located physical page of the ORIGINAL PDF behind a condition excerpt.
 * The bytes must hash to the digest the signed result carries. This shows where the word was located. It does not
 * highlight the word and it is not a check that the passage means what the condition asks.
 */
export function ConditionPagePreview(props: {
  api: ApiClient;
  caseId: string;
  briefId: string;
  found: Found;
}) {
  const { api, caseId, briefId, found } = props;
  const canvas = useRef<HTMLCanvasElement>(null);
  const engine = useRef<PdfInspection | null>(null);
  const [state, setState] = useState<'closed' | 'loading' | 'open' | 'error'>(
    'closed',
  );
  const [pages, setPages] = useState(0);
  const [message, setMessage] = useState('');
  const abort = useRef<AbortController | null>(null);

  useEffect(
    () => () => {
      abort.current?.abort();
      void engine.current?.close();
      engine.current = null;
    },
    [],
  );
  if (found.pdf_page === null || found.pdf_page === undefined) return null;
  const page = found.pdf_page;

  function close() {
    abort.current?.abort();
    void engine.current?.close();
    engine.current = null;
    if (canvas.current) canvas.current.width = 0;
    setState('closed');
  }

  async function open() {
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    setState('loading');
    setMessage('');
    let inspection: PdfInspection | null = null;
    try {
      const path = `/v2/matters/${encodeURIComponent(caseId)}/briefs/${encodeURIComponent(briefId)}/sources/${encodeURIComponent(found.source_id)}/versions/${encodeURIComponent(found.version_id)}/original`;
      const bytes = await api.signedOriginal(
        path,
        found.original_sha256,
        controller.signal,
      );
      const { PdfInspection: Engine } = await import('../../shared/pdf/engine');
      if (controller.signal.aborted) return;
      inspection = new Engine();
      engine.current = inspection;
      const opened = inspection;
      await boundedInspection(opened.open(bytes), controller.signal, () => {
        void opened.close();
      });
      if (controller.signal.aborted) return;
      if (page > opened.pages) throw new Error('page unavailable');
      setPages(opened.pages);
      setState('open');
      if (!canvas.current) throw new Error('canvas unavailable');
      await boundedInspection(
        opened.render(
          canvas.current,
          page,
          1,
          0,
          Math.max(1, Math.min(devicePixelRatio || 1, 2)),
          520,
        ),
        controller.signal,
        () => {
          void opened.close();
        },
      );
    } catch (reason) {
      if (controller.signal.aborted) return;
      void inspection?.close();
      engine.current = null;
      setState('error');
      setMessage(
        reason instanceof InspectionTimeout
          ? 'Opening the original exceeded its time budget.'
          : 'The original could not be opened, or it does not match its recorded digest. Nothing is shown.',
      );
    }
  }

  return (
    <span className="small" style={{ display: 'block' }}>
      {state === 'closed' || state === 'error' ? (
        <Button
          onClick={() => {
            void open();
          }}
        >
          {`Open original PDF page ${page} (${found.piece})`}
        </Button>
      ) : (
        <Button onClick={close}>Close page</Button>
      )}
      {state === 'loading' && ' Opening the original…'}
      {state === 'error' && <Notice error>{message}</Notice>}
      {state === 'open' && (
        <span role="note" style={{ display: 'block' }}>
          {`Original page ${page} of ${pages}, digest ${found.original_sha256.slice(0, 12)}… verified before display. The word is not highlighted and the page is not a check of what it means.`}
        </span>
      )}
      <canvas
        ref={canvas}
        aria-label={`Original PDF page ${page} of ${found.piece}`}
        style={{ display: state === 'open' ? 'block' : 'none' }}
      />
    </span>
  );
}
