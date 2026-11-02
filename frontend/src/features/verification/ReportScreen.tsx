import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useParams, useSearchParams } from 'react-router';
import type { ApiClient, FindingView } from '../../shared/api';
import { useSession } from '../../shared/session';
import { Notice, StateValue } from '../../shared/ui';
import { readReport } from './api';
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
  renderSource?: (finding: FindingView, historical: boolean, onInspected: () => void) => ReactNode;
  renderDraft?: (finding: FindingView, historical: boolean) => ReactNode;
  renderReview?: (finding: FindingView, historical: boolean, inspected: boolean) => ReactNode;
}) {
  const { caseId = '', briefId = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const snapshot = params.get('snapshot') ?? '';
  const session = useSession();
  const valid =
    uuid.test(caseId) && uuid.test(briefId) && /^[0-9a-f]{64}$/.test(snapshot);
  const [filter, setFilter] = useState<'attention' | 'all'>('attention');
  const query = useQuery({
    queryKey: ['report', session.epoch, caseId, briefId, snapshot],
    queryFn: ({ signal }) =>
      readReport(api, { caseId, briefId, snapshot }, signal),
    enabled: valid && session.connected,
  });
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
  const needsAttention = (f: FindingView) => f.identity !== 'resolved' || f.page_mapping !== 'mapped' || f.fidelity !== 'exact_match' || f.support === 'not_assessed';
  const filtered = filter === 'attention' ? report.findings.filter(needsAttention) : report.findings;
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
  return (
    <>
      <header className="page-heading">
        <p className="eyebrow">
          {historical
            ? 'Historical report · read-only'
            : 'Current preserved report'}
        </p>
        <h1>Review the evidence</h1>
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
      <div className="review-layout">
        <section className="queue" aria-label="References">
          <h2>
            References <span>{report.findings.length}</span>
          </h2>
          <p role="status">{report.findings.filter(needsAttention).length} need attention out of {report.findings.length} detected references. Review coverage separately.</p>
          <div className="catalog-actions">
            <button className="button" aria-pressed={filter === 'attention'} onClick={() => { setFilter('attention'); movePage(0); }}>Needs attention</button>
            <button className="button" aria-pressed={filter === 'all'} onClick={() => { setFilter('all'); movePage(0); }}>Show all</button>
          </div>
          {report.findings.length === 0 ? (
            <p>
              No explicit references were detected. Inspect processing coverage
              before drawing conclusions.
            </p>
          ) : visible.length === 0 ? <p>No references in this filter. Choose Show all to inspect the full scope.</p> : (
            <ul>
              {visible.map((f) => (
                <li key={f.reference_id}>
                  <button
                    className="finding"
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
                    {f.literal}
                    <small>{f.identity.replaceAll('_', ' ')}</small>
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
        <section className="inspection" aria-labelledby="finding-title">
          {selected ? (
            <>
              <p className="eyebrow">Selected reference</p>
              <h2 id="finding-title">{selected.literal}</h2>
              <dl className="dimensions">
                <StateValue label="Identity" value={selected.identity} />
                <StateValue
                  label="Page mapping"
                  value={selected.page_mapping}
                />
                <StateValue label="Fidelity" value={selected.fidelity} />
                <StateValue label="Human support" value={selected.support} />
              </dl>
              <FindingInspection
                key={selected.reference_id}
                finding={selected}
                historical={historical}
                renderSource={renderSource}
                renderDraft={renderDraft}
                renderReview={renderReview}
              />
            </>
          ) : (
            <h2 id="finding-title">No reference selected</h2>
          )}
          <details>
            <summary>Processing coverage from this snapshot</summary>
            <pre>{JSON.stringify(report.coverage, null, 2)}</pre>
          </details>
          <p className="small">
            Snapshot <code>{report.snapshot_hash}</code>
          </p>
        </section>
      </div>
    </>
  );
}

function FindingInspection({
  finding, historical, renderSource, renderDraft, renderReview,
}: {
  finding: FindingView;
  historical: boolean;
  renderSource?: (finding: FindingView, historical: boolean, onInspected: () => void) => ReactNode;
  renderDraft?: (finding: FindingView, historical: boolean) => ReactNode;
  renderReview?: (finding: FindingView, historical: boolean, inspected: boolean) => ReactNode;
}) {
  const [inspected, setInspected] = useState(false);
  return (
    <>
      {renderDraft?.(finding, historical)}
      {renderSource ? renderSource(finding, historical, () => setInspected(true)) :
        <Notice error>Preserved source viewer unavailable. No human source inspection may be recorded.</Notice>}
      {renderReview?.(finding, historical, inspected)}
    </>
  );
}
