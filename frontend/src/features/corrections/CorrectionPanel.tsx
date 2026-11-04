import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import type { ApiClient, DossierView, FindingView } from '../../shared/api';
import { ApiError, parseDossier } from '../../shared/api';
import validateLocator from '../../shared/api/docx-locator-v1-generated-validator';
import { Button, Notice, UnsavedChanges } from '../../shared/ui';
import { useSession } from '../../shared/session';
import { CorrectionRecovery } from './CorrectionRecovery';
import { comparisonCounts, findingReasons } from './comparison';
import { boundedRedline } from './boundedRedline';

type Scope = { caseId: string; briefId: string; snapshot: string };
type Preview = {
  schema: string;
  committed: false;
  requires_recheck: true;
  original_sha256: string;
  derivative_sha256: string;
  derivative_byte_length: number;
  reference_id: string;
  paragraph_index: number;
  before: string;
  after: string;
  brief_version_id: string;
  snapshot_hash: string;
};
type Commit = {
  state: string;
  version_id: string;
  committed: true;
  requires_recheck: true;
};
const sha = /^[0-9a-f]{64}$/;
const uuid =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
function record(x: unknown): Record<string, unknown> {
  if (!x || typeof x !== 'object' || Array.isArray(x))
    throw Error('Invalid server response');
  return x as Record<string, unknown>;
}
function previewReceipt(
  x: unknown,
  expected: {
    snapshot_hash: string;
    original_sha256: string;
    reference_id: string;
    paragraph_index: number;
    before: string;
    after: string;
  },
  briefId: string,
): Preview {
  const r = record(x);
  if (
    r.schema !== 'caseproof-docx-correction-preview-v1' ||
    r.committed !== false ||
    r.requires_recheck !== true ||
    r.original_sha256 !== expected.original_sha256 ||
    r.reference_id !== expected.reference_id ||
    r.paragraph_index !== expected.paragraph_index ||
    r.before !== expected.before ||
    r.after !== expected.after ||
    r.brief_version_id !== briefId ||
    r.snapshot_hash !== expected.snapshot_hash ||
    typeof r.derivative_sha256 !== 'string' ||
    !sha.test(r.derivative_sha256) ||
    !Number.isSafeInteger(r.derivative_byte_length) ||
    (r.derivative_byte_length as number) < 1 ||
    (r.derivative_byte_length as number) > 5_242_880 ||
    'content_base64' in r
  )
    throw Error('Unverified correction preview');
  return r as Preview;
}
function commitReceipt(x: unknown): Commit {
  const r = record(x);
  if (
    r.state !== 'active' ||
    r.committed !== true ||
    r.requires_recheck !== true ||
    typeof r.version_id !== 'string' ||
    !uuid.test(r.version_id)
  )
    throw Error('Activation not confirmed');
  return r as Commit;
}
type DriftRow = {
  previous_reference_id: string | null;
  current_reference_id: string | null;
  status: 'unchanged' | 'changed' | 'uncertain' | 'added' | 'removed';
  reasons: string[];
  review_transfer: 'never';
};
type Drift = {
  schema: 'caseproof-finding-drift-v1';
  previous_brief_id: string;
  previous_snapshot_hash: string;
  current_brief_id: string;
  current_snapshot_hash: string;
  correspondence_basis: string;
  review_transfer: 'never';
  rows: DriftRow[];
};

function parseDrift(
  response: unknown,
  previous: DossierView,
  current: DossierView,
): Drift {
  const envelope = record(response);
  if (
    envelope.schema !== 'caseproof-finding-drift-v1' ||
    envelope.case_id !== previous.case_id ||
    envelope.previous_brief_id !== previous.brief_id ||
    envelope.previous_snapshot_hash !== previous.snapshot_hash ||
    envelope.current_brief_id !== current.brief_id ||
    envelope.current_snapshot_hash !== current.snapshot_hash ||
    envelope.review_transfer !== 'never' ||
    envelope.correspondence_basis !==
      'unique_region_and_start_offset_candidate_not_identity_proof' ||
    !Array.isArray(envelope.rows) ||
    envelope.rows.length > 20000
  )
    throw Error('Unbound reference correspondence');

  const oldIds = new Set(previous.findings.map((item) => item.reference_id));
  const newIds = new Set(current.findings.map((item) => item.reference_id));
  for (const entry of envelope.rows) {
    const row = record(entry);
    const before = row.previous_reference_id;
    const after = row.current_reference_id;
    if (
      row.review_transfer !== 'never' ||
      !['unchanged', 'changed', 'uncertain', 'added', 'removed'].includes(
        String(row.status),
      ) ||
      !(
        before === null ||
        (typeof before === 'string' && oldIds.has(before))
      ) ||
      !(after === null || (typeof after === 'string' && newIds.has(after))) ||
      (before === null && after === null) ||
      !Array.isArray(row.reasons) ||
      row.reasons.length > 20 ||
      !row.reasons.every(
        (reason: unknown) => typeof reason === 'string' && reason.length <= 120,
      )
    )
      throw Error('Unverified reference correspondence row');
  }
  return envelope as Drift;
}

