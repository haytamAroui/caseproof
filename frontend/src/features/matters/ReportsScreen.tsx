import { useQuery } from '@tanstack/react-query';
import { Link, useParams, useSearchParams } from 'react-router';
import { ApiClient, parseReports } from '../../shared/api';
import { useLocale } from '../../shared/i18n';
import { useSession } from '../../shared/session';
import { Button, IconFileCheck, IconInbox, Notice } from '../../shared/ui';
export function ReportsScreen({ api }: { api: ApiClient }) {
  const { t } = useLocale();
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
    <section className="matter-catalog">
      <Link className="legal-back-link" to="/">
        {t('reportsBackLink')}
      </Link>
      <header className="page-heading page-heading-review">
        <div className="page-heading-title-group">
          <h1>{t('reportsHeading')}</h1>
        </div>
        <div className="cockpit-review-links">
          <Link
            className="cockpit-action-link"
            to={`/matters/${caseId}/sources`}
          >
            {t('reportsSourcesLink')}
          </Link>
        </div>
      </header>
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
            className="button-secondary button-compact"
            onClick={() => {
              void query.refetch();
            }}
            disabled={query.isFetching}
          >
            Refresh reports
          </Button>
        </>
      ) : query.data.reports.length === 0 ? (
        <div className="empty-state-card" role="status">
          <IconInbox size={22} />
          <p>
            No preserved reports were returned for this matter. Intake and
            running a new check are not available in this screen yet.
          </p>
        </div>
      ) : (
        <>
          <div
            className="matter-table-head reports-table-head"
            aria-hidden="true"
          >
            <span>{t('reportsColReport')}</span>
            <span>{t('reportsColDate')}</span>
            <span>{t('reportsColActions')}</span>
          </div>
          <ul className="matter-list matter-table-list">
            {query.data.reports.map((report) => (
              <li key={report.snapshot_hash} className="report-table-item">
                <Link
                  className="matter-table-row report-table-row"
                  to={`/matters/${caseId}/briefs/${report.brief_id}?snapshot=${report.snapshot_hash}`}
                >
                  <span className="matter-cell-primary">
                    <IconFileCheck size={15} />
                    <span>
                      <strong>{t('reportsOpenLabel')}</strong>{' '}
                      <code className="hash-chip" title={report.snapshot_hash}>
                        {report.snapshot_hash}
                      </code>
                    </span>
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
                <Link
                  className="cockpit-action-link report-row-export"
                  to={`/matters/${caseId}/exports?brief=${report.brief_id}&snapshot=${report.snapshot_hash}`}
                >
                  {t('reportsReviewedExportsLink')}
                </Link>
              </li>
            ))}
          </ul>
          <nav className="catalog-actions" aria-label="Report pages">
            <Button
              className="button-secondary button-compact"
              disabled={after === null}
              onClick={() => setParams({})}
            >
              First reports
            </Button>
            <Button
              className="button-secondary button-compact"
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
