import { CorrectionPanel } from '../corrections/CorrectionPanel';
import type { FindingView } from '../../shared/api';
import { useQuery } from '@tanstack/react-query';
import type { ApiClient } from '../../shared/api';
import { parseDraftExcerpt } from '../../shared/api/review';
import { useSession } from '../../shared/session';
import { Notice } from '../../shared/ui';

export function DraftContext({
  api,
  caseId,
  briefId,
  snapshot,
  referenceId,
  finding,
}: {
  api: ApiClient;
  caseId: string;
  briefId: string;
  snapshot: string;
  referenceId: string;
  finding: FindingView;
}) {
  const session = useSession();
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
        { caseId, briefId, snapshot, referenceId },
      ),
    enabled: session.connected,
  });
  return (
    <section className="draft-context" aria-label="Read-only draft reference">
      <h3>Preserved DOCX reference context</h3>
      <Notice>
        Bounded extracted plain text, not Word pagination or a safe editable
        location. No document mutation is performed.
      </Notice>
      {excerpt.isPending && <p>Loading authorized draft context…</p>}
      {excerpt.isError && (
        <Notice error>
          Draft context unavailable; do not infer the reference anchor.
        </Notice>
      )}
      {excerpt.data &&
        (!excerpt.data.available ? (
          <Notice>
            Draft anchor unsupported or ambiguous. Do not guess the first
            matching paragraph.
          </Notice>
        ) : (
          <>
            <p className="small">
              Story region {excerpt.data.region}; original SHA-256{' '}
              {excerpt.data.original_sha256}
            </p>
            <p className="draft-quote">
              {excerpt.data.excerpt.slice(0, excerpt.data.selection_start)}
              <mark>
                {excerpt.data.excerpt.slice(
                  excerpt.data.selection_start,
                  excerpt.data.selection_end,
                )}
              </mark>
              {excerpt.data.excerpt.slice(excerpt.data.selection_end)}
            </p>
            <CorrectionPanel key={snapshot + referenceId} api={api}
              scope={{ caseId, briefId, snapshot }} finding={finding}
              originalSha={excerpt.data.original_sha256} />
          </>
        ))}
    </section>
  );
}
