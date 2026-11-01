import { useQuery } from '@tanstack/react-query';
import { useParams, useSearchParams } from 'react-router';
import type { ApiClient } from '../../shared/api';
import { useSession } from '../../shared/session';
import { Notice, StateValue } from '../../shared/ui';
import { readReport } from './api';
const uuid =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
export function ReportScreen({ api }: { api: ApiClient }) {
  const { caseId = '', briefId = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const snapshot = params.get('snapshot') ?? '';
  const session = useSession();
  const valid =
    uuid.test(caseId) && uuid.test(briefId) && /^[0-9a-f]{64}$/.test(snapshot);
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
  const report = query.data;
  const selected =
    report.findings.find((f) => f.reference_id === params.get('finding')) ??
    report.findings[0];
  return (
    <>
      <header className="page-heading">
        <p className="eyebrow">Preserved report</p>
        <h1>Review the evidence</h1>
        <p>
          Each result describes a separate check. Human judgment remains
          separate.
        </p>
      </header>
      <Notice>
        Read-only foundation · Page viewing and review actions are not connected
        yet.
      </Notice>
      <div className="review-layout">
        <section className="queue" aria-label="References">
          <h2>
            References <span>{report.findings.length}</span>
          </h2>
          {report.findings.length === 0 ? (
            <p>
              No explicit references were detected. Inspect processing coverage
              before drawing conclusions.
            </p>
          ) : (
            <ul>
              {report.findings.map((f) => (
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
              <div className="page-empty">
                <h3>Original page not loaded</h3>
                <p>
                  Page images and coordinate overlays require the viewer
                  acceptance spike.
                </p>
              </div>
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
