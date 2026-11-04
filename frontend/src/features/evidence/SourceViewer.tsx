import { useEffect, useRef, useState } from 'react';
import type { FindingView } from '../../shared/api';
import {
  boundedInspection,
  InspectionTimeout,
} from '../../shared/pdf/lifecycle';
import { pageSpaceLabel } from './pageSpaces';
import { ApiClient, parseViewer } from '../../shared/api';
import { Button, Notice } from '../../shared/ui';
import type { DocumentInspection } from '../../shared/pdf/geometry';
import type { PdfPageResult, RasterRegion } from '../../shared/pdf/geometry';
import {
  parseRasterRegions,
  projectRasterBox,
} from '../../shared/pdf/geometry';
export interface ViewerScope {
  caseId: string;
  briefId: string;
  snapshot: string;
  referenceId: string;
  historical?: boolean;
}
interface SourceViewerProps {
  api: ApiClient;
  scope: ViewerScope;
  finding: FindingView;
  onInspected?: () => void;
}
export function SourceViewer(props: SourceViewerProps) {
  const [attempt, setAttempt] = useState(0);
  if (props.finding.reference_id !== props.scope.referenceId)
    return (
      <Notice error>The source selection changed. Reopen this report.</Notice>
    );
  return (
    <SourceInspection
      key={JSON.stringify([props.scope, attempt])}
      {...props}
      onRetry={() => setAttempt((value) => value + 1)}
    />
  );
}
function SourceInspection({
  api,
  scope,
  finding,
  onRetry,
  onInspected,
}: SourceViewerProps & { onRetry: () => void }) {
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
  const [showOcr, setShowOcr] = useState(false);
  const [mapping, setMapping] = useState('');
  const [hash, setHash] = useState('');
  const [legacy, setLegacy] = useState(0);
  const [rasterRegions, setRasterRegions] = useState<RasterRegion[]>([]);
  const [unassessed, setUnassessed] = useState(0);
  const [mappedPage, setMappedPage] = useState<number | null>(null);
  const [version, setVersion] = useState('');
  const { caseId, briefId, snapshot, referenceId, historical = false } = scope;
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
    const base = `/v2/matters/${encodeURIComponent(caseId)}/briefs/${encodeURIComponent(briefId)}/dossier`;
    const path = historical
      ? `${base}/history/${encodeURIComponent(snapshot)}/references/${encodeURIComponent(referenceId)}/viewer`
      : `${base}/snapshots/${encodeURIComponent(snapshot)}/references/${encodeURIComponent(referenceId)}/viewer`;
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
        const regions = parseRasterRegions(
          await api.get(path + '/regions', controller.signal),
          {
            snapshot,
            sha256: context.original_sha256,
            version: context.version_id,
          },
        );
        if (controller.signal.aborted) return;
        setRasterRegions(regions.regions);
        setUnassessed(regions.unassessed);
        const { PdfInspection } = await import('../../shared/pdf/engine');
        if (controller.signal.aborted) return;
        inspection = new PdfInspection();
        engine.current = inspection;
        await boundedInspection(
          inspection.open(bytes),
          controller.signal,
          () => {
            void inspection?.close();
          },
        );
        if (controller.signal.aborted) return;
        setHash(context.original_sha256);
        setVersion(context.version_id);
        setMappedPage(context.pdf_page);
        setPages(inspection.pages);
        setMapping(context.page_mapping);
        setLegacy(context.legacy_region_count);
        if (context.pdf_page !== null && context.pdf_page > inspection.pages)
          throw new Error('Mapped page unavailable');
        setPage(context.pdf_page ?? 1);
        setRendering(true);
        setReady(true);
      } catch (reason) {
        if (!controller.signal.aborted)
          setError(
            reason instanceof InspectionTimeout
              ? 'PDF opening exceeded its time budget.'
              : 'This source could not be opened. It may be unavailable, unsupported or outside the inspection budget.',
          );
        void inspection?.close();
      }
    })();
    return () => {
      controller.abort();
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
  }, [api, caseId, briefId, snapshot, referenceId, historical]);
  useEffect(() => {
    if (!ready || !engine.current || !canvas.current) return;
    let active = true;
    const inspection = engine.current;
    setRendering(true);
    setError('');
    setResult(null);
    const controller = new AbortController();
    void boundedInspection(
      inspection.render(
        canvas.current,
        page,
        zoom,
        rotation,
        Math.max(1, Math.min(devicePixelRatio || 1, 3)),
        availableWidth,
      ),
      controller.signal,
      () => {
        void inspection.close();
      },
    )
      .then((value) => {
        if (active) setResult(value);
      })
      .catch((reason: unknown) => {
        if (active) {
          if (canvas.current) canvas.current.width = 0;
          setResult(null);
          setError(
            reason instanceof InspectionTimeout
              ? 'Page rendering exceeded its time budget. Reopen this source to retry.'
              : 'This page could not be rendered. Reduce zoom or select another page.',
          );
        }
      })
      .finally(() => {
        if (active) setRendering(false);
      });
    return () => {
      active = false;
      inspection.cancelRender();
      controller.abort();
    };
  }, [ready, page, zoom, rotation, availableWidth]);
  useEffect(() => {
    if (!overlay.current || !canvas.current) return;
    const layer = overlay.current;
    layer.width = canvas.current.width;
    layer.height = canvas.current.height;
    const context = layer.getContext('2d');
    if (!context || !result) return;
    const xScale = layer.width / result.width,
      yScale = layer.height / result.height;
    context.strokeStyle = getComputedStyle(layer).getPropertyValue('--focus');
    context.lineWidth = 2 * xScale;
    for (const region of showBoxes ? rasterRegions : []) {
      if (region.page_number !== page || region.original_sha256 !== hash)
        continue;
      const box = projectRasterBox(region, result);
      if (!box) continue; // Unsupported geometry is never guessed.
      context.strokeRect(
        box[0] * xScale,
        box[1] * yScale,
        (box[2] - box[0]) * xScale,
        (box[3] - box[1]) * yScale,
      );
    }
    if (showOcr) {
      const words = rasterRegions.filter(
        (region) =>
          region.page_number === page &&
          region.original_sha256 === hash &&
          region.ocr_word,
      );
      words.forEach((region, index) => {
        const box = projectRasterBox(
          { ...region, bbox: region.ocr_word!.bbox },
          result,
        );
        if (!box) return;
        context.strokeRect(
          box[0] * xScale,
          box[1] * yScale,
          (box[2] - box[0]) * xScale,
          (box[3] - box[1]) * yScale,
        );
        context.font = `${Math.max(12, 12 * xScale)}px sans-serif`;
        context.fillStyle = context.strokeStyle;
        context.fillText(
          String(index + 1),
          box[0] * xScale,
          Math.max(12, box[1] * yScale),
        );
      });
    }
    if (!showBoxes || !search.trim()) return;
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
  }, [result, search, showBoxes, showOcr, rasterRegions, page, hash]);
  useEffect(() => {
    if (
      result &&
      !rendering &&
      mapping === 'mapped' &&
      page === mappedPage &&
      !historical
    ) {
      onInspected?.();
    }
  }, [result, rendering, mapping, page, mappedPage, historical, onInspected]);
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
      {error && (
        <>
          <Notice error>{error}</Notice>
          <Button onClick={onRetry}>Reopen source</Button>
        </>
      )}
      {!ready && !error && <Notice>Opening the authorized source…</Notice>}
      {ready && (
        <>
          <dl className="dimensions" aria-label="Reference page spaces">
            <div className="dimension">
              <dt>Reference PDF page</dt>
              <dd>
                {mappedPage ??
                  (mapping === 'conflicting'
                    ? 'Conflicting mapping'
                    : 'Unmapped')}
              </dd>
            </div>
            <div className="dimension">
              <dt>Printed page</dt>
              <dd>
                {pageSpaceLabel(finding.page_spaces, 'printed', mappedPage)}
              </dd>
            </div>
            <div className="dimension">
              <dt>Bundle page</dt>
              <dd>
                {pageSpaceLabel(finding.page_spaces, 'bundle', mappedPage)}
              </dd>
            </div>
          </dl>
          {(finding.fidelity === 'ocr_unreliable' ||
            finding.fidelity === 'representation_conflict') && (
            <Notice>
              {finding.fidelity === 'ocr_unreliable'
                ? 'OCR is unreliable for this reference. Inspect the preserved pixels; extracted text does not resolve that uncertainty.'
                : 'The source representations conflict. Inspect the preserved pixels alongside the literal text; finding states remain unchanged.'}
            </Notice>
          )}
          {mappedPage !== null && page !== mappedPage && (
            <Notice>
              Browsing another PDF page. The reference targets PDF page{' '}
              {mappedPage}; printed and bundle labels above describe that
              reference target.
            </Notice>
          )}
          {mappedPage !== null && (
            <Button
              disabled={page === mappedPage}
              onClick={() => {
                clearPage();
                setPage(mappedPage);
              }}
            >
              Return to reference page
            </Button>
          )}
          <p>
            {historical ? 'Historical original version · read-only. ' : ''}
            Reference page mapping: {mapping}.{' '}
            {mapping !== 'mapped' &&
              'Page 1 is an exploration starting point, not a mapped reference.'}
          </p>
          {(legacy > 0 || unassessed > 0) && (
            <Notice>
              Legacy and unsupported raster regions are not guessed.{' '}
              {unassessed}
              region(s) in this report have unassessed provenance. Overlay
              outlines are navigation aids, not an assessment or a human
              decision.
            </Notice>
          )}
          {rasterRegions.length > 0 && (
            <p role="status">
              {
                rasterRegions.filter(
                  (region) =>
                    region.page_number === page &&
                    result &&
                    projectRasterBox(region, result),
                ).length
              }{' '}
              source-bound raster outline(s) aligned on this page.
            </p>
          )}
          {rasterRegions.some(
            (region) => region.page_number === page && region.ocr_word,
          ) && (
            <>
              <Button
                aria-pressed={showOcr}
                onClick={() => setShowOcr((value) => !value)}
              >
                {showOcr
                  ? 'Hide OCR word positions'
                  : 'Show OCR word positions'}
              </Button>
              {showOcr && (
                <div>
                  <p>
                    Derived OCR words and numbered positions are navigation
                    aids, not proof of accuracy or support. Only available valid
                    positions are shown; omissions do not establish complete
                    OCR. Compare them with the preserved pixels.
                  </p>
                  <ol aria-label="OCR words on this page">
                    {rasterRegions
                      .filter(
                        (region) =>
                          region.page_number === page && region.ocr_word,
                      )
                      .map((region) => (
                        <li key={region.region_id}>{region.ocr_word!.text}</li>
                      ))}
                  </ol>
                </div>
              )}
            </>
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
                  sourceVersion: version,
                  referenceId,
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
