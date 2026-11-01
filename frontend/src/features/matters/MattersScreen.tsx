import { useQuery } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router';
import { ApiClient, parseMatters } from '../../shared/api';
import { useSession } from '../../shared/session';
import { Button, Notice } from '../../shared/ui';

export function MattersScreen({ api }: { api: ApiClient }) {
  const session = useSession();
  const [params, setParams] = useSearchParams();
  const query = useQuery({
    queryKey: ['matters', session.epoch],
    queryFn: async ({ signal }) =>
      parseMatters(await api.get('/v2/workspace/matters', signal)),
    enabled: session.connected,
  });
  const pageSize = 20;
  const matters = query.data?.matters ?? [];
  const rawPage = Number(params.get('page') ?? 0);
  const page =
    Number.isInteger(rawPage) && rawPage >= 0
      ? Math.min(rawPage, Math.max(0, Math.ceil(matters.length / pageSize) - 1))
      : 0;
  function move(next: number) {
    setParams({ page: String(next) });
  }
  return (
    <section aria-labelledby="matters-heading">
      <p className="eyebrow">Evidence workspace</p>
      <h1 id="matters-heading">Your permitted matters</h1>
      <p>Choose a matter returned for your current signed session.</p>
      <Notice>
        This development catalog lists up to 100 matters. Matter access does not
        grant permission to review, correct or export. Each request is
        authorized separately. Report history and new matter intake are not
        connected yet.
      </Notice>
      <div className="catalog-actions">
        <Button
          onClick={() => {
            void query.refetch();
          }}
          disabled={query.isFetching}
        >
          {query.isFetching ? 'Refreshing matters…' : 'Refresh matters'}
        </Button>
        <Link to="/reports/open">Open a report by its identifiers</Link>
      </div>
      <div className="matter-catalog" aria-busy={query.isFetching}>
        {query.isPending ? (
          <Notice>Loading permitted matters…</Notice>
        ) : query.isError ? (
          <Notice error>
            The matter catalog is unavailable. Refresh to try again. No cached
            matters are shown.
          </Notice>
        ) : matters.length === 0 ? (
          <Notice>
            No permitted matters were returned. Ask your workspace owner to
            check your matter access, or refresh after access is granted.
          </Notice>
        ) : (
          <>
            <p role="status">
              {page * pageSize + 1}–
              {Math.min((page + 1) * pageSize, matters.length)} of{' '}
              {matters.length} returned matters
            </p>
            <ul className="matter-list">
              {matters
                .slice(page * pageSize, (page + 1) * pageSize)
                .map((matter) => (
                  <li key={matter.case_id}>
                    <Link to={`/matters/${encodeURIComponent(matter.case_id)}`}>
                      <span>
                        Matter <code>{matter.case_id}</code>
                      </span>
                      <span className="small">
                        Revision {matter.case_revision} · Recorded state:{' '}
                        {matter.state}
                      </span>
                    </Link>
                  </li>
                ))}
            </ul>
            <nav aria-label="Matter pages" className="catalog-actions">
              <Button disabled={page === 0} onClick={() => move(page - 1)}>
                Previous matters
              </Button>
              <Button
                disabled={(page + 1) * pageSize >= matters.length}
                onClick={() => move(page + 1)}
              >
                Next matters
              </Button>
            </nav>
          </>
        )}
      </div>
    </section>
  );
}