/** A bounded correction command: never silently infer a DOCX paragraph index from a text excerpt. */
export function CorrectionPanel({
  api,
  scope,
  finding,
  originalSha,
}: {
  api: ApiClient;
  scope: Scope;
  finding: FindingView;
  originalSha: string;
}) {
  const navigate = useNavigate();
  const session = useSession();
  const before = finding.literal;
  const [after, setAfter] = useState('');
  const [preview, setPreview] = useState<Preview | null>(null);
  const [command, setCommand] = useState<Record<string, unknown> | null>(null);
  const [receipt, setReceipt] = useState<Commit | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [stale, setStale] = useState(false);
  const [unknown, setUnknown] = useState(false);
  const [resumeId, setResumeId] = useState<string | null>(null);
  const [recoveryReady, setRecoveryReady] = useState(false);
  const [drift, setDrift] = useState<Drift | null>(null);
  const [comparison, setComparison] = useState<{
    old: DossierView;
    current: DossierView;
  } | null>(null);
  const base = `/v2/matters/${encodeURIComponent(scope.caseId)}/briefs/${encodeURIComponent(scope.briefId)}/dossier`;
  const anchor = useQuery({
    queryKey: [
      'correction-anchor',
      session.epoch,
      scope.caseId,
      scope.briefId,
      scope.snapshot,
      finding.reference_id,
    ],
    queryFn: async ({ signal }) => {
      const result = record(
        await api.get(
          `${base}/snapshots/${encodeURIComponent(scope.snapshot)}/references/${encodeURIComponent(finding.reference_id)}/correction-anchor`,
          signal,
        ),
      );
      if (
        result.snapshot_hash !== scope.snapshot ||
        result.brief_version_id !== scope.briefId ||
        result.reference_id !== finding.reference_id ||
        result.original_sha256 !== originalSha ||
        result.before !== before ||
        !Number.isSafeInteger(result.paragraph_index) ||
        (result.paragraph_index as number) < 0 ||
        (result.paragraph_index as number) > 100000
      )
        throw Error('Unverified correction anchor');
      const identity = result.locator_identity;
      if (
        !validateLocator(identity) ||
        identity.source_version_id !== scope.briefId ||
        identity.exact_text !== before
      )
        throw Error('Unverified correction locator');
      return {
        paragraph_index: result.paragraph_index as number,
        locator_identity: identity,
      };
    },
    retry: false,
    enabled: session.connected,
  });
  const review = useQuery({
    queryKey: [
      'correction-review-receipt',
      session.epoch,
      scope.caseId,
      scope.briefId,
      scope.snapshot,
      finding.reference_id,
    ],
    queryFn: async ({ signal }) => {
      const result = record(
        await api.get(
          `${base}/corrections/review-receipt?snapshot_hash=${encodeURIComponent(scope.snapshot)}&reference_id=${encodeURIComponent(finding.reference_id)}`,
          signal,
        ),
      );
      if (
        result.schema !== 'caseproof-correction-review-receipt-v1' ||
        result.brief_version_id !== scope.briefId ||
        result.snapshot_hash !== scope.snapshot ||
        result.reference_id !== finding.reference_id ||
        typeof result.reviewer_id !== 'string' ||
        !uuid.test(result.reviewer_id) ||
        typeof result.review_request_id !== 'string' ||
        !uuid.test(result.review_request_id)
      )
        throw Error('Unverified persisted human review');
      return result;
    },
    retry: false,
    enabled: session.connected,
  });
  const reviewReady = review.isSuccess && Boolean(review.data);
  const valid =
    !stale &&
    sha.test(originalSha) &&
    sha.test(scope.snapshot) &&
    anchor.data !== undefined &&
    recoveryReady &&
    before.length > 0 &&
    before.length <= 4000 &&
    after.length <= 4000 &&
    !/[\t\r\n]/.test(after) &&
    before !== after;
  function invalidate() {
    setPreview(null);
    setCommand(null);
    setReceipt(null);
    setUnknown(false);
    setMessage('');
  }
  const payload = () => ({
    snapshot_hash: scope.snapshot,
    original_sha256: originalSha,
    reference_id: finding.reference_id,
    paragraph_index: anchor.data?.paragraph_index ?? -1,
    locator_identity: anchor.data?.locator_identity,
    before,
    after,
  });
  async function requestPreview() {
    if (!valid || busy) return;
    setBusy(true);
    invalidate();
    try {
      const result = previewReceipt(
        await api.post(`${base}/corrections/preview`, payload(), undefined, {
          snapshot: scope.snapshot,
        }),
        payload(),
        scope.briefId,
      );
      setPreview(result);
      setMessage('Read-only preview validated. No change was committed.');
    } catch (e) {
      if (e instanceof ApiError && (e.status === 409 || e.status === 412)) {
        setStale(true);
      } else {
        setMessage('Preview unavailable or unsupported. No commit allowed.');
      }
    } finally {
      setBusy(false);
    }
  }
  async function commit() {
    if (!preview || command || busy || !valid || !reviewReady) return;
    setBusy(true);
    setUnknown(false);
    try {
      // A fresh signed receipt is required even if the button was enabled.
      const proof = await review.refetch();
      if (!proof.isSuccess || !proof.data) {
        setMessage(
          'Human review receipt is not confirmed. No commit was sent.',
        );
        return;
      }
      const submitted = {
        ...payload(),
        request_id: resumeId ?? crypto.randomUUID(),
      };
      setCommand(submitted);
      const result = commitReceipt(
        await api.post(`${base}/corrections/commit`, submitted, undefined, {
          snapshot: scope.snapshot,
          idempotencyKey: submitted.request_id,
        }),
      );
      setReceipt(result);
      setMessage(
        'New draft activated. Recheck is required; previous approvals are not transferred.',
      );
    } catch (e) {
      if (e instanceof ApiError && e.status === 412) {
        setUnknown(true);
        setPreview(null);
        setStale(true);
        return;
      }
      if (e instanceof ApiError && e.status === 409) setCommand(null);
      setUnknown(!(e instanceof ApiError && e.status === 409));
      setMessage(
        e instanceof ApiError && e.status === 409
          ? 'The version or command conflicts. For recovery, enter the identical replacement text; otherwise reopen the current draft.'
          : 'Commit outcome unknown. Do not submit another correction. Reconcile with the authorized draft history.',
      );
    } finally {
      setBusy(false);
    }
  }
  async function reconcile() {
    if (!command || busy) return;
    setBusy(true);
    try {
      // Read-only durable lookup: never replay an uncertain consequential write.
      const status = record(
        await api.post(`${base}/corrections/status`, command),
      );
      if (status.state !== 'active') {
        setUnknown(true);
        setMessage(
          status.state === 'reserved'
            ? 'Correction reserved but activation is not confirmed. Contact the workspace administrator for recovery.'
            : 'No durable activation found. Do not create another correction until the outcome is investigated.',
        );
        return;
      }
      const result = commitReceipt(status);
      setReceipt(result);
      setUnknown(false);
      setMessage(
        'Exact correction reconciled against the durable activation receipt.',
      );
    } catch {
      setUnknown(true);
      setMessage(
        'Durable outcome still unresolved. Do not create another correction.',
      );
    } finally {
      setBusy(false);
    }
  }
  async function recheck() {
    if (!receipt || busy) return;
    setBusy(true);
    try {
      const current = parseDossier(
        await api.post(
          `/v2/matters/${encodeURIComponent(scope.caseId)}/briefs/${encodeURIComponent(receipt.version_id)}/dossier/recheck`,
          {},
        ),
      );
      if (
        current.case_id !== scope.caseId ||
        current.brief_id !== receipt.version_id ||
        !sha.test(current.snapshot_hash)
      )
        throw Error('Recheck binding mismatch');
      const historical = record(
        await api.get(`${base}/history/${encodeURIComponent(scope.snapshot)}`),
      );
      const old = parseDossier(historical.report);
      if (
        historical.mode !== 'historical_read_only' ||
        old.case_id !== scope.caseId ||
        old.brief_id !== scope.briefId ||
        old.snapshot_hash !== scope.snapshot
      )
        throw Error('Historical report binding mismatch');
      let explained: Drift | null = null;
      try {
        const payload = await api.get(
          `${base}/history/${encodeURIComponent(scope.snapshot)}/comparison?current_brief_id=${encodeURIComponent(current.brief_id)}&current_snapshot_hash=${encodeURIComponent(current.snapshot_hash)}`,
        );
        explained = parseDrift(payload, old, current);
      } catch {
        // Recheck remains valid; correspondence is explicitly unavailable.
        // Never fabricate a match or carry forward a human decision.
      }
      setDrift(explained);
      setComparison({ old, current });
      setMessage(
        explained
          ? 'Recheck completed. Reference drift remains a review aid, not approval.'
          : 'Recheck completed. Reference drift is unavailable; manually inspect both frozen reports.',
      );
    } catch {
      setMessage(
        'Recheck could not be confirmed. Reopen the activated draft from authorized history.',
      );
    } finally {
      setBusy(false);
    }
  }
  const redline = preview ? boundedRedline(before, after) : null;
  return (
    <section
      className="draft-context"
      aria-label="Correction preview and recheck"
      aria-busy={busy}
    >
      <UnsavedChanges dirty={Boolean(preview && !command)} />
      <h3>Propose a bounded DOCX correction</h3>
      {stale && <p role="alert">Stale draft. Reopen the current report.</p>}
      <CorrectionRecovery
        api={api}
        scope={scope}
        referenceId={finding.reference_id}
        onResume={setResumeId}
        onReady={setRecoveryReady}
      />
      <Notice>
        Only the exact reference in a supported DOCX paragraph can be replaced.
        Replacement text inherits the formatting of the first affected run;
        surrounding text keeps its formatting. Tabs and line breaks are not
        supported in a replacement. Commit requires your own saved human
        decision in the current snapshot.
      </Notice>
      {!reviewReady && (
        <Notice error>
          Persisted signed human review for this reference and snapshot is
          required. Save your decision in Human review first.
        </Notice>
      )}
      <Button
        disabled={busy || review.isFetching}
        onClick={() => void review.refetch()}
      >
        Refresh saved human review receipt
      </Button>
      {anchor.isPending && (
        <p>Locating the reference in the preserved draft…</p>
      )}
      {anchor.isError && (
        <Notice error>
          The reference cannot be safely located for correction.
        </Notice>
      )}
      <fieldset disabled={busy || Boolean(command)}>
        <label>
          Exact original text
          <textarea value={before} readOnly />
        </label>
        <label>
          Replacement text
          <textarea
            maxLength={4000}
            value={after}
            onChange={(e) => {
              invalidate();
              setAfter(e.target.value);
            }}
          />
        </label>
      </fieldset>
      <Button
        disabled={!valid || busy || Boolean(command)}
        onClick={() => void requestPreview()}
      >
        Validate exact preview
      </Button>
      {preview && (
        <div aria-label="Before and after correction">
          <p>Proposed change (not committed)</p>
          <p>
            {redline?.prefix}
            <del>{redline?.removed}</del>
            <ins>{redline?.added}</ins>
            {redline?.suffix}
          </p>
          <p className="small">Original SHA-256: {preview.original_sha256}</p>
          <p className="small">
            Derivative SHA-256: {preview.derivative_sha256} ·{' '}
            {preview.derivative_byte_length} bytes
          </p>
          <Notice>
            Verified bounded text diff and derivative digest only. The full DOCX
            is never returned by the preview API.
          </Notice>
          <Button
            disabled={busy || Boolean(command) || !reviewReady}
            onClick={() => void commit()}
          >
            Explicitly commit and activate new draft
          </Button>
        </div>
      )}
      {unknown && (
        <>
          <Notice error>
            Unknown write outcome. Automatic retry is disabled. Reconcile only
            the identical request.
          </Notice>
          <Button disabled={busy} onClick={() => void reconcile()}>
            Reconcile identical operation
          </Button>
        </>
      )}
      {receipt && (
        <Button disabled={busy} onClick={() => void recheck()}>
          Recheck activated draft
        </Button>
      )}
      {comparison && (
        <section aria-label="Report comparison">
          <h3>Compare preserved reports</h3>
          <Notice>
            Each report is shown independently. A changed reference may have a
            new identity; review both lists and coverage.
          </Notice>
          <ComparisonSummary
            old={comparison.old}
            current={comparison.current}
          />
          {drift ? (
            <section aria-label="Exhibit reference drift">
              <h4>Reference drift explanations</h4>
              <Notice>
                Matches are positional candidates only. Renumbered, ambiguous
                and unsupported citations require renewed human inspection. No
                prior signed decision is carried forward.
              </Notice>
              <ul>
                {drift.rows.map((row, index) => (
                  <li
                    key={`${row.previous_reference_id ?? 'new'}-${row.current_reference_id ?? 'gone'}-${index}`}
                  >
                    <strong>{row.status}</strong> — previous{' '}
                    {row.previous_reference_id ?? 'none'}; rechecked{' '}
                    {row.current_reference_id ?? 'none'}.
                    {row.reasons.length > 0 && (
                      <span> Reasons: {row.reasons.join(', ')}.</span>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          ) : (
            <Notice>
              Reference drift comparison was not confirmed by the signed API.
              Previous review cannot be transferred to the new draft.
            </Notice>
          )}
          {(
            [
              ['Previous report', comparison.old],
              ['Rechecked report', comparison.current],
            ] as const
          ).map(([label, report]) => (
            <section key={report.snapshot_hash}>
              <h4>{label}</h4>
              <p>
                Draft: {report.brief_id} · Snapshot: {report.snapshot_hash}
              </p>
              <h5>Coverage</h5>
              <pre>{JSON.stringify(report.coverage, null, 2)}</pre>
              <h5>Findings</h5>
              {report.findings.map((item) => (
                <div key={item.reference_id}>
                  <p>
                    {item.literal} ({item.reference_id})
                  </p>
                  <p>
                    Identity: {item.identity} · Page: {item.page_mapping} ·
                    Fidelity: {item.fidelity} · Support: {item.support}
                  </p>
                  {findingReasons(item).length > 0 && (
                    <ul
                      aria-label={`Reasons for ${item.reference_id} in ${label}`}
                    >
                      {findingReasons(item).map(([name, reason]) => (
                        <li key={name}>
                          {name}: {reason}
                        </li>
                      ))}
                    </ul>
                  )}
                  <Button
                    onClick={() =>
                      navigate(
                        `/matters/${encodeURIComponent(scope.caseId)}/briefs/${encodeURIComponent(report.brief_id)}?snapshot=${encodeURIComponent(report.snapshot_hash)}&finding=${encodeURIComponent(item.reference_id)}`,
                      )
                    }
                  >
                    Open {item.reference_id} in {label.toLowerCase()}
                  </Button>
                </div>
              ))}
            </section>
          ))}
          <Button
            onClick={() =>
              navigate(
                `/matters/${encodeURIComponent(scope.caseId)}/briefs/${encodeURIComponent(comparison.current.brief_id)}?snapshot=${comparison.current.snapshot_hash}`,
              )
            }
          >
            Open rechecked report
          </Button>
        </section>
      )}
      <p role="status">
        {busy ? 'Waiting for an authorized server response…' : message}
      </p>
    </section>
  );
}

function ComparisonSummary({
  old,
  current,
}: {
  old: DossierView;
  current: DossierView;
}) {
  const previous = comparisonCounts(old);
  const rechecked = comparisonCounts(current);
  const rows: Array<[string, keyof typeof previous]> = [
    ['Detected references', 'references'],
    ['Identity resolved', 'identityResolved'],
    ['Physical page mapped', 'pageMapped'],
    ['Text exact match', 'exactText'],
    ['Text not assessed', 'fidelityUnassessed'],
    ['OCR unreliable', 'ocrUnreliable'],
    ['Representation conflict', 'representationConflict'],
    ['Support dimension not assessed', 'supportUnassessed'],
  ];
  return (
    <section aria-label="Comparison of check counts">
      <h4>Check counts by report</h4>
      <p>
        Counts describe each report separately. They do not match references or
        transfer review decisions.
      </p>
      <table>
        <thead>
          <tr>
            <th scope="col">Check</th>
            <th scope="col">Previous</th>
            <th scope="col">Rechecked</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, field]) => (
            <tr key={field}>
              <th scope="row">{label}</th>
              <td>{previous[field]}</td>
              <td>{rechecked[field]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
