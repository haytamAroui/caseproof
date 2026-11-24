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
import { useLocale } from '../../shared/i18n';
import { Button, Notice } from '../../shared/ui';
import { ReviewBox } from './ReviewBox';

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const STATUS_ORDER: Record<string, number> = {
  FAIL: 0,
  UNVERIFIED: 1,
  UNDETERMINED: 2,
  PASS: 3,
};
const STATUS_TONE: Record<string, string> = {
  FAIL: 'error',
  UNVERIFIED: 'impossible',
  UNDETERMINED: 'warning',
  PASS: 'success',
};
const STATUS_ICON: Record<string, string> = {
  FAIL: '✕',
  UNVERIFIED: '⊘',
  UNDETERMINED: '!',
  PASS: '✓',
};

export function LegalScreen({ api }: { api: ApiClient }) {
  const { caseId = '', briefId = '' } = useParams();
  const session = useSession();
  const { t, legalStatusLabel, categoryLabel } = useLocale();
  const [open, setOpen] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
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
      <Link to={`/matters/${caseId}`}>{t('legalBack')}</Link>
      <h1 id="legal-title">{t('legalTitle')}</h1>
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
                {t('legalCorpusPrefix')} {refs.data.corpus_articles}{' '}
                {t('legalCorpusArticles')}{' '}
                <code>{refs.data.corpus_pack_sha256}</code>.{' '}
                {t('legalCorpusDisclaimer')}
              </>
            ) : (
              t('legalNoCorpus')
            )}
          </p>
          {refs.data.corpus_failures.length > 0 && (
            <Notice error>
              Corpus entries refused: {refs.data.corpus_failures.join(', ')}
            </Notice>
          )}
          <div
            className="legal-kpi-strip"
            role="group"
            aria-label="Filter by status"
          >
            {(
              [
                ['ALL', t('legalAll'), refs.data.coverage.detected, 'neutral'],
                [
                  'FAIL',
                  categoryLabel('ecart'),
                  refs.data.coverage.by_status.FAIL,
                  'error',
                ],
                [
                  'UNVERIFIED',
                  categoryLabel('impossible'),
                  refs.data.coverage.by_status.UNVERIFIED,
                  'impossible',
                ],
                [
                  'UNDETERMINED',
                  categoryLabel('appreciation'),
                  refs.data.coverage.by_status.UNDETERMINED,
                  'warning',
                ],
                [
                  'PASS',
                  categoryLabel('correspondance'),
                  refs.data.coverage.by_status.PASS,
                  'success',
                ],
              ] as const
            ).map(([key, title, count, tone]) => (
              <button
                key={key}
                type="button"
                className="legal-kpi"
                data-tone={tone}
                aria-pressed={statusFilter === key}
                onClick={() => setStatusFilter(key)}
              >
                <span className="legal-kpi-count">{count}</span>
                <span className="legal-kpi-label">{title}</span>
              </button>
            ))}
          </div>
          <details className="legal-coverage-disclosure">
            <summary>
              {t('legalCoverage')} ({refs.data.coverage.detected} ·{' '}
              {refs.data.coverage.analysed})
            </summary>
            <p className="small">
              Detected: {refs.data.coverage.detected} (
              {(['PASS', 'FAIL', 'UNVERIFIED', 'UNDETERMINED'] as const)
                .map((s) => `${s} ${refs.data.coverage.by_status[s]}`)
                .join(', ')}
              ). Looked at: {refs.data.coverage.analysed}.
            </p>
            <p className="small">
              Not looked at: {refs.data.coverage.not_analysed.join('; ')}. A
              citation the check does not detect is not a verified citation.
            </p>
          </details>
          {refs.data.references.length === 0 ? (
            <Notice>No explicit article citation was detected.</Notice>
          ) : (
            <ul
              className="matter-list legal-list"
              aria-label="Detected citations"
            >
              {[...refs.data.references]
                .filter(
                  (r) => statusFilter === 'ALL' || r.status === statusFilter,
                )
                .sort(
                  (a, b) =>
                    (STATUS_ORDER[a.status] ?? 9) -
                    (STATUS_ORDER[b.status] ?? 9),
                )
                .map((r) => (
                  <li
                    key={r.reference_id}
                    className="legal-card"
                    data-tone={STATUS_TONE[r.status] ?? 'neutral'}
                  >
                    <div className="legal-card-head">
                      <span
                        className="legal-badge"
                        data-tone={STATUS_TONE[r.status] ?? 'neutral'}
                      >
                        <span aria-hidden="true">
                          {STATUS_ICON[r.status] ?? '·'}
                        </span>{' '}
                        <strong>{legalStatusLabel(r.status)}</strong>{' '}
                        <code>{r.status}</code>
                      </span>
                      <span className="legal-ref-title">
                        {r.act_code ?? 'unknown act'} art. {r.article ?? '?'}
                        {r.language ? ` (${r.language})` : ''}: {r.raw_text}
                      </span>
                    </div>
                    <span className="small">
                      {t('legalReasonLabelPrefix')} <code>{r.reason}</code>.{' '}
                      {t('legalClaimSupportUnassessed')}
                    </span>
                    <Button
                      aria-expanded={open === r.reference_id}
                      onClick={() =>
                        setOpen(open === r.reference_id ? null : r.reference_id)
                      }
                    >
                      {open === r.reference_id
                        ? t('legalHide')
                        : t('legalCompare')}
                    </Button>
                    {open === r.reference_id && (
                      <div aria-live="polite" className="legal-detail-panel">
                        {passage.isPending ? (
                          <Notice>Loading passage…</Notice>
                        ) : passage.isError ? (
                          <Notice error>
                            The stored article cannot be shown. The corpus may
                            have changed since this run; run the check again.
                          </Notice>
                        ) : (
                          <div className="legal-compare">
                            <div className="legal-compare-pane">
                              <h3>{t('legalDraft')}</h3>
                              <DraftExcerpt p={passage.data} />
                            </div>
                            <div className="legal-compare-pane">
                              <h3>{t('legalStored')}</h3>
                              <p className="legal-prose">
                                {passage.data.article_text ??
                                  t('legalNoArticleStored')}
                              </p>
                              <p className="small legal-provenance">
                                Source:{' '}
                                {passage.data.corpus_source_uri ?? 'n/a'};
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
          <h2>{t('legalRulesHeading')}</h2>
          {refs.data.suitability.length === 0 ? (
            <Notice>{t('legalNoRulesEvaluated')}</Notice>
          ) : (
            <ul className="matter-list legal-list" aria-label="Rules">
              {refs.data.suitability.map((x) => (
                <li key={x.observation_id}>
                  <strong>{legalStatusLabel(x.status)}</strong>{' '}
                  <code>{x.status}</code>
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
