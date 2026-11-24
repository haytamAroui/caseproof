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
  term?: string;
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
  const overlay = useRef<HTMLCanvasElement>(null);
  const engine = useRef<PdfInspection | null>(null);
  const [outlined, setOutlined] = useState(0);
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
    if (overlay.current) overlay.current.width = 0;
    setOutlined(0);
    setState('closed');
  }

  /** Outlines the text LINES (extracted text items) that literally contain the word. Line-level, not word-level. */
  function outline(result: Awaited<ReturnType<PdfInspection['render']>>) {
    const base = canvas.current;
    const layer = overlay.current;
    if (!base || !layer || !result) return;
    layer.width = base.width;
    layer.height = base.height;
    const context = layer.getContext('2d');
    const word = (found.term ?? '').toLowerCase();
    let count = 0;
    if (context && word) {
      const xs = layer.width / result.width;
      const ys = layer.height / result.height;
      context.strokeStyle = '#8a6d00';
      context.fillStyle = 'rgba(255, 224, 102, 0.35)';
      context.lineWidth = 2 * xs;
      for (const item of result.textBoxes) {
        if (!item.text.toLowerCase().includes(word)) continue;
        const [x1, y1, x2, y2] = item.box;
        context.fillRect(x1 * xs, y1 * ys, (x2 - x1) * xs, (y2 - y1) * ys);
        context.strokeRect(x1 * xs, y1 * ys, (x2 - x1) * xs, (y2 - y1) * ys);
        count += 1;
      }
    }
    setOutlined(count);
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
      const rendered = await boundedInspection(
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
      outline(rendered);
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
    <div className="small">
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
        <p role="note">
          {`Original page ${page} of ${pages}, digest ${found.original_sha256.slice(0, 12)}… verified before display. `}
          {outlined > 0
            ? `${outlined} text line(s) containing the word are outlined (line-level, not the exact word). `
            : 'The word could not be located in the page text layer, so nothing is outlined. '}
          The page is not a check of what it means.
        </p>
      )}
      <div className="viewer-page" hidden={state !== 'open'}>
        <canvas
          ref={canvas}
          aria-label={`Original PDF page ${page} of ${found.piece}`}
        />
        <canvas ref={overlay} className="viewer-overlay" aria-hidden="true" />
      </div>
    </div>
  );
}
