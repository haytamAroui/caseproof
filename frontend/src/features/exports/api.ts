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
export interface ReleasePolicy {
  version: 1;
  scope: 'blocked' | 'partial' | 'complete';
  can_release: boolean;
  total_findings: number;
  required_findings: number;
  reviewed_findings: number;
  unreviewed_findings: number;
  review_complete: boolean;
  reviewed_reference_ids: string[];
  unreviewed_reference_ids: string[];
  references_truncated: boolean;
  reason_codes: string[];
}
export interface ReleaseManifest {
  schema: 'caseproof-reviewed-release-v1';
  release_id: string;
  case_id: string;
  brief_id: string;
  snapshot_hash: string;
  review_count: number;
  finding_count: number;
  release_policy?: ReleasePolicy; // absent for immutable legacy v1 releases
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
  currentness: 'current';
  release_policy: ReleasePolicy;
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

function validPolicy(value: unknown, allowBlocked: boolean): value is ReleasePolicy {
  if (!plain(value)) return false;
  const p = value;
  if (
    p.version !== 1 ||
    !['blocked', 'partial', 'complete'].includes(String(p.scope)) ||
    typeof p.can_release !== 'boolean' ||
    !number(p.total_findings) ||
    !number(p.required_findings) ||
    !number(p.reviewed_findings) ||
    !number(p.unreviewed_findings) ||
    typeof p.review_complete !== 'boolean' ||
    typeof p.references_truncated !== 'boolean' ||
    !Array.isArray(p.reviewed_reference_ids) ||
    !Array.isArray(p.unreviewed_reference_ids) ||
    !Array.isArray(p.reason_codes) ||
    !p.reason_codes.every((r: unknown) => typeof r === 'string') ||
    ![p.reviewed_reference_ids, p.unreviewed_reference_ids].every(
      (values) =>
        values.length <= 128 &&
        values.every((ref: unknown) => typeof ref === 'string' && ref.length > 0 && ref.length <= 256) &&
        new Set(values).size === values.length,
    )
  ) return false;
  if (
    p.total_findings !== p.required_findings ||
    p.reviewed_findings + p.unreviewed_findings !== p.total_findings ||
    p.reviewed_reference_ids.length > p.reviewed_findings ||
    p.unreviewed_reference_ids.length > p.unreviewed_findings ||
    p.can_release !== (p.scope !== 'blocked') ||
    p.review_complete !== (p.scope === 'complete') ||
    (p.scope === 'complete' && (p.total_findings === 0 || p.unreviewed_findings !== 0)) ||
    (p.scope === 'partial' && (p.reviewed_findings === 0 || p.unreviewed_findings === 0)) ||
    (p.scope === 'blocked' && p.reviewed_findings !== 0) ||
    (!allowBlocked && p.scope === 'blocked')
  ) return false;
  return true;
}

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
    !validPolicy(raw.release_policy, true) ||
    raw.can_release !== raw.release_policy.can_release ||
    raw.release_ready !== raw.release_policy.can_release ||
    raw.release_policy.total_findings !== raw.finding_count ||
    raw.release_policy.reviewed_findings > raw.review_count ||
    raw.currentness !== 'current' ||
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
    (manifest.release_policy !== undefined && (
      !validPolicy(manifest.release_policy, false) ||
      manifest.release_policy.total_findings !== manifest.finding_count ||
      manifest.release_policy.reviewed_findings > manifest.review_count
    )) ||
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
