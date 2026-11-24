import { Link } from 'react-router';
import { useLocale } from '../shared/i18n';

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
  const { t } = useLocale();
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
    { number: 1, label: t('step1'), to: `${root}/sources` },
    { number: 2, label: t('step2'), to: `${root}/inventory` },
    {
      number: 3,
      label: t('step3'),
      to: reportUrl ? `${reportUrl}#coverage` : null,
    },
    {
      number: 4,
      label: t('step4'),
      to: reportUrl ? `${reportUrl}#inspection` : null,
    },
    {
      number: 5,
      label: t('step5'),
      to: reportUrl
        ? `${root}/briefs/${brief}/edit?snapshot=${snapshot}`
        : null,
    },
    { number: 6, label: t('step6'), to: exportUrl },
    {
      number: 7,
      label: t('step7'),
      to: exportUrl ? `${exportUrl}#release-history` : null,
    },
  ];
  return (
    <nav className="cockpit-journey" aria-label="Matter workflow">
      <p className="cockpit-journey-caption">
        {t('journeyCaption')} <span>{t('journeyNote')}</span>
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
