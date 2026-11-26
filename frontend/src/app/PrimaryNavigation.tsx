import { Link } from 'react-router';
import { useLocale } from '../shared/i18n';
import {
  IconDownload,
  IconFileCheck,
  IconFolder,
  IconScale,
} from '../shared/ui';

const uuid =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const sha = /^[0-9a-f]{64}$/;

/**
 * Storyteller's top navigation is intentionally linked to the existing
 * authenticated routes. Missing snapshot context cannot be guessed.
 */
export function PrimaryNavigation({
  pathname,
  search,
}: {
  pathname: string;
  search: string;
}) {
  const { t } = useLocale();
  const segments = pathname.split('/').filter(Boolean);
  const matter = segments[0] === 'matters' ? segments[1] : null;
  const query = new URLSearchParams(search);
  const brief = segments[2] === 'briefs' ? segments[3] : query.get('brief');
  const snapshot = query.get('snapshot');
  const reportReady =
    uuid.test(matter ?? '') &&
    uuid.test(brief ?? '') &&
    sha.test(snapshot ?? '');
  const reportUrl = reportReady
    ? `/matters/${matter}/briefs/${brief}?snapshot=${snapshot}`
    : null;
  const legalUrl =
    uuid.test(matter ?? '') && uuid.test(brief ?? '')
      ? `/matters/${matter}/briefs/${brief}/legal${snapshot && sha.test(snapshot) ? `?snapshot=${snapshot}` : ''}`
      : null;
  const exportUrl = reportReady
    ? `/matters/${matter}/exports?brief=${brief}&snapshot=${snapshot}`
    : null;
  const current =
    segments[2] === 'exports'
      ? 'export'
      : segments[2] === 'briefs' && segments[4] === 'legal'
        ? 'legal'
        : segments[2] === 'briefs'
          ? 'verification'
          : 'matter';
  return (
    <nav className="app-primary-nav" aria-label="Primary workspace">
      <Link to="/" aria-current={current === 'matter' ? 'page' : undefined}>
        <IconFolder size={15} />
        <span>{t('navMatter')}</span>
      </Link>
      <span className="app-primary-divider" aria-hidden="true">
        ·
      </span>
      {reportUrl ? (
        <Link
          to={reportUrl}
          aria-current={current === 'verification' ? 'page' : undefined}
        >
          <IconFileCheck size={15} />
          <span>{t('navVerification')}</span>
        </Link>
      ) : (
        <span className="app-primary-unavailable" aria-disabled="true">
          <IconFileCheck size={15} />
          <span>{t('navVerification')}</span>
        </span>
      )}
      <span className="app-primary-divider" aria-hidden="true">
        ·
      </span>
      {legalUrl ? (
        <Link
          to={legalUrl}
          aria-current={current === 'legal' ? 'page' : undefined}
        >
          <IconScale size={15} />
          <span>{t('navLegal')}</span>
        </Link>
      ) : (
        <span className="app-primary-unavailable" aria-disabled="true">
          <IconScale size={15} />
          <span>{t('navLegal')}</span>
        </span>
      )}
      <span className="app-primary-divider" aria-hidden="true">
        ·
      </span>
      {exportUrl ? (
        <Link
          to={exportUrl}
          aria-current={current === 'export' ? 'page' : undefined}
        >
          <IconDownload size={15} />
          <span>{t('navExport')}</span>
        </Link>
      ) : (
        <span className="app-primary-unavailable" aria-disabled="true">
          <IconDownload size={15} />
          <span>{t('navExport')}</span>
        </span>
      )}
    </nav>
  );
}
