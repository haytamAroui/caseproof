import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { ApiClient } from '../../shared/api';
import { parseDraftExcerpt } from '../../shared/api/review';
import { useSession } from '../../shared/session';
import { useLocale } from '../../shared/i18n';
import { Notice } from '../../shared/ui';

export function DraftContext({
  api,
  caseId,
  briefId,
  snapshot,
  referenceId,
  literal,
  renderCorrection,
}: {
  api: ApiClient;
  caseId: string;
  briefId: string;
  snapshot: string;
  referenceId: string;
  literal: string;
  renderCorrection: (originalSha: string) => ReactNode;
}) {
  const session = useSession();
  const { t } = useLocale();
  const excerpt = useQuery({
    queryKey: [
      'draft-excerpt',
      session.epoch,
      caseId,
      briefId,
      snapshot,
      referenceId,
    ],
    queryFn: async ({ signal }) =>
      parseDraftExcerpt(
        await api.get(
          `/v2/matters/${encodeURIComponent(caseId)}/briefs/${encodeURIComponent(briefId)}/dossier/snapshots/${snapshot}/references/${encodeURIComponent(referenceId)}/draft-context`,
          signal,
        ),
        { caseId, briefId, snapshot, referenceId, literal },
      ),
    enabled: session.connected,
  });
  return (
    <section className="draft-context" aria-label="Read-only draft reference">
      <h3>{t('draftContextTitle')}</h3>
      <Notice>{t('draftContextNotice')}</Notice>
      {excerpt.isPending && <p>{t('draftContextLoading')}</p>}
      {excerpt.isError && <Notice error>{t('draftContextUnavailable')}</Notice>}
      {excerpt.data &&
        (!excerpt.data.available ? (
          <Notice>{t('draftAnchorUnsupported')}</Notice>
        ) : (
          <>
            <p className="small">
              Story region {excerpt.data.region}; original SHA-256{' '}
              {excerpt.data.original_sha256}
            </p>
            <p className="draft-quote">
              {Array.from(excerpt.data.excerpt)
                .slice(0, excerpt.data.selection_start)
                .join('')}
              <mark>
                {Array.from(excerpt.data.excerpt)
                  .slice(
                    excerpt.data.selection_start,
                    excerpt.data.selection_end,
                  )
                  .join('')}
              </mark>
              {Array.from(excerpt.data.excerpt)
                .slice(excerpt.data.selection_end)
                .join('')}
            </p>
            {renderCorrection(excerpt.data.original_sha256)}
          </>
        ))}
    </section>
  );
}
