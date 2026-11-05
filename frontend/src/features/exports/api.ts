import type { ApiClient } from '../../shared/api';

export type ExportFormat = 'json' | 'markdown' | 'docx';
export interface ReleaseScope {
  caseId: string;
  briefId: string;
  snapshot: string;
}
export interface ArtifactInfo {
  sha256: string;
  byte_length: number;
  media_type: string;
}
export interface ReviewCompleteness {
  policy_version: 'caseproof-release-completeness-v1';
  total_findings: number;
  required_reviews: number;
  reviewed_findings: number;
  unreviewed_findings: number;
  unreviewed_reference_ids: string[];
  review_complete: boolean;
  can_release_complete: boolean;
  can_release_partial: boolean;
  text_coverage_complete: boolean;
  reference_recall_measured: boolean;
  reason_codes: string[];
}
export interface ReleaseScopePolicy extends ReviewCompleteness {
  release_type: 'complete_review' | 'partial_review';
  partial_acknowledged: boolean;
}
export interface ReleaseManifest {
  schema: 'caseproof-reviewed-release-v1';
  release_id: string;
  case_id: string;
  brief_id: string;
  snapshot_hash: string;
  review_count: number;
  finding_count: number;
  // Absent only on immutable releases issued before completeness policy v1.
  review_completeness?: ReleaseScopePolicy;
  coverage: Record<string, unknown>;
  sources: { role: string; version_id: string; sha256: string }[];
  source_links: {
    role: string;
    version_id: string;
    sha256: string;
    original_path: string;
  }[];
  reference_links: {
    reference_id: string;
    source_version_id: string;
    original_sha256: string;
    pdf_page: number | null;
    viewer_path: string;
    page_space: 'physical_pdf_page' | 'unmapped';
  }[];
  limitations: string[];
  artifacts: Record<ExportFormat, ArtifactInfo>;
  server_receipt: string;
  manifest_sha256: string;
}
export interface ReleaseRecord {
  state: 'released';
  release_id: string;
  brief_id: string;
  snapshot_hash: string;
  manifest: ReleaseManifest;
  created_at?: string;
}
export interface ReleasePreview {
  schema: 'caseproof-release-preview-v1';
  case_id: string;
  brief_id: string;
  snapshot_hash: string;
  finding_count: number;
  review_count: number;
  release_ready: boolean;
  can_release: boolean;
  review_completeness: ReviewCompleteness;
  formats: ExportFormat[];
  coverage: Record<string, unknown>;
  limitations: string[];
}
const digest = /^[0-9a-f]{64}$/;
const uuid =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const plain = (v: unknown): v is Record<string, unknown> =>
  Boolean(v) && typeof v === 'object' && !Array.isArray(v);
const number = (v: unknown): v is number =>
  typeof v === 'number' && Number.isSafeInteger(v) && v >= 0;
const formats: ExportFormat[] = ['json', 'markdown', 'docx'];
function validPolicy(raw: unknown): raw is ReviewCompleteness {
  if (!plain(raw)) return false;
  if (
    raw.policy_version !== 'caseproof-release-completeness-v1' ||
    !number(raw.total_findings) ||
    !number(raw.required_reviews) ||
    !number(raw.reviewed_findings) ||
    !number(raw.unreviewed_findings) ||
    raw.total_findings !== raw.required_reviews ||
    raw.reviewed_findings + raw.unreviewed_findings !== raw.total_findings ||
    typeof raw.review_complete !== 'boolean' ||
    raw.review_complete !==
      (raw.total_findings > 0 && raw.unreviewed_findings === 0) ||
    raw.can_release_complete !== raw.review_complete ||
    raw.can_release_partial !==
      (raw.reviewed_findings > 0 && !raw.review_complete) ||
    typeof raw.text_coverage_complete !== 'boolean' ||
    typeof raw.reference_recall_measured !== 'boolean' ||
    !Array.isArray(raw.unreviewed_reference_ids) ||
    raw.unreviewed_reference_ids.length !== raw.unreviewed_findings ||
    !raw.unreviewed_reference_ids.every(
      (ref: unknown) =>
        typeof ref === 'string' && ref.length > 0 && ref.length <= 256,
    ) ||
    new Set(raw.unreviewed_reference_ids).size !==
      raw.unreviewed_reference_ids.length ||
    !Array.isArray(raw.reason_codes) ||
    !raw.reason_codes.every((v: unknown) => typeof v === 'string')
  )
    return false;
  return true;
}
function validReleaseScope(raw: unknown): raw is ReleaseScopePolicy {
  if (!validPolicy(raw) || !plain(raw)) return false;
  return (
    (raw.release_type === 'complete_review' &&
      raw.review_complete === true &&
      raw.partial_acknowledged === false) ||
    (raw.release_type === 'partial_review' &&
      raw.can_release_partial === true &&
      raw.partial_acknowledged === true)
  );
}
const medias: Record<ExportFormat, string> = {
  json: 'application/json',
  markdown: 'text/markdown',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
};
const limits: Record<ExportFormat, number> = {
  json: 2_000_000,
  markdown: 2_000_000,
  docx: 5_242_880,
};

