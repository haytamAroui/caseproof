import { Link } from 'react-router';

const uuid =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const sha = /^[0-9a-f]{64}$/;

export function MatterJourney({
  pathname,
  search,
  hash,
}: {
  pathname: string;
  search: string;
  hash: string;
}) {
  const segments = pathname.split('/').filter(Boolean);
  if (segments[0] !== 'matters' || !uuid.test(segments[1] ?? '')) return null;
  const matter = segments[1]!;
  const briefFromPath = segments[2] === 'briefs' ? segments[3] : null;
  const query = new URLSearchParams(search);
  const brief = briefFromPath ?? query.get('brief');
  const snapshot = query.get('snapshot');
  const reportReady = uuid.test(brief ?? '') && sha.test(snapshot ?? '');
  const root = `/matters/${matter}`;
  const reportUrl = reportReady
    ? `${root}/briefs/${brief}?snapshot=${snapshot}`
    : null;
  const exportUrl = reportReady
    ? `${root}/exports?brief=${brief}&snapshot=${snapshot}`
    : null;
  const active =
    segments[2] === 'sources'
      ? 1
      : segments[2] === 'inventory'
        ? 2
        : segments[2] === 'briefs' && segments[4] === 'edit'
          ? 5
          : segments[2] === 'briefs'
            ? hash === '#coverage'
              ? 3
              : 4
            : segments[2] === 'exports'
              ? hash === '#release-history'
                ? 7
                : 6
              : 0;
  const steps = [
    { number: 1, label: 'Matter & intake', to: `${root}/sources` },
    { number: 2, label: 'Confirm inventory', to: `${root}/inventory` },
    {
      number: 3,
      label: 'Verification & coverage',
      to: reportUrl ? `${reportUrl}#coverage` : null,
    },
    {
      number: 4,
      label: 'Evidence review',
      to: reportUrl ? `${reportUrl}#inspection` : null,
    },
    {
      number: 5,
      label: 'Correction & recheck',
      to: reportUrl
        ? `${root}/briefs/${brief}/edit?snapshot=${snapshot}`
        : null,
    },
    { number: 6, label: 'Release & export', to: exportUrl },
    {
      number: 7,
      label: 'Historical reopening',
      to: exportUrl ? `${exportUrl}#release-history` : null,
    },
  ];
  return (
    <nav className="cockpit-journey" aria-label="Matter workflow">
      <p className="cockpit-journey-caption">
        Dossier workflow <span>Navigation does not establish completion</span>
      </p>
      <ol>
        {steps.map(({ number, label, to }) => (
          <li key={number}>
            {to ? (
              <Link
                to={to}
                aria-current={number === active ? 'step' : undefined}
              >
                <span className="cockpit-step-number">
                  {String(number).padStart(2, '0')}
                </span>
                <span>{label}</span>
              </Link>
            ) : (
              <span aria-disabled="true">
                <span className="cockpit-step-number">
                  {String(number).padStart(2, '0')}
                </span>
                <span>{label}</span>
              </span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
