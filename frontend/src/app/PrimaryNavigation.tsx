import { Link } from 'react-router';

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
  const exportUrl = reportReady
    ? `/matters/${matter}/exports?brief=${brief}&snapshot=${snapshot}`
    : null;
  const current =
    segments[2] === 'exports'
      ? 'export'
      : segments[2] === 'briefs'
        ? 'verification'
        : 'matter';
  return (
    <nav className="app-primary-nav" aria-label="Primary workspace">
      <Link to="/" aria-current={current === 'matter' ? 'page' : undefined}>
        Matter
      </Link>
      <span className="app-primary-divider" aria-hidden="true">
        ·
      </span>
      {reportUrl ? (
        <Link
          to={reportUrl}
          aria-current={current === 'verification' ? 'page' : undefined}
        >
          Verification
        </Link>
      ) : (
        <span className="app-primary-unavailable" aria-disabled="true">
          Verification
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
          Export
        </Link>
      ) : (
        <span className="app-primary-unavailable" aria-disabled="true">
          Export
        </span>
      )}
    </nav>
  );
}
