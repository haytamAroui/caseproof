import { useEffect, useRef, useState } from 'react';
import { ApiClient, parseViewer } from '../../shared/api';
import { Button, Notice } from '../../shared/ui';
import type { DocumentInspection } from '../../shared/pdf/geometry';
import type { PdfPageResult } from '../../shared/pdf/geometry';
export interface ViewerScope {
  caseId: string;
  briefId: string;
  snapshot: string;
  referenceId: string;
}
export function SourceViewer({
  api,
  scope,
}: {
  api: ApiClient;
  scope: ViewerScope;
}) {
  const frame = useRef<HTMLDivElement>(null);
  const [availableWidth, setAvailableWidth] = useState(600);
  const canvas = useRef<HTMLCanvasElement>(null);
  const overlay = useRef<HTMLCanvasElement>(null);
  const engine = useRef<DocumentInspection | null>(null);
  const [ready, setReady] = useState(false);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [rendering, setRendering] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<PdfPageResult | null>(null);
  const [search, setSearch] = useState('');
  const [showBoxes, setShowBoxes] = useState(true);
  const [mapping, setMapping] = useState('');
  const [hash, setHash] = useState('');
  const [legacy, setLegacy] = useState(0);
  const { caseId, briefId, snapshot, referenceId } = scope;
  useEffect(() => {
    if (!frame.current) return;
    const observer = new ResizeObserver((entries) => {
      const width = Math.max(
        100,
        Math.min(2000, Math.round(entries[0]?.contentRect.width ?? 600)),
      );
      setAvailableWidth((previous) => (previous === width ? previous : width));
    });
    observer.observe(frame.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const pixels = canvas.current,
      boxes = overlay.current;
    let inspection: DocumentInspection | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const path = `/v2/matters/${encodeURIComponent(caseId)}/briefs/${encodeURIComponent(briefId)}/dossier/snapshots/${encodeURIComponent(snapshot)}/references/${encodeURIComponent(referenceId)}/viewer`;
    void (async () => {
      try {
        const context = parseViewer(await api.get(path, controller.signal), {
          caseId,
          briefId,
          snapshot,
          referenceId,
        });
        const bytes = await api.pdf(
          path + '/original',
          {
            sha256: context.original_sha256,
            snapshot,
            length: context.byte_length,
          },
          controller.signal,
        );
        if (controller.signal.aborted) return;
        const { PdfInspection } = await import('../../shared/pdf/engine');
        if (controller.signal.aborted) return;
        inspection = new PdfInspection();
        engine.current = inspection;
        timer = setTimeout(() => {
          controller.abort();
          void inspection?.close();
          setError('PDF opening exceeded its time budget.');
        }, 15000);
        await inspection.open(bytes);
        clearTimeout(timer);
        if (controller.signal.aborted) return;
        setHash(context.original_sha256);
        setPages(inspection.pages);
        setMapping(context.page_mapping);
        setLegacy(context.legacy_region_count);
        if (context.pdf_page !== null && context.pdf_page > inspection.pages)
          throw new Error('Mapped page unavailable');
        setPage(context.pdf_page ?? 1);
        setRendering(true);
        setReady(true);
      } catch {
        if (!controller.signal.aborted)
          setError(
            'This source could not be opened. It may be unavailable, unsupported or outside the inspection budget.',
          );
        void inspection?.close();
      }
    })();
    return () => {
      controller.abort();
      clearTimeout(timer);
      void inspection?.close();
      engine.current = null;
      if (pixels) {
        pixels.width = 0;
        pixels.height = 0;
      }
      if (boxes) {
        boxes.width = 0;
        boxes.height = 0;
      }
    };
  }, [api, caseId, briefId, snapshot, referenceId]);
  useEffect(() => {
    if (!ready || !engine.current || !canvas.current) return;
    let active = true;
    const inspection = engine.current;
    setRendering(true);
    setError('');
    setResult(null);
    const timer = setTimeout(() => {
      if (active) {
        void inspection.close();
        setError(
          'Page rendering exceeded its time budget. Reopen the report to retry.',
        );
        setRendering(false);
      }
    }, 15000);
    void inspection
      .render(
        canvas.current,
        page,
        zoom,
        rotation,
        Math.min(devicePixelRatio || 1, 3),
        availableWidth,
      )
      .then((value) => {
        if (active) setResult(value);
      })
      .catch(() => {
        if (active) {
          if (canvas.current) canvas.current.width = 0;
          setError(
            'This page could not be rendered. Reduce zoom or select another page.',
          );
        }
      })
      .finally(() => {
        clearTimeout(timer);
        if (active) setRendering(false);
      });
    return () => {
      active = false;
      inspection.cancelRender();
      clearTimeout(timer);
    };
  }, [ready, page, zoom, rotation, availableWidth]);
  useEffect(() => {
    if (!overlay.current || !canvas.current) return;
    const layer = overlay.current;
    layer.width = canvas.current.width;
    layer.height = canvas.current.height;
    const context = layer.getContext('2d');
    if (!context || !result || !showBoxes || !search.trim()) return;
    const xScale = layer.width / result.width,
      yScale = layer.height / result.height;
    context.strokeStyle = getComputedStyle(layer).getPropertyValue('--focus');
    context.lineWidth = 2 * xScale;
    for (const item of result.textBoxes.filter((item) =>
      item.text.includes(search),
    )) {
      const [x1, y1, x2, y2] = item.box;
      context.strokeRect(
        x1 * xScale,
        y1 * yScale,
        (x2 - x1) * xScale,
        (y2 - y1) * yScale,
      );
    }
  }, [result, search, showBoxes]);
  function clearPage() {
    if (canvas.current) canvas.current.width = 0;
    if (overlay.current) overlay.current.width = 0;
    engine.current?.cancelRender();
    setResult(null);
    setRendering(true);
  }
  const matches =
    result && search.trim()
      ? result.textBoxes.filter((item) => item.text.includes(search)).length
      : 0;
  return (
    <section className="source-viewer" aria-label="Preserved PDF inspection">
      <h3>Preserved source pixels</h3>
      <Notice>
        Source inspection does not change identity, page mapping, fidelity or
        human support. Extracted text and search boxes below are derived
        navigation aids.
      </Notice>
      {error && <Notice error>{error}</Notice>}
      {!ready && !error && <Notice>Opening the authorized source…</Notice>}
      {ready && (
        <>
          <p>
            Reference page mapping: {mapping}.{' '}
            {mapping !== 'mapped' &&
              'Page 1 is an exploration starting point, not a mapped reference.'}
          </p>
          {legacy > 0 && (
            <Notice>
              {legacy} frozen raster regions lack complete PDF page-box
              geometry. They are not projected onto this page. Inspect their
              original crops separately.
            </Notice>
          )}
          <div className="viewer-controls" aria-label="Source page controls">
            <Button
              disabled={page <= 1}
              onClick={() => {
                clearPage();
                setPage((p) => p - 1);
              }}
            >
              Previous source page
            </Button>
            <span>
              PDF page {page} of {pages}
            </span>
            <Button
              disabled={page >= pages}
              onClick={() => {
                clearPage();
                setPage((p) => p + 1);
              }}
            >
              Next source page
            </Button>
            <Button
              disabled={zoom <= 0.5}
              onClick={() => {
                clearPage();
                setZoom((z) => z - 0.25);
              }}
            >
              Zoom out
            </Button>
            <span>Zoom {Math.round(zoom * 100)}%</span>
            <Button
              disabled={zoom >= 2}
              onClick={() => {
                clearPage();
                setZoom((z) => z + 0.25);
              }}
            >
              Zoom in
            </Button>
            <Button
              onClick={() => {
                clearPage();
                setRotation((r) => (r + 90) % 360);
              }}
            >
              Rotate page
            </Button>
          </div>
          <label>
            Find text on this page
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              autoComplete="off"
              maxLength={4096}
              spellCheck={false}
            />
          </label>
          {search && (
            <Button onClick={() => setSearch('')}>Clear page search</Button>
          )}
          <Button
            aria-pressed={showBoxes}
            onClick={() => setShowBoxes((v) => !v)}
          >
            {showBoxes ? 'Hide navigation boxes' : 'Show navigation boxes'}
          </Button>
          {search && (
            <p role="status">
              {matches} derived text locations in this page. All occurrences are
              retained; none is a verified match.
            </p>
          )}
          <p role="status">
            {rendering
              ? 'Rendering source page…'
              : result
                ? 'Source page rendered.'
                : ''}
          </p>
        </>
      )}
      <div
        ref={frame}
        className="viewer-scroll"
        role="region"
        aria-label="Scrollable source page"
        tabIndex={0}
      >
        <div
          className={`viewer-page viewer-zoom-${zoom * 100}`}
          aria-busy={rendering}
        >
          <canvas
            role="img"
            ref={canvas}
            aria-label="Preserved PDF page pixels"
          >
            Use extracted text below or inspect the original document.
          </canvas>
          <canvas ref={overlay} className="viewer-overlay" aria-hidden="true" />
        </div>
      </div>
      {result && (
        <>
          <details>
            <summary>
              Extracted text — derived, not an OCR or fidelity assessment
            </summary>
            <pre>
              {result.text ||
                'No selectable text was extracted. This does not establish OCR coverage or verification.'}
            </pre>
          </details>
          <details>
            <summary>Page geometry and provenance</summary>
            <pre>
              {JSON.stringify(
                {
                  originalSha256: hash,
                  snapshot,
                  physicalPage: page,
                  viewBox: result.view,
                  userUnit: result.userUnit,
                  rotation: result.rotation,
                  viewportTransform: result.transform,
                  coordinateSpace:
                    'PDF user space → actual viewport → backing pixels; CSS fits the same aspect ratio',
                },
                null,
                2,
              )}
            </pre>
          </details>
        </>
      )}
    </section>
  );
}
