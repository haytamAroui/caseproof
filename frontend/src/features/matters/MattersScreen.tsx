import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router';
import { ApiClient, parseMatters } from '../../shared/api';
import { useLocale } from '../../shared/i18n';
import { useSession } from '../../shared/session';
import { Button, IconFolder, IconInbox, Notice } from '../../shared/ui';

export function MattersScreen({ api }: { api: ApiClient }) {
  const { t } = useLocale();
  const session = useSession();
  const [params, setParams] = useSearchParams();
  const [search, setSearch] = useState('');
  const query = useQuery({
    queryKey: ['matters', session.epoch],
    queryFn: async ({ signal }) =>
      parseMatters(await api.get('/v2/workspace/matters', signal)),
    enabled: session.connected,
  });
  const pageSize = 20;
  const allMatters = query.data?.matters ?? [];
  const needle = search.trim().toLowerCase();
  const matters = needle
    ? allMatters.filter(
        (m) =>
          m.case_id.toLowerCase().includes(needle) ||
          m.state.toLowerCase().includes(needle),
      )
    : allMatters;
  const rawPage = Number(params.get('page') ?? 0);
  const page =
    Number.isInteger(rawPage) && rawPage >= 0
      ? Math.min(rawPage, Math.max(0, Math.ceil(matters.length / pageSize) - 1))
      : 0;
  function move(next: number) {
    setParams({ page: String(next) });
  }
  return (
    <section className="matter-catalog" aria-labelledby="matters-heading">
      <header className="page-heading page-heading-review">
        <div className="page-heading-title-group">
          <h1 id="matters-heading">{t('mattersHeading')}</h1>
          <p className="eyebrow">{t('mattersEyebrow')}</p>
        </div>
        <div className="cockpit-review-links">
          <Link className="cockpit-action-link" to="/reports/open">
            {t('mattersOpenByIdLink')}
          </Link>
          <Button
            className="button-secondary button-compact"
            onClick={() => {
              void query.refetch();
            }}
            disabled={query.isFetching}
          >
            {query.isFetching
              ? t('mattersRefreshingBtn')
              : t('mattersRefreshBtn')}
          </Button>
          <Link className="button button-compact" to="/matters/new">
            {t('mattersCreateLink')}
          </Link>
        </div>
        <p>{t('mattersLead')}</p>
      </header>
      <Notice>
        This development catalog lists up to 100 matters. Matter access does not
        grant permission to review, correct or export. Each request is
        authorized separately. Select a matter to browse preserved reports.
        Source intake and inventory confirmation are available separately.
      </Notice>
      <div aria-busy={query.isFetching}>
        {query.isPending ? (
          <Notice>Loading permitted matters…</Notice>
        ) : query.isError ? (
          <Notice error>
            The matter catalog is unavailable. Refresh to try again. No cached
            matters are shown.
          </Notice>
        ) : allMatters.length === 0 ? (
          <div className="empty-state-card" role="status">
            <IconInbox size={22} />
            <p>
              No permitted matters were returned. Ask your workspace owner to
              check your matter access, or refresh after access is granted.
            </p>
          </div>
        ) : (
          <>
            <div className="matter-toolbar">
              <label className="matter-search-field">
                <span className="viewer-search-label">
                  {t('mattersSearchPlaceholder')}
                </span>
                <input
                  value={search}
                  placeholder={t('mattersSearchPlaceholder')}
                  onChange={(event) => {
                    setSearch(event.target.value);
                    setParams({ page: '0' }, { replace: true });
                  }}
                  autoComplete="off"
                  spellCheck={false}
                />
              </label>
              <p className="small" role="status">
                {matters.length === 0
                  ? '0'
                  : `${page * pageSize + 1}–${Math.min((page + 1) * pageSize, matters.length)}`}{' '}
                of {matters.length} returned matters
              </p>
            </div>
            <div className="matter-table-head" aria-hidden="true">
              <span>{t('mattersColMatter')}</span>
              <span>{t('mattersColRevision')}</span>
              <span>{t('mattersColState')}</span>
            </div>
            <ul className="matter-list matter-table-list">
              {matters
                .slice(page * pageSize, (page + 1) * pageSize)
                .map((matter) => (
                  <li key={matter.case_id}>
                    <Link
                      className="matter-table-row"
                      to={`/matters/${encodeURIComponent(matter.case_id)}`}
                    >
                      <span className="matter-cell-primary">
                        <IconFolder size={15} />
                        <span>
                          Matter <code>{matter.case_id}</code>
                        </span>
                      </span>
                      <span className="small">
                        Revision {matter.case_revision}
                      </span>
                      <span className="small matter-state-pill">
                        Recorded state: {matter.state}
                      </span>
                    </Link>
                  </li>
                ))}
            </ul>
            <nav aria-label="Matter pages" className="catalog-actions">
              <Button
                className="button-secondary button-compact"
                disabled={page === 0}
                onClick={() => move(page - 1)}
              >
                Previous matters
              </Button>
              <Button
                className="button-secondary button-compact"
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
