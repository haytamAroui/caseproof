import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router';
import type { ApiClient } from '../../shared/api';
import {
  parseLegalPassage,
  parseLegalReferences,
} from '../../shared/api/legal';
import { useSession } from '../../shared/session';
import { Button, Notice } from '../../shared/ui';

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const LABEL: Record<string, string> = {
  PASS: 'Found in the stored text',
  FAIL: 'Does not match the stored text',
  UNVERIFIED: 'Not in the chosen corpus',
  UNDETERMINED: 'Cannot be decided',
};

export function LegalScreen({ api }: { api: ApiClient }) {
  const { caseId = '', briefId = '' } = useParams();
  const session = useSession();
  const [open, setOpen] = useState<string | null>(null);
  const valid = uuid.test(caseId) && uuid.test(briefId);
  const base = `/v2/matters/${encodeURIComponent(caseId)}/briefs/${encodeURIComponent(briefId)}/legal-references`;
  const refs = useQuery({
    queryKey: ['legal-references', session.epoch, caseId, briefId],
    enabled: valid && session.connected,
    queryFn: async ({ signal }) =>
      parseLegalReferences(await api.get(base, signal), { briefId }),
  });
  const snapshot = refs.data?.snapshot_hash ?? '';
  const passage = useQuery({
    queryKey: ['legal-passage', session.epoch, caseId, briefId, snapshot, open],
    enabled: valid && session.connected && open !== null && snapshot !== '',
    queryFn: async ({ signal }) =>
      parseLegalPassage(
        await api.get(
          `${base}/${encodeURIComponent(open ?? '')}/passage`,
          signal,
        ),
        { snapshot, referenceId: open ?? '' },
      ),
  });
  return (
    <section aria-labelledby="legal-title">
      <Link to={`/matters/${caseId}`}>Back to preserved reports</Link>
      <h1 id="legal-title">Cited legal articles</h1>
      {!valid ? (
        <Notice error>This link is invalid.</Notice>
      ) : refs.isPending ? (
        <Notice>Loading cited articles…</Notice>
      ) : refs.isError ? (
        <>
          <Notice error>
            Cited articles are unavailable. No cached result is shown.
          </Notice>
          <Button
            onClick={() => {
              void refs.refetch();
            }}
            disabled={refs.isFetching}
          >
            Reload
          </Button>
        </>
      ) : (
        <>
          <Notice>{refs.data.note}</Notice>
          <p>
            {refs.data.corpus === 'configured' ? (
              <>
                Chosen corpus: {refs.data.corpus_articles} articles, pack{' '}
                <code>{refs.data.corpus_pack_sha256}</code>. No applicability or
                currency claim is made about it.
              </>
            ) : (
              'No corpus is chosen for this matter. No article can be found, so nothing is marked as found.'
            )}
          </p>
          {refs.data.corpus_failures.length > 0 && (
            <Notice error>
              Corpus entries refused: {refs.data.corpus_failures.join(', ')}
            </Notice>
          )}
          <p>
            Detected: {refs.data.coverage.detected} (
            {(['PASS', 'FAIL', 'UNVERIFIED', 'UNDETERMINED'] as const)
              .map((s) => `${s} ${refs.data.coverage.by_status[s]}`)
              .join(', ')}
            ). Looked at: {refs.data.coverage.analysed}.
          </p>
          <p>
            Not looked at: {refs.data.coverage.not_analysed.join('; ')}. A
            citation the check does not detect is not a verified citation.
          </p>
          {refs.data.references.length === 0 ? (
            <Notice>No explicit article citation was detected.</Notice>
          ) : (
            <ul
              className="matter-list legal-list"
              aria-label="Detected citations"
            >
              {refs.data.references.map((r) => (
                <li key={r.reference_id}>
                  <strong>{LABEL[r.status]}</strong> <code>{r.status}</code>
                  <span className="small">
                    {r.act_code ?? 'unknown act'} art. {r.article ?? '?'}
                    {r.language ? ` (${r.language})` : ''}: {r.raw_text}
                  </span>
                  <span className="small">
                    Reason: <code>{r.reason}</code>. Claim support: not
                    assessed.
                  </span>
                  <Button
                    aria-expanded={open === r.reference_id}
                    onClick={() =>
                      setOpen(open === r.reference_id ? null : r.reference_id)
                    }
                  >
                    {open === r.reference_id ? 'Hide' : 'Compare'} with stored
                    article
                  </Button>
                  {open === r.reference_id && (
                    <div aria-live="polite">
                      {passage.isPending ? (
                        <Notice>Loading passage…</Notice>
                      ) : passage.isError ? (
                        <Notice error>
                          The stored article cannot be shown. The corpus may
                          have changed since this run; run the check again.
                        </Notice>
                      ) : (
                        <div className="legal-compare">
                          <div>
                            <h3>Your draft</h3>
                            <p>
                              {Array.from(passage.data.brief_excerpt)
                                .slice(0, passage.data.citation_span[0])
                                .join('')}
                              <mark>
                                {Array.from(passage.data.brief_excerpt)
                                  .slice(
                                    passage.data.citation_span[0],
                                    passage.data.citation_span[1],
                                  )
                                  .join('')}
                              </mark>
                              {Array.from(passage.data.brief_excerpt)
                                .slice(passage.data.citation_span[1])
                                .join('')}
                            </p>
                          </div>
                          <div>
                            <h3>Stored article text</h3>
                            <p>
                              {passage.data.article_text ??
                                'No stored article for this citation.'}
                            </p>
                            <p className="small">
                              Source: {passage.data.corpus_source_uri ?? 'n/a'};
                              version {passage.data.corpus_version ?? 'n/a'};
                              text SHA-256{' '}
                              <code>
                                {passage.data.corpus_text_sha256 ?? 'n/a'}
                              </code>
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
