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
export interface ReleaseManifest {
  schema: 'caseproof-reviewed-release-v1';
  release_id: string;
  case_id: string;
  brief_id: string;
  snapshot_hash: string;
  review_count: number;
  finding_count: number;
  coverage: Record<string, unknown>;
  sources: { role: string; version_id: string; sha256: string }[];
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
  formats: ExportFormat[];
  coverage: Record<string, unknown>;
  limitations: string[];
}
const digest = /^[0-9a-f]{64}$/;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const plain = (v: unknown): v is Record<string, unknown> =>
  Boolean(v) && typeof v === 'object' && !Array.isArray(v);
const number = (v: unknown): v is number => typeof v === 'number' && Number.isSafeInteger(v) && v >= 0;
const formats: ExportFormat[] = ['json', 'markdown', 'docx'];
const medias: Record<ExportFormat, string> = {
  json: 'application/json',
  markdown: 'text/markdown',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
};
const limits: Record<ExportFormat, number> = { json: 2_000_000, markdown: 2_000_000, docx: 5_242_880 };

export function exportsPath(scope: ReleaseScope): string {
  return `/v2/matters/${encodeURIComponent(scope.caseId)}/briefs/${encodeURIComponent(scope.briefId)}/dossier/releases`;
}
export function parseReleasePreview(raw: unknown, scope: ReleaseScope): ReleasePreview {
  if (!plain(raw) || raw.schema !== 'caseproof-release-preview-v1' ||
    raw.case_id !== scope.caseId || raw.brief_id !== scope.briefId ||
    raw.snapshot_hash !== scope.snapshot || !number(raw.finding_count) ||
    !number(raw.review_count) || typeof raw.release_ready !== 'boolean' ||
    raw.release_ready !== (raw.review_count > 0) ||
    !plain(raw.coverage) || !Array.isArray(raw.formats) ||
    raw.formats.length !== 3 || !formats.every((x) => raw.formats.includes(x)) ||
    !Array.isArray(raw.limitations) || !raw.limitations.every((v) => typeof v === 'string')) {
    throw new Error('Unrecognized export readiness response.');
  }
  return raw as unknown as ReleasePreview;
}
export function parseRelease(raw: unknown, scope: ReleaseScope): ReleaseRecord {
  if (!plain(raw) || raw.state !== 'released' ||
    typeof raw.release_id !== 'string' || !uuid.test(raw.release_id) ||
    raw.brief_id !== scope.briefId || raw.snapshot_hash !== scope.snapshot ||
    !plain(raw.manifest)) throw new Error('Unrecognized release record.');
  const manifest = raw.manifest;
  if (manifest.schema !== 'caseproof-reviewed-release-v1' ||
    manifest.release_id !== raw.release_id ||
    manifest.case_id !== scope.caseId || manifest.brief_id !== scope.briefId ||
    manifest.snapshot_hash !== scope.snapshot ||
    !number(manifest.review_count) || manifest.review_count < 1 ||
    !number(manifest.finding_count) || !plain(manifest.coverage) ||
    !digest.test(String(manifest.manifest_sha256)) ||
    !digest.test(String(manifest.server_receipt)) ||
    !Array.isArray(manifest.sources) || manifest.sources.length < 1 ||
    !manifest.sources.every((v: unknown) =>
      plain(v) && typeof v.role === 'string' && typeof v.version_id === 'string' &&
      typeof v.sha256 === 'string' && digest.test(v.sha256)) ||
    !Array.isArray(manifest.limitations) ||
    !manifest.limitations.every((v: unknown) => typeof v === 'string') ||
    !plain(manifest.artifacts) ||
    !formats.every((kind) => {
      const info = manifest.artifacts as Record<string, unknown>;
      const item = info[kind];
      return plain(item) && typeof item.sha256 === 'string' && digest.test(item.sha256) &&
        number(item.byte_length) && item.byte_length > 0 &&
        item.byte_length <= limits[kind] && item.media_type ===
        (kind === 'markdown' ? 'text/markdown; charset=utf-8' : medias[kind]);
    })
  ) throw new Error('Release manifest failed validation.');
  return raw as unknown as ReleaseRecord;
}
export function parseReleaseList(raw: unknown, scope: ReleaseScope): ReleaseRecord[] {
  if (!plain(raw) || !Array.isArray(raw.releases) || raw.releases.length > 50)
    throw new Error('Unrecognized export history.');
  return raw.releases.map((entry) => {
    if (!plain(entry) || typeof entry.snapshot_hash !== 'string' || !digest.test(entry.snapshot_hash))
      throw new Error('Invalid historical release identity.');
    return parseRelease(entry, { ...scope, snapshot: entry.snapshot_hash });
  });
}
export function parseReleaseStatus(raw: unknown, scope: ReleaseScope): ReleaseRecord | null {
  if (plain(raw) && raw.state === 'absent' && Object.keys(raw).length === 1) return null;
  return parseRelease(raw, scope);
}
export async function downloadArtifact(api: ApiClient, scope: ReleaseScope,
  release: ReleaseRecord, format: ExportFormat, signal: AbortSignal): Promise<Uint8Array> {
  const info = release.manifest.artifacts[format];
  return api.artifact(
    `${exportsPath(scope)}/${encodeURIComponent(release.release_id)}/artifacts/${format}`,
    { sha256: info.sha256, snapshot: release.snapshot_hash, length: info.byte_length,
      media: medias[format] as 'application/json' | 'text/markdown' |
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      export: true },
    signal,
  );
}