export function exportsPath(scope: ReleaseScope): string {
  return `/v2/matters/${encodeURIComponent(scope.caseId)}/briefs/${encodeURIComponent(scope.briefId)}/dossier/releases`;
}
export function parseReleasePreview(
  raw: unknown,
  scope: ReleaseScope,
): ReleasePreview {
  if (
    !plain(raw) ||
    raw.schema !== 'caseproof-release-preview-v1' ||
    raw.case_id !== scope.caseId ||
    raw.brief_id !== scope.briefId ||
    raw.snapshot_hash !== scope.snapshot ||
    !number(raw.finding_count) ||
    !number(raw.review_count) ||
    typeof raw.release_ready !== 'boolean' ||
    !validPolicy(raw.review_completeness) ||
    raw.review_count !== raw.review_completeness.reviewed_findings ||
    raw.finding_count !== raw.review_completeness.total_findings ||
    raw.release_ready !== raw.review_completeness.can_release_complete ||
    raw.can_release !==
      (raw.review_completeness.can_release_complete ||
        raw.review_completeness.can_release_partial) ||
    !plain(raw.coverage) ||
    !Array.isArray(raw.formats) ||
    raw.formats.length !== 3 ||
    !formats.every((x) => (raw.formats as unknown[]).includes(x)) ||
    !Array.isArray(raw.limitations) ||
    !raw.limitations.every((v) => typeof v === 'string')
  ) {
    throw new Error('Unrecognized export readiness response.');
  }
  return raw as unknown as ReleasePreview;
}
export function parseRelease(raw: unknown, scope: ReleaseScope): ReleaseRecord {
  if (
    !plain(raw) ||
    raw.state !== 'released' ||
    typeof raw.release_id !== 'string' ||
    !uuid.test(raw.release_id) ||
    raw.brief_id !== scope.briefId ||
    raw.snapshot_hash !== scope.snapshot ||
    !plain(raw.manifest)
  )
    throw new Error('Unrecognized release record.');
  const manifest = raw.manifest;
  if (
    manifest.schema !== 'caseproof-reviewed-release-v1' ||
    manifest.release_id !== raw.release_id ||
    manifest.case_id !== scope.caseId ||
    manifest.brief_id !== scope.briefId ||
    manifest.snapshot_hash !== scope.snapshot ||
    !number(manifest.review_count) ||
    manifest.review_count < 1 ||
    !number(manifest.finding_count) ||
    (manifest.review_completeness !== undefined &&
      (!validReleaseScope(manifest.review_completeness) ||
        manifest.review_count !==
          manifest.review_completeness.reviewed_findings ||
        manifest.finding_count !==
          manifest.review_completeness.total_findings)) ||
    !plain(manifest.coverage) ||
    !digest.test(String(manifest.manifest_sha256)) ||
    !digest.test(String(manifest.server_receipt)) ||
    !Array.isArray(manifest.sources) ||
    manifest.sources.length < 1 ||
    !manifest.sources.every(
      (v: unknown) =>
        plain(v) &&
        typeof v.role === 'string' &&
        typeof v.version_id === 'string' &&
        typeof v.sha256 === 'string' &&
        digest.test(v.sha256),
    ) ||
    !Array.isArray(manifest.limitations) ||
    !manifest.limitations.every((v: unknown) => typeof v === 'string') ||
    !plain(manifest.artifacts) ||
    !formats.every((kind) => {
      const info = manifest.artifacts as Record<string, unknown>;
      const item = info[kind];
      return (
        plain(item) &&
        typeof item.sha256 === 'string' &&
        digest.test(item.sha256) &&
        number(item.byte_length) &&
        item.byte_length > 0 &&
        item.byte_length <= limits[kind] &&
        item.media_type ===
          (kind === 'markdown' ? 'text/markdown; charset=utf-8' : medias[kind])
      );
    })
  )
    throw new Error('Release manifest failed validation.');
  const expectedSourcePath = (version: string) =>
    '/v2/matters/' +
    encodeURIComponent(scope.caseId) +
    '/briefs/' +
    encodeURIComponent(scope.briefId) +
    '/dossier/history/' +
    scope.snapshot +
    '/sources/' +
    encodeURIComponent(version) +
    '/original';
  if (
    !Array.isArray(manifest.source_links) ||
    manifest.source_links.length !== manifest.sources.length ||
    !manifest.source_links.every((link: unknown, i: number) => {
      if (!plain(link)) return false;
      const source = (manifest.sources as ReleaseManifest['sources'])[i];
      return (
        source !== undefined &&
        link.version_id === source.version_id &&
        link.role === source.role &&
        link.sha256 === source.sha256 &&
        link.original_path === expectedSourcePath(source.version_id)
      );
    }) ||
    !Array.isArray(manifest.reference_links) ||
    manifest.reference_links.length > 10_000 ||
    !manifest.reference_links.every((link: unknown) => {
      if (
        !plain(link) ||
        typeof link.reference_id !== 'string' ||
        !link.reference_id ||
        link.reference_id.length > 256
      )
        return false;
      const source = (manifest.sources as ReleaseManifest['sources']).find(
        (s) => s.version_id === link.source_version_id,
      );
      const page = link.pdf_page;
      return (
        source !== undefined &&
        link.original_sha256 === source.sha256 &&
        (page === null || (number(page) && page > 0 && page <= 10000)) &&
        link.page_space ===
          (page === null ? 'unmapped' : 'physical_pdf_page') &&
        link.viewer_path ===
          '/matters/' +
            encodeURIComponent(scope.caseId) +
            '/briefs/' +
            encodeURIComponent(scope.briefId) +
            '?snapshot=' +
            scope.snapshot +
            '&finding=' +
            encodeURIComponent(link.reference_id)
      );
    })
  )
    throw new Error(
      'Unrecognized source and physical-page navigation bindings.',
    );
  return raw as unknown as ReleaseRecord;
}
export function parseReleaseList(
  raw: unknown,
  scope: ReleaseScope,
): ReleaseRecord[] {
  if (!plain(raw) || !Array.isArray(raw.releases) || raw.releases.length > 50)
    throw new Error('Unrecognized export history.');
  return raw.releases.map((entry) => {
    if (
      !plain(entry) ||
      typeof entry.snapshot_hash !== 'string' ||
      !digest.test(entry.snapshot_hash)
    )
      throw new Error('Invalid historical release identity.');
    return parseRelease(entry, { ...scope, snapshot: entry.snapshot_hash });
  });
}
export function parseReleaseStatus(
  raw: unknown,
  scope: ReleaseScope,
): ReleaseRecord | null {
  if (plain(raw) && raw.state === 'absent' && Object.keys(raw).length === 1)
    return null;
  return parseRelease(raw, scope);
}
export async function downloadArtifact(
  api: ApiClient,
  scope: ReleaseScope,
  release: ReleaseRecord,
  format: ExportFormat,
  signal: AbortSignal,
): Promise<Uint8Array> {
  const info = release.manifest.artifacts[format];
  return api.artifact(
    `${exportsPath(scope)}/${encodeURIComponent(release.release_id)}/artifacts/${format}`,
    {
      sha256: info.sha256,
      snapshot: release.snapshot_hash,
      length: info.byte_length,
      media: medias[format] as
        | 'application/json'
        | 'text/markdown'
        | 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      export: true,
    },
    signal,
  );
}
