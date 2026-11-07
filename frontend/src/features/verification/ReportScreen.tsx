import { useQuery } from '@tanstack/react-query';
import { motion, useReducedMotion } from 'motion/react';
import { useEffect, useId, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';
import type { ApiClient, FindingView } from '../../shared/api';
import { SplitHandle } from '../../shared/ui/SplitHandle';
import { useSession } from '../../shared/session';
import { Notice, StateValue } from '../../shared/ui';
import { readReport } from './api';
import { coveragePages, coverageRegions } from './coverageRegions';
import { quoteMatches } from './quoteComparison';
import { CoverageSource } from './CoverageSource';
import { OriginalDraftDownload } from './OriginalDraftDownload';
import type { ReactNode } from 'react';
const uuid =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
export function ReportScreen({
  api,
  renderSource,
  renderDraft,
  renderReview,
}: {
  api: ApiClient;
  renderSource?: (
    finding: FindingView,
    historical: boolean,
    onInspected: () => void,
  ) => ReactNode;
  renderDraft?: (finding: FindingView, historical: boolean) => ReactNode;
  renderReview?: (
    finding: FindingView,
    historical: boolean,
    inspected: boolean,
    onNext: (() => void) | undefined,
  ) => ReactNode;
}) {
  const { caseId = '', briefId = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const snapshot = params.get('snapshot') ?? '';
  const session = useSession();
  const valid =
    uuid.test(caseId) && uuid.test(briefId) && /^[0-9a-f]{64}$/.test(snapshot);
  const queueRef = useRef<HTMLElement>(null);
  const inspectionRef = useRef<HTMLElement>(null);
  const layoutRef = useRef<HTMLDivElement>(null);
  const [queueWidth, setQueueWidth] = useState(300);
  // Presentation preferences survive reference changes; source inspection does not.
  const [sourceWidth, setSourceWidth] = useState(400);
  const reduceMotion = useReducedMotion();
  const [readingMode, setReadingMode] = useState<'split' | 'draft' | 'source'>(
    'split',
  );
  const focusReference = useRef<string | null>(null);
  const [filter, setFilter] = useState<'attention' | 'all'>('attention');
  const [search, setSearch] = useState('');
  const query = useQuery({
    queryKey: ['report', session.epoch, caseId, briefId, snapshot],
    queryFn: ({ signal }) =>
      readReport(api, { caseId, briefId, snapshot }, signal),
    enabled: valid && session.connected,
  });
  useEffect(() => {
    if (!focusReference.current) return;
    const target = focusReference.current;
    focusReference.current = null;
    const buttons =
      queueRef.current?.querySelectorAll<HTMLButtonElement>('button.finding');
    Array.from(buttons ?? [])
      .find((button) => button.dataset.referenceId === target)
      ?.focus();
  }, [params, query.data]);
  if (!valid)
    return (
      <Notice error>
        The report link needs valid matter, brief and snapshot identifiers.
      </Notice>
    );
  if (query.isPending) return <Notice>Opening the preserved report…</Notice>;
  if (query.isError) return <Notice error>{query.error.message}</Notice>;
  const { report, mode } = query.data;
  const historical = mode === 'historical_read_only';
  const selected =
    report.findings.find((f) => f.reference_id === params.get('finding')) ??
    report.findings[0];
  const needsAttention = (f: FindingView) =>
    f.identity !== 'resolved' ||
    f.page_mapping !== 'mapped' ||
    f.fidelity !== 'exact_match' ||
    f.support !== 'supported';
  const filtered = report.findings
    .filter((f) => filter === 'all' || needsAttention(f))
    .filter((f) =>
      f.literal.toLocaleLowerCase().includes(search.toLocaleLowerCase()),
    )
    .sort((a, b) => Number(needsAttention(b)) - Number(needsAttention(a)));
  function selectReference(referenceId: string) {
    // Coverage links may target a reference hidden by the current filters.
    // Reveal it in the queue rather than displaying a selection the queue omits.
    const ordered = [...report.findings].sort(
      (a, b) => Number(needsAttention(b)) - Number(needsAttention(a)),
    );
    const index = ordered.findIndex(
      (finding) => finding.reference_id === referenceId,
    );
    if (index < 0) return;
    setFilter('all');
    setSearch('');
    setParams(
      (p) => {
        p.set('finding', referenceId);
        p.set('page', String(Math.floor(index / 50)));
        return p;
      },
      { replace: true },
    );
  }
  const pageSize = 50;
  const rawPage = Number(params.get('page') ?? 0);
  const page =
    Number.isInteger(rawPage) && rawPage >= 0
      ? Math.min(
          rawPage,
          Math.max(0, Math.ceil(filtered.length / pageSize) - 1),
        )
      : 0;
  const visible = filtered.slice(page * pageSize, (page + 1) * pageSize);
  const selectedQueueIndex = selected
    ? filtered.findIndex((f) => f.reference_id === selected.reference_id)
    : -1;
  const nextFinding =
    selectedQueueIndex >= 0 ? filtered[selectedQueueIndex + 1] : undefined;
  function movePage(next: number) {
    setParams(
      (p) => {
        p.set('page', String(next));
        const first = filtered[next * pageSize];
        if (first) p.set('finding', first.reference_id);
        return p;
      },
      { replace: true },
    );
  }
  function resetPage() {
    setParams(
      (p) => {
        p.set('page', '0');
        return p;
      },
      { replace: true },
    );
  }
  return (
    <>
      <header className="page-heading page-heading-review">
        <p className="eyebrow">
          {historical
            ? 'Historical report · read-only'
            : 'Current preserved report'}
        </p>
        <h1>Review the evidence</h1>
        <Link
          to={`/matters/${caseId}/exports?brief=${briefId}&snapshot=${snapshot}`}
        >
          Reviewed exports and historical downloads
        </Link>
        {!historical && (
          <Link
            to={`/matters/${caseId}/briefs/${briefId}/edit?snapshot=${snapshot}`}
          >
            Edit current DOCX candidate (not committed)
          </Link>
        )}
        {!historical && (
          <Link to={`/matters/${caseId}/inventory`}>
            Reconfirm inventory and page mappings
          </Link>
        )}
        <p>
          Each result describes a separate check. Human judgment remains
          separate.
        </p>
      </header>
      <Notice>
        {historical
          ? 'Historical snapshot. Current permissions were checked again, but this report cannot be reviewed, corrected, rechecked or exported as current. Source availability is checked separately.'
          : 'Current snapshot inspection. Human decisions remain separate from source rendering.'}
      </Notice>
      <div
        className="review-layout"
        ref={layoutRef}
        data-queue-width={queueWidth}
      >
        <section
          className="queue"
          aria-label="References"
          ref={queueRef}
          onKeyDown={(event) => {
            if (
              event.defaultPrevented ||
              event.altKey ||
              event.ctrlKey ||
              event.metaKey ||
              event.shiftKey ||
              event.nativeEvent.isComposing ||
              !(event.target instanceof HTMLButtonElement) ||
              !event.target.classList.contains('finding') ||
              (event.key !== 'j' && event.key !== 'k' && event.key !== ' ')
            )
              return;
            if (event.key === ' ') {
              event.preventDefault();
              const referenceId = event.target.dataset.referenceId;
              if (referenceId && referenceId !== selected?.reference_id) {
                setParams(
                  (current) => {
                    current.set('finding', referenceId);
                    return current;
                  },
                  { replace: true },
                );
              }
              inspectionRef.current?.focus();
              return;
            }
            const currentReference = event.target.dataset.referenceId;
            const index = filtered.findIndex(
              (finding) => finding.reference_id === currentReference,
            );
            const nextIndex = index + (event.key === 'j' ? 1 : -1);
            const next = index < 0 ? undefined : filtered[nextIndex];
            if (next) {
              event.preventDefault();
              focusReference.current = next.reference_id;
              setParams(
                (current) => {
                  current.set('finding', next.reference_id);
                  current.set('page', String(Math.floor(nextIndex / pageSize)));
                  return current;
                },
                { replace: true },
              );
            }
          }}
        >
          <h2>
            Findings <span>{report.findings.length}</span>
          </h2>
          <p role="status">
            {report.findings.filter(needsAttention).length} need attention out
            of {report.findings.length} detected references. Review coverage
            separately.
          </p>
          <p role="status">
            {filtered.length} references match the current filter and search.
            {selected &&
            !filtered.some((f) => f.reference_id === selected.reference_id)
              ? ' The selected reference is outside this queue; it remains open for inspection.'
              : ''}
          </p>
          <div className="catalog-actions">
            <button
              className="button"
              aria-pressed={filter === 'attention'}
              onClick={() => {
                setFilter('attention');
                resetPage();
              }}
            >
              Needs attention
            </button>
            <button
              className="button"
              aria-pressed={filter === 'all'}
              onClick={() => {
                setFilter('all');
                resetPage();
              }}
            >
              Show all
            </button>
          </div>
          <label>
            Search reference text (this session only)
            <input
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                resetPage();
              }}
              placeholder="Reference text"
              maxLength={200}
            />
          </label>
          {search && (
            <button
              className="button"
              onClick={() => {
                setSearch('');
                resetPage();
              }}
            >
              Clear reference search
            </button>
          )}
          <p className="small">
            When a reference button is focused, press J/K for next/previous or
            Space to inspect it. No decision is saved by a shortcut.
          </p>
          {report.findings.length === 0 ? (
            <p>
              No explicit references were detected. Inspect processing coverage
              before drawing conclusions.
            </p>
          ) : visible.length === 0 ? (
            <p>
              No references in this filter. Choose Show all to inspect the full
              scope.
            </p>
          ) : (
            <ul>
              {visible.map((f) => (
                <li key={f.reference_id}>
                  <button
                    className={`finding ${needsAttention(f) ? 'finding-attention' : 'finding-unflagged'}`}
                    data-reference-id={f.reference_id}
                    aria-current={
                      f.reference_id === selected?.reference_id
                        ? 'true'
                        : undefined
                    }
                    onClick={() =>
                      setParams(
                        (p) => {
                          p.set('finding', f.reference_id);
                          return p;
                        },
                        { replace: true },
                      )
                    }
                  >
                    {f.reference_id === selected?.reference_id && (
                      <motion.span
                        className="cockpit-selected-outline"
                        aria-hidden="true"
                        initial={reduceMotion ? false : { opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ duration: reduceMotion ? 0 : 0.16 }}
                      />
                    )}
                    {f.literal}
                    <small>
                      {needsAttention(f)
                        ? 'Needs attention'
                        : 'No machine discrepancy flagged'}{' '}
                      · {f.identity.replaceAll('_', ' ')}
                    </small>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {filtered.length > pageSize && (
            <nav aria-label="Reference pages">
              <p>
                {page * pageSize + 1}–
                {Math.min((page + 1) * pageSize, filtered.length)} of{' '}
                {filtered.length}
              </p>
              <button
                className="button"
                disabled={page === 0}
                onClick={() => movePage(page - 1)}
              >
                Previous references
              </button>
              <button
                className="button"
                disabled={(page + 1) * pageSize >= filtered.length}
                onClick={() => movePage(page + 1)}
              >
                Next references
              </button>
            </nav>
          )}
        </section>
        <SplitHandle
          containerRef={layoutRef}
          label="Resize findings queue"
          value={queueWidth}
          min={240}
          max={420}
          step={10}
          unit="px"
          reset={300}
          onChange={setQueueWidth}
          className="cockpit-queue-splitter"
        />
        <section
          className="inspection"
          id="inspection"
          aria-labelledby="finding-title"
          ref={inspectionRef}
          tabIndex={-1}
        >
          {selected ? (
            <>
              <FindingInspection
                key={`${session.epoch}:${caseId}:${briefId}:${snapshot}:${selected.reference_id}:${historical}`}
                finding={selected}
                historical={historical}
                sourceWidth={sourceWidth}
                onSourceWidthChange={setSourceWidth}
                readingMode={readingMode}
                onReadingModeChange={setReadingMode}
                renderSource={renderSource}
                renderDraft={renderDraft}
                renderReview={renderReview}
                onNext={
                  nextFinding
                    ? () => {
                        setParams(
                          (p) => {
                            p.set('finding', nextFinding.reference_id);
                            p.set(
                              'page',
                              String(
                                Math.floor((selectedQueueIndex + 1) / pageSize),
                              ),
                            );
                            return p;
                          },
                          { replace: true },
                        );
                      }
                    : undefined
                }
              />
            </>
          ) : (
            <h2 id="finding-title">No reference selected</h2>
          )}
          <CoverageSummary
            key={`${session.epoch}:${caseId}:${briefId}:${snapshot}:${historical}`}
            api={api}
            scope={{ caseId, briefId, snapshot, historical }}
            sources={report.sources}
            coverage={report.coverage}
            findings={report.findings}
            onSelectReference={selectReference}
          />
          <p className="small">
            Snapshot <code>{report.snapshot_hash}</code>
          </p>
        </section>
      </div>
    </>
  );
}

/**
 * Only displays snapshot-frozen, derived-text warnings. The lexical window
 * is never a verified PDF crop, NLI result or legal support classification.
 */
function ParaphraseGuardPanel({ finding }: { finding: FindingView }) {
  const raw = finding.paraphrase_guard;
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return (
      <Notice>
        This frozen report has no guarded-term review. Inspect the preserved
        source and surrounding context prior to making a semantic decision.
      </Notice>
    );
  }
  const guard = raw as Record<string, unknown>;
  if (
    guard.schema !== 'caseproof-paraphrase-review-guard-v1' ||
    guard.semantic_support !== 'not_assessed'
  )
    return (
      <Notice error>
        Unsupported guarded-term assessment. Review the original.
      </Notice>
    );
  const warnings = Array.isArray(guard.warnings)
    ? guard.warnings
        .slice(0, 24)
        .filter(
          (x): x is Record<string, unknown> =>
            x !== null && typeof x === 'object' && !Array.isArray(x),
        )
    : [];
  const candidateTerms = Array.isArray(guard.candidate_terms)
    ? guard.candidate_terms
        .slice(0, 24)
        .filter(
          (x): x is Record<string, unknown> =>
            x !== null && typeof x === 'object' && !Array.isArray(x),
        )
    : [];
  const reasonCodes = Array.isArray(guard.reason_codes)
    ? guard.reason_codes
        .slice(0, 12)
        .filter((x): x is string => typeof x === 'string')
    : [];
  const excerpt =
    typeof guard.source_excerpt === 'string'
      ? guard.source_excerpt.slice(0, 760)
      : '';
  const sourceVersion =
    typeof guard.source_version_id === 'string'
      ? guard.source_version_id.slice(0, 100)
      : 'unresolved';
  const pdfPage =
    typeof guard.pdf_page === 'number' && Number.isInteger(guard.pdf_page)
      ? guard.pdf_page
      : null;
  return (
    <section
      className="paraphrase-review-guard"
      aria-label="Deterministic paraphrase review warnings"
    >
      <h4>Guarded-term review — human assessment required</h4>
      <p>
        No automated claim verification. These lexical signals are warnings,
        never contradictions, support findings, or authenticated PDF locations.
      </p>
      <p className="small">
        Source version {sourceVersion}
        {pdfPage !== null
          ? ` · physical PDF page ${pdfPage}`
          : ' · pinpoint unavailable'}
        {' · '}Human support: not assessed by this guard
      </p>
      {warnings.length > 0 ? (
        <ul aria-label="Guarded terms requiring attention">
          {warnings.map((w, index) =>
            typeof w.kind === 'string' && typeof w.term === 'string' ? (
              <li key={index}>
                <strong>{w.kind.replaceAll('_', ' ')}:</strong>{' '}
                {w.term.slice(0, 96)} — not found in the nearby derived passage;
                inspect original pixels and adjacent paragraphs
              </li>
            ) : null,
          )}
        </ul>
      ) : (
        <p>
          {reasonCodes.length > 0
            ? 'Guarded terms could not be compared reliably. Inspect the original page and adjoining evidence.'
            : 'No lexical discrepancy identified. This does not establish semantic support.'}
        </p>
      )}
      {reasonCodes.length > 0 && candidateTerms.length > 0 && (
        <details>
          <summary>Unassessed guarded terms from the draft</summary>
          <ul aria-label="Guarded terms requiring original source inspection">
            {candidateTerms.map((item, index) =>
              typeof item.kind === 'string' && typeof item.term === 'string' ? (
                <li key={index}>
                  {item.kind.replaceAll('_', ' ')}: {item.term.slice(0, 96)}
                </li>
              ) : null,
            )}
          </ul>
          <p className="small">
            These terms were extracted only from the draft, not confirmed absent
            from any original exhibit.
          </p>
        </details>
      )}
      {reasonCodes.length > 0 && (
        <p className="small">
          Review limitations:{' '}
          {reasonCodes.join(', ').replaceAll('_', ' ').toLowerCase()}.
        </p>
      )}
      {excerpt && (
        <details>
          <summary>Read adjacent derived source context</summary>
          <blockquote>{excerpt}</blockquote>
          <p className="small">
            Derived page text for navigation only. The original PDF remains
            authoritative for inspection.
          </p>
        </details>
      )}
    </section>
  );
}

function QuoteContext({ finding }: { finding: FindingView }) {
  const [showMatches, setShowMatches] = useState(false);
  const quote = finding.quoted_text;
  const source = finding.source_text_context;
  const validQuote =
    typeof quote === 'string' && quote.length > 0 && quote.length <= 1000;
  const validSource =
    typeof source === 'string' && source.length > 0 && source.length <= 4000;
  const comparison =
    validQuote && validSource ? quoteMatches(source, quote) : null;
  return (
    <section
      className="draft-context"
      aria-label="Quotation and derived source text"
    >
      <h3>Quotation and derived source text</h3>
      <ParaphraseGuardPanel finding={finding} />
      <p>
        Compare this text with the preserved source pixels. A text match is not
        a finding of legal support.
      </p>
      <h4>Quotation in draft</h4>
      <p>
        {validQuote
          ? quote
          : 'No supported quotation is available in this report.'}
      </p>
      <h4>Extracted source text</h4>
      {validSource ? (
        <>
          {comparison && (
            <button
              type="button"
              className="button"
              aria-pressed={showMatches}
              onClick={() => setShowMatches((value) => !value)}
            >
              {showMatches
                ? 'Hide exact text highlights'
                : 'Highlight exact text occurrences'}
            </button>
          )}
          {showMatches && comparison && (
            <p role="status">
              {comparison.occurrences} exact occurrences in the supplied derived
              text. Highlights are text navigation only, not verified source
              locations.
            </p>
          )}
          <pre>
            {showMatches && comparison
              ? comparison.segments.map((segment, index) =>
                  segment.matched ? (
                    <mark key={index}>{segment.text}</mark>
                  ) : (
                    segment.text
                  ),
                )
              : source}
          </pre>
          <p>
            Derived page text; it may contain OCR errors and does not identify a
            verified crop.
            {finding.source_text_context_partial === false
              ? ''
              : ' The supplied text may be incomplete.'}
          </p>
        </>
      ) : (
        <p>
          Extracted source text is unavailable or unsupported. Inspect the
          preserved pixels.
        </p>
      )}
      {finding.translation_review_required === true && (
        <Notice>
          Translation requires human review; the texts may be in different
          languages.
        </Notice>
      )}
    </section>
  );
}

function FindingInspection({
  finding,
  historical,
  sourceWidth,
  onSourceWidthChange,
  readingMode,
  onReadingModeChange,
  renderSource,
  renderDraft,
  renderReview,
  onNext,
}: {
  finding: FindingView;
  historical: boolean;
  sourceWidth: number;
  onSourceWidthChange: (width: number) => void;
  readingMode: 'split' | 'draft' | 'source';
  onReadingModeChange: (mode: 'split' | 'draft' | 'source') => void;
  renderSource?:
    | ((
        finding: FindingView,
        historical: boolean,
        onInspected: () => void,
      ) => ReactNode)
    | undefined;
  renderDraft?:
    ((finding: FindingView, historical: boolean) => ReactNode) | undefined;
  renderReview?:
    | ((
        finding: FindingView,
        historical: boolean,
        inspected: boolean,
        onNext: (() => void) | undefined,
      ) => ReactNode)
    | undefined;
  onNext: (() => void) | undefined;
}) {
  const [inspected, setInspected] = useState(false);
  const readerRef = useRef<HTMLDivElement>(null);
  const widthControlId = useId();
  const reduceMotion = useReducedMotion();
  return (
    <div className="cockpit-reader">
      <div
        className="cockpit-view-switch"
        role="group"
        aria-label="Reading layout"
      >
        <button
          type="button"
          className="button"
          aria-pressed={readingMode === 'split'}
          onClick={() => onReadingModeChange('split')}
        >
          Split view
        </button>
        <button
          type="button"
          className="button"
          aria-pressed={readingMode === 'draft'}
          onClick={() => onReadingModeChange('draft')}
        >
          Draft focus
        </button>
        <button
          type="button"
          className="button"
          aria-pressed={readingMode === 'source'}
          onClick={() => onReadingModeChange('source')}
        >
          Source focus
        </button>
      </div>
      <motion.p
        key={readingMode}
        className="cockpit-reading-summary"
        initial={reduceMotion ? false : { opacity: 0, y: 3 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: reduceMotion ? 0 : 0.16, ease: 'easeOut' }}
        aria-live="polite"
      >
        {readingMode === 'split'
          ? 'Three-panel review: the preserved draft and original source remain separate. Drag the divider or use arrow keys.'
          : readingMode === 'draft'
            ? 'Draft focus. Source evidence is hidden, not verified or discarded.'
            : 'Source focus. Preserved original pixels remain the inspection authority.'}
      </motion.p>
      <div className="cockpit-resize-controls" hidden={readingMode !== 'split'}>
        <label htmlFor={widthControlId}>
          Source panel width: {sourceWidth}px
        </label>
        <input
          id={widthControlId}
          type="range"
          min={320}
          max={560}
          step={10}
          value={sourceWidth}
          onChange={(event) => onSourceWidthChange(Number(event.target.value))}
          aria-label="Source evidence panel width"
        />
        <button
          type="button"
          className="button"
          onClick={() => onSourceWidthChange(400)}
        >
          Restore 400px source
        </button>
      </div>
      <div
        ref={readerRef}
        className={`cockpit-inspection cockpit-mode-${readingMode}`}
        data-source-width={sourceWidth}
      >
        <div className="cockpit-draft">
          <p className="eyebrow">Selected reference</p>
          <h2 id="finding-title">{finding.literal}</h2>
          <dl className="dimensions cockpit-reference-dimensions">
            <StateValue label="Identity" value={finding.identity} />
            <StateValue label="Page mapping" value={finding.page_mapping} />
            <StateValue label="Fidelity" value={finding.fidelity} />
            <StateValue label="Human support" value={finding.support} />
          </dl>
          <header className="cockpit-pane-heading">
            <h3>Draft</h3>
            <span>Preserved DOCX · extracted context</span>
          </header>
          {renderDraft?.(finding, historical)}
          <QuoteContext finding={finding} />
        </div>
        {readingMode === 'split' && (
          <SplitHandle
            containerRef={readerRef}
            label="Resize draft and source panels"
            value={sourceWidth}
            min={320}
            max={560}
            step={10}
            unit="px"
            reset={400}
            fromEnd
            onChange={onSourceWidthChange}
            className="cockpit-draft-splitter"
          />
        )}
        <div className="cockpit-evidence">
          <header className="cockpit-pane-heading">
            <h3>Source evidence</h3>
            <span>{finding.literal} · original PDF</span>
          </header>
          {renderSource ? (
            renderSource(finding, historical, () => setInspected(true))
          ) : (
            <Notice error>
              Preserved source viewer unavailable. No human source inspection
              may be recorded.
            </Notice>
          )}
          {renderReview?.(finding, historical, inspected, onNext)}
        </div>
      </div>
    </div>
  );
}

function CoverageSummary({
  api,
  scope,
  sources,
  coverage,
  findings,
  onSelectReference,
}: {
  api: ApiClient;
  scope: {
    caseId: string;
    briefId: string;
    snapshot: string;
    historical: boolean;
  };
  sources: unknown;
  coverage: Record<string, unknown>;
  findings: FindingView[];
  onSelectReference: (reference: string) => void;
}) {
  const [selectedPage, setSelectedPage] = useState<{
    versionId: string;
    sha256: string;
    length: number;
    page: number;
  } | null>(null);
  const ledger = coverageRegions(coverage);
  const pageLedger = coveragePages(coverage);
  const drafts = Array.isArray(sources)
    ? sources.filter((source: unknown) => {
        if (!source || typeof source !== 'object' || Array.isArray(source))
          return false;
        const row = source as Record<string, unknown>;
        return (
          row.role === 'draft' &&
          row.version_id === scope.briefId &&
          row.media_type ===
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document' &&
          typeof row.sha256 === 'string' &&
          /^[0-9a-f]{64}$/.test(row.sha256) &&
          typeof row.byte_length === 'number' &&
          Number.isSafeInteger(row.byte_length) &&
          row.byte_length > 0 &&
          row.byte_length <= 20_000_000
        );
      })
    : [];
  const draft =
    drafts.length === 1
      ? (drafts[0] as { sha256: string; byte_length: number })
      : null;
  const referencesByPage = new Map<string, FindingView>();
  const referencesByRegion = new Map<string, FindingView>();
  for (const finding of findings) {
    if (
      finding.page_mapping === 'mapped' &&
      typeof finding.version_id === 'string' &&
      typeof finding.source_sha256 === 'string' &&
      typeof finding.pdf_page === 'number'
    ) {
      const key = JSON.stringify([
        finding.version_id,
        finding.source_sha256,
        finding.pdf_page,
      ]);
      if (!referencesByPage.has(key)) referencesByPage.set(key, finding);
    }
    if (
      typeof finding.region === 'string' &&
      !referencesByRegion.has(finding.region)
    )
      referencesByRegion.set(finding.region, finding);
  }
  const count = (key: string) =>
    typeof coverage[key] === 'number' &&
    Number.isInteger(coverage[key]) &&
    (coverage[key] as number) >= 0
      ? (coverage[key] as number)
      : null;
  const values = [
    ['Detected references', count('detected')],
    ['Checked identity and pinpoint', count('checked')],
    ['Unresolved', count('unresolved')],
    ['Unsupported notation', count('unsupported_references')],
    ['Unprocessed DOCX regions', count('unprocessed_regions')],
    ['Pending inventory exceptions', count('inventory_exceptions_pending')],
    ['Known source pages', count('source_pages_known_total')],
    [
      'Total source pages',
      pageLedger.unknown ? null : count('source_pages_total'),
    ],
    ['Pages processed by OCR worker', count('source_pages_ocr_processed')],
    ['Pages failed or not processed', count('source_pages_failed_or_skipped')],
    ['Visual pages completed', count('visual_pages_completed')],
    ['Visual findings not assessed', count('visual_findings_not_assessed')],
  ] as const;
  return (
    <section
      aria-label="Verification and processing coverage"
      id="coverage"
      className="draft-context"
    >
      <h3>Coverage and exclusions</h3>
      <p>
        These denominators describe assessed scope, not legal support or full
        reference recall.
      </p>
      <dl className="dimensions">
        {values.map(([label, value]) => (
          <div className="dimension" key={label}>
            <dt>{label}</dt>
            <dd>{value === null ? 'Not supplied' : value}</dd>
          </div>
        ))}
      </dl>
      {coverage.reference_recall_measured !== true && (
        <Notice>
          Reference detection recall has not been measured; an absence of
          references cannot mean all claims were checked.
        </Notice>
      )}
      {coverage.text_coverage_complete !== true && (
        <Notice>
          DOCX text coverage is partial or unknown. Unsupported regions may
          contain additional assertions.
        </Notice>
      )}
      {Array.isArray(coverage.limits) && (
        <ul>
          {coverage.limits
            .filter((x): x is string => typeof x === 'string')
            .map((limit) => (
              <li key={limit}>{limit}</li>
            ))}
        </ul>
      )}
      <details>
        <summary>DOCX region coverage</summary>
        {ledger.unknown && (
          <Notice>Region coverage is unavailable or unknown.</Notice>
        )}
        {ledger.invalid && (
          <Notice error>
            Some region entries could not be displayed safely.
          </Notice>
        )}
        {ledger.limited && (
          <Notice>Only the first 1,000 region entries are shown.</Notice>
        )}
        {ledger.regions.length === 0 ? (
          <p>
            No region entries are available. This does not prove complete
            coverage.
          </p>
        ) : (
          <ul aria-label="DOCX coverage regions">
            {ledger.regions.map((region, index) => {
              const reference = referencesByRegion.get(region.part);
              return (
                <li key={`${region.part}:${index}`}>
                  <p>
                    {region.part} · {region.kind}
                  </p>
                  <p>
                    Status: {region.status} · Reason: {region.reason}
                  </p>
                  {reference ? (
                    <button
                      type="button"
                      className="button"
                      onClick={() => onSelectReference(reference.reference_id)}
                    >
                      Open detected reference in this region
                    </button>
                  ) : (
                    <p>
                      No detected reference is available for navigation in this
                      region.
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        )}
        <p>
          Text extraction, visual inspection and editability are separate; a
          listed region is not a verified finding.
        </p>
        {draft && (
          <OriginalDraftDownload
            api={api}
            {...scope}
            sha256={draft.sha256}
            length={draft.byte_length}
          />
        )}
        {!draft && (
          <p>Preserved original DOCX access is unavailable for this report.</p>
        )}
      </details>
      <details>
        <summary>Source-page processing</summary>
        {pageLedger.unknown && (
          <Notice>
            The total source-page count is unavailable, unknown or inconsistent.
          </Notice>
        )}
        {pageLedger.invalid && (
          <Notice error>
            Some page entries could not be displayed safely.
          </Notice>
        )}
        {pageLedger.limited && (
          <Notice>Only the first 1,000 page entries are shown.</Notice>
        )}
        {pageLedger.pages.length === 0 ? (
          <p>No source-page entries are available.</p>
        ) : (
          <ul aria-label="Source-page processing ledger">
            {pageLedger.pages.map((page, index) => {
              const key = JSON.stringify([
                page.versionId,
                page.sha256,
                page.page,
              ]);
              const reference = referencesByPage.get(key);
              const matching = Array.isArray(sources)
                ? sources.filter((source: unknown) => {
                    if (
                      !source ||
                      typeof source !== 'object' ||
                      Array.isArray(source)
                    )
                      return false;
                    const row = source as Record<string, unknown>;
                    return (
                      row.version_id === page.versionId &&
                      row.sha256 === page.sha256 &&
                      row.media_type === 'application/pdf' &&
                      typeof row.byte_length === 'number' &&
                      Number.isSafeInteger(row.byte_length) &&
                      row.byte_length > 0 &&
                      row.byte_length <= 20_000_000
                    );
                  })
                : [];
              const length =
                matching.length === 1
                  ? (matching[0] as Record<string, unknown>).byte_length
                  : null;
              return (
                <li key={`${key}:${index}`}>
                  <p>
                    Source version {page.versionId} · PDF page {page.page}
                  </p>
                  <p>
                    Processing: {page.method} · Reason:{' '}
                    {page.reason ?? 'Not supplied'}
                  </p>
                  {reference ? (
                    <button
                      type="button"
                      className="button"
                      onClick={() => onSelectReference(reference.reference_id)}
                    >
                      Open reference on this source page
                    </button>
                  ) : (
                    <p>
                      No mapped reference is available for this source page.
                    </p>
                  )}
                  {typeof length === 'number' && page.page <= 200 && (
                    <button
                      type="button"
                      className="button"
                      onClick={() =>
                        setSelectedPage({
                          versionId: page.versionId,
                          sha256: page.sha256,
                          length,
                          page: page.page,
                        })
                      }
                    >
                      Open preserved PDF page {page.page}
                    </button>
                  )}
                  {(typeof length !== 'number' || page.page > 200) && (
                    <p>
                      Preserved PDF page access is unavailable for this entry.
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        )}
        <p>
          Page processing is not proof of source identity, fidelity or human
          support.
        </p>
      </details>
      {selectedPage && (
        <CoverageSource
          key={`${selectedPage.versionId}:${selectedPage.sha256}:${selectedPage.page}`}
          api={api}
          {...scope}
          {...selectedPage}
          onClose={() => setSelectedPage(null)}
        />
      )}
      <details>
        <summary>Machine-readable coverage record</summary>
        <pre>{JSON.stringify(coverage, null, 2)}</pre>
      </details>
    </section>
  );
}
