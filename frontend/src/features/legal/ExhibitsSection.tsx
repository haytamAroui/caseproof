import { useQuery } from '@tanstack/react-query';
import type { ApiClient } from '../../shared/api';
import { parseExhibitReferences } from '../../shared/api/legal';
import { useLocale } from '../../shared/i18n';
import { useSession } from '../../shared/session';
import { Notice } from '../../shared/ui';

/** Exhibit mentions mapped to the inventory a person confirmed. Located never means content verified. */
export function ExhibitsSection(props: {
  api: ApiClient;
  caseId: string;
  briefId: string;
  snapshot: string;
}) {
  const { api, caseId, briefId, snapshot } = props;
  const session = useSession();
  const { t } = useLocale();
  const q = useQuery({
    queryKey: ['exhibit-references', session.epoch, caseId, briefId, snapshot],
    enabled: session.connected,
    retry: false,
    queryFn: async ({ signal }) =>
      parseExhibitReferences(
        await api.get(
          `/v2/matters/${encodeURIComponent(caseId)}/briefs/${encodeURIComponent(briefId)}/exhibit-references`,
          signal,
        ),
        { briefId, snapshot },
      ),
  });
  return (
    <>
      <h2>{t('exhibitsHeading')}</h2>
      {q.isPending ? (
        <Notice>{t('exhibitsLoading')}</Notice>
      ) : q.isError ? (
        <Notice error>{t('exhibitsError')}</Notice>
      ) : (
        <>
          <Notice>{q.data.note}</Notice>
          <p>
            {q.data.inventory_confirmed
              ? `Inventory confirmed${q.data.inventory_complete ? ' and declared complete' : ', not declared complete'} (confirmation ${q.data.confirmation_id ?? 'n/a'}).`
              : 'No confirmed inventory for this draft. Nothing is mapped to a file.'}{' '}
            Detected: {q.data.coverage.detected}; located in the inventory:{' '}
            {q.data.coverage.located}.
          </p>
          {q.data.references.length === 0 ? (
            <Notice>{t('exhibitsNone')}</Notice>
          ) : (
            <ul
              className="matter-list legal-list"
              aria-label="Exhibit mentions"
            >
              {q.data.references.map((r) => {
                const tone =
                  r.status === 'UNVERIFIED' ? 'impossible' : 'warning';
                const word =
                  r.status === 'UNVERIFIED'
                    ? t('exhibitNotInInventory')
                    : t('exhibitUndetermined');
                return (
                  <li
                    key={r.reference_id}
                    className="legal-card"
                    data-tone={tone}
                  >
                    <div className="legal-card-head">
                      <span className="legal-badge" data-tone={tone}>
                        <span aria-hidden="true">
                          {tone === 'impossible' ? '⊘' : '!'}
                        </span>{' '}
                        <strong>{word}</strong> <code>{r.status}</code>
                      </span>
                      <span className="legal-ref-title">
                        {r.raw_text}
                        {r.page_cited ? ' (a page is cited)' : ''}
                      </span>
                    </div>
                    <span className="small">
                      {t('legalReasonLabelPrefix')} <code>{r.reason}</code>
                    </span>
                    {r.entry && (
                      <span className="small">
                        Inventory entry {r.entry.label} {r.entry.number}:{' '}
                        {r.entry.filename ?? 'no source file bound'}
                        {r.entry.sha256 && (
                          <>
                            {' '}
                            SHA-256 <code>{r.entry.sha256}</code>
                          </>
                        )}
                        {r.entry.readback
                          ? `, readback ${r.entry.readback}`
                          : ''}
                        {r.entry.pages.length > 0 &&
                          `; confirmed pages: ${r.entry.pages
                            .map(
                              (p) =>
                                `${p.space} ${p.label} = PDF p.${p.pdf_page}`,
                            )
                            .join(', ')}`}
                        . Content not compared to the brief.
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
          {q.data.coverage.entries_not_detected_in_brief.length > 0 && (
            <p className="small">
              Inventory entries with no mention detected in the assessed text:{' '}
              {q.data.coverage.entries_not_detected_in_brief.join(', ')}. This
              is not a finding that they are uncited.
            </p>
          )}
        </>
      )}
    </>
  );
}
