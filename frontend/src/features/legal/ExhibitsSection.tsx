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
              ? `${q.data.inventory_complete ? t('exhibitsConfirmedComplete') : t('exhibitsConfirmedIncomplete')} (confirmation ${q.data.confirmation_id ?? 'n/a'}).`
              : t('exhibitsUnconfirmed')}{' '}
            {t('exhibitsDetectedLabel')} {q.data.coverage.detected};{' '}
            {t('exhibitsLocatedLabel')} {q.data.coverage.located}.
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
                            SHA-256{' '}
                            <code className="hash-chip">{r.entry.sha256}</code>
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
                        . {t('exhibitsContentNotCompared')}
                      </span>
                    )}
                    {r.status_cue_flag && (
                      <div className="status-cue-callout" role="note">
                        <div className="status-cue-head">
                          <span className="legal-badge" data-tone="warning">
                            <span aria-hidden="true">!</span>{' '}
                            <strong>{t('statusCueFlagTitle')}</strong>
                          </span>
                          <span className="small">
                            {t('statusCueFlagClaimVsSource')}{' '}
                            <code>{r.status_cue_flag.claim_cue}</code> →{' '}
                            <code>{r.status_cue_flag.passage_cue}</code>
                            {r.status_cue_flag.pdf_page
                              ? ` (PDF p.${r.status_cue_flag.pdf_page})`
                              : ''}
                          </span>
                        </div>
                        <p className="small">
                          <strong>{t('legalDraft')}:</strong>{' '}
                          {r.status_cue_flag.claim_excerpt}
                        </p>
                        <p className="small">
                          <strong>{t('sourceEvidenceHeading')}:</strong>{' '}
                          {r.status_cue_flag.source_excerpt}
                        </p>
                        <p className="small muted">
                          {t('statusCueFlagDisclaimer')}
                        </p>
                      </div>
                    )}
                    {r.reservation_cue_flag && (
                      <div className="status-cue-callout" role="note">
                        <div className="status-cue-head">
                          <span className="legal-badge" data-tone="warning">
                            <span aria-hidden="true">!</span>{' '}
                            <strong>{t('lexicalCueReservationTitle')}</strong>
                          </span>
                          <span className="small">
                            <code>
                              {r.reservation_cue_flag.reservation_cue}
                            </code>
                            {r.reservation_cue_flag.pdf_page
                              ? ` (PDF p.${r.reservation_cue_flag.pdf_page})`
                              : ''}
                          </span>
                        </div>
                        <p className="small">
                          <strong>{t('legalDraft')}:</strong>{' '}
                          {r.reservation_cue_flag.draft_quote}
                        </p>
                        <p className="small">
                          <strong>{t('sourceEvidenceHeading')}:</strong>{' '}
                          {r.reservation_cue_flag.source_excerpt}
                        </p>
                        <p className="small muted">
                          {t('lexicalCueStatusDisclaimer')}
                        </p>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
          {q.data.coverage.entries_not_detected_in_brief.length > 0 && (
            <p className="small">
              {t('exhibitsUncitedPrefix')}{' '}
              {q.data.coverage.entries_not_detected_in_brief.join(', ')}.{' '}
              {t('exhibitsUncitedDisclaimer')}
            </p>
          )}
        </>
      )}
    </>
  );
}
