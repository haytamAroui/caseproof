import { useQuery } from '@tanstack/react-query';
import { Link, useParams, useSearchParams } from 'react-router';
import { ApiClient, parseReports } from '../../shared/api';
import { useSession } from '../../shared/session';
import { Button, Notice } from '../../shared/ui';
export function ReportsScreen({ api }: { api: ApiClient }) {
  const { caseId = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const after = params.get('after');
  const session = useSession();
  const valid =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(
      caseId,
    ) &&
    (after === null || /^[0-9a-f]{64}$/.test(after));
  const query = useQuery({
    queryKey: ['reports', session.epoch, caseId, after],
    enabled: valid && session.connected,
    queryFn: async ({ signal }) =>
      parseReports(
        await api.get(
          `/v2/workspace/matters/${encodeURIComponent(caseId)}/reports${after ? `?after=${after}` : ''}`,
          signal,
        ),
        caseId,
        after,
      ),
  });
  return (
    <section>
      <Link to="/">Back to permitted matters</Link>
      <h1>Preserved reports</h1>
      <Notice>
        Reports are ordered by snapshot identifier, not by date. Each is a
        historical check; opening it rechecks current access and source
        bindings. No new check runs when you select a report.
      </Notice>
      {!valid ? (
        <Notice error>This matter link is invalid.</Notice>
      ) : query.isPending ? (
        <Notice>Loading preserved reports…</Notice>
      ) : query.isError ? (
        <>
          <Notice error>
            Reports are unavailable for this matter. No cached reports are
            shown.
          </Notice>
          <Button
            onClick={() => {
              void query.refetch();
            }}
            disabled={query.isFetching}
          >
            Refresh reports
          </Button>
        </>
      ) : query.data.reports.length === 0 ? (
        <Notice>
          No preserved reports were returned for this matter. Intake and running
          a new check are not available in this screen yet.
        </Notice>
      ) : (
        <>
          <ul className="matter-list">
            {query.data.reports.map((report) => (
              <li key={report.snapshot_hash}>
                <Link
                  to={`/matters/${caseId}/briefs/${report.brief_id}?snapshot=${report.snapshot_hash}`}
                >
                  <span>Open preserved report</span>
                  <span className="small">
                    Snapshot <code>{report.snapshot_hash}</code>
                  </span>
                  <span className="small">
                    Created:{' '}
                    {new Intl.DateTimeFormat('en-BE', {
                      dateStyle: 'medium',
                      timeStyle: 'short',
                      timeZone: 'Europe/Brussels',
                    }).format(new Date(report.created_at))}{' '}
                    (Europe/Brussels)
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          <nav className="catalog-actions" aria-label="Report pages">
            <Button disabled={after === null} onClick={() => setParams({})}>
              First reports
            </Button>
            <Button
              disabled={!query.data.next_cursor}
              onClick={() => {
                if (query.data.next_cursor)
                  setParams({ after: query.data.next_cursor });
              }}
            >
              Next reports
            </Button>
          </nav>
        </>
      )}
    </section>
  );
}
