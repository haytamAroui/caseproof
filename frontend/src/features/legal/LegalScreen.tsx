import { useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router';
import type { ApiClient } from '../../shared/api';
import {
  parseLegalPassage,
  parseLegalReferences,
  type LegalPassageView,
} from '../../shared/api/legal';
import { useSession } from '../../shared/session';
import { Button, Notice } from '../../shared/ui';
import { ExhibitsSection } from './ExhibitsSection';
import { PackDownload } from './PackDownload';
import { ReviewBox } from './ReviewBox';

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
                            <DraftExcerpt p={passage.data} />
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
                      <ReviewBox
                        api={api}
                        caseId={caseId}
                        briefId={briefId}
                        snapshot={snapshot}
                        observationId={`legal:${r.reference_id}`}
                      />
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
          {refs.data.corpus === 'configured' && (
            <PackDownload
              api={api}
              caseId={caseId}
              briefId={briefId}
              snapshot={refs.data.snapshot_hash}
            />
          )}
          <ExhibitsSection
            api={api}
            caseId={caseId}
            briefId={briefId}
            snapshot={refs.data.snapshot_hash}
          />
          <h2>Lawyer-defined rules on declared facts</h2>
          {refs.data.suitability.length === 0 ? (
            <Notice>
              No lawyer-defined rule was evaluated for this run. Nothing here is
              a legal conclusion.
            </Notice>
          ) : (
            <ul className="matter-list legal-list" aria-label="Rules">
              {refs.data.suitability.map((x) => (
                <li key={x.observation_id}>
                  <strong>{LABEL[x.status]}</strong> <code>{x.status}</code>
                  <span className="small">
                    Rule {x.rule_id} v{x.rule_version}: {x.reference}
                  </span>
                  <span className="small">
                    Reason: <code>{x.reason}</code>
                  </span>
                  {x.missing.length > 0 && (
                    <span className="small">
                      Missing inputs: {x.missing.join(', ')}
                    </span>
                  )}
                  <span className="small">
                    Facts used (declared by a person, never confirmed by the
                    system unless marked):{' '}
                    {x.facts
                      .map((f) => `${String(f[0])}=${String(f[1])}`)
                      .join('; ') || 'none'}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}

type Mark = { a: number; b: number; kind: 'checked' | 'cite' | 'other' };
function DraftExcerpt({ p }: { p: LegalPassageView }) {
  const chars = Array.from(p.brief_excerpt);
  const marks: Mark[] = [
    { a: p.citation_span[0] ?? 0, b: p.citation_span[1] ?? 0, kind: 'cite' },
  ];
  if (p.quote_span)
    marks.push({
      a: p.quote_span[0] ?? 0,
      b: p.quote_span[1] ?? 0,
      kind: 'checked',
    });
  for (const o of p.other_findings) {
    marks.push({ a: o.span[0] ?? 0, b: o.span[1] ?? 0, kind: 'other' });
    if (o.quote_span)
      marks.push({
        a: o.quote_span[0] ?? 0,
        b: o.quote_span[1] ?? 0,
        kind: 'other',
      });
  }
  marks.sort((x, y) => x.a - y.a);
  const overlap = marks.some((m, i) => i > 0 && m.a < (marks[i - 1]?.b ?? 0));
  const parts: ReactNode[] = [];
  let at = 0;
  if (!overlap)
    marks.forEach((m, i) => {
      parts.push(chars.slice(at, m.a).join(''));
      parts.push(
        <mark key={i} className={`legal-mark legal-mark-${m.kind}`}>
          {chars.slice(m.a, m.b).join('')}
        </mark>,
      );
      at = m.b;
    });
  parts.push(chars.slice(at).join(''));
  return (
    <>
      <p className="small">
        This row checked:{' '}
        {p.quote ? <q>{p.quote}</q> : 'no quotation (the citation only)'}
        {p.quote &&
          !p.quote_span &&
          ' (its exact position could not be located)'}
        . Solid highlight = what this row checked. Dashed = another citation or
        quotation in the same passage, checked separately in its own row
        {p.other_findings.length > 0 &&
          ` (${p.other_findings.map((o) => o.status).join(', ')})`}
        . {p.status} here does not cover the dashed parts.
      </p>
      <p>{overlap ? p.brief_excerpt : parts}</p>
    </>
  );
}
