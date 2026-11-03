import { describe, expect, it, vi } from 'vitest';
import { SessionController } from '../../shared/session';
import { ApiClient } from '../../shared/api';
import {
  parseRelease,
  parseReleaseList,
  parseReleasePreview,
  parseReleaseStatus,
} from './api';
import type { ReleaseScope } from './api';

const id = '11111111-1111-4111-8111-111111111111';
const scope: ReleaseScope = {
  caseId: '22222222-2222-4222-8222-222222222222',
  briefId: '33333333-3333-4333-8333-333333333333',
  snapshot: 'a'.repeat(64),
};
const media = {
  json: 'application/json',
  markdown: 'text/markdown; charset=utf-8',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
} as const;
const artifact = (kind: keyof typeof media) => ({
  sha256: 'b'.repeat(64),
  byte_length: 17,
  media_type: media[kind],
});
const manifest = {
  schema: 'caseproof-reviewed-release-v1',
  release_id: id,
  case_id: scope.caseId,
  brief_id: scope.briefId,
  snapshot_hash: scope.snapshot,
  review_count: 1,
  finding_count: 1,
  coverage: { reference_recall_measured: false },
  sources: [
    { role: 'draft', version_id: scope.briefId, sha256: 'c'.repeat(64) },
  ],
  source_links: [
    {
      role: 'draft',
      version_id: scope.briefId,
      sha256: 'c'.repeat(64),
      original_path:
        '/v2/matters/' +
        scope.caseId +
        '/briefs/' +
        scope.briefId +
        '/dossier/history/' +
        scope.snapshot +
        '/sources/' +
        scope.briefId +
        '/original',
    },
  ],
  reference_links: [
    {
      reference_id: 'ref-one',
      source_version_id: scope.briefId,
      original_sha256: 'c'.repeat(64),
      pdf_page: 6,
      page_space: 'physical_pdf_page',
      viewer_path:
        '/matters/' +
        scope.caseId +
        '/briefs/' +
        scope.briefId +
        '?snapshot=' +
        scope.snapshot +
        '&finding=ref-one',
    },
  ],
  limitations: ['Not a legal certificate'],
  artifacts: {
    json: artifact('json'),
    markdown: artifact('markdown'),
    docx: artifact('docx'),
  },
  manifest_sha256: 'd'.repeat(64),
  server_receipt: 'e'.repeat(64),
};
const record = {
  state: 'released',
  release_id: id,
  brief_id: scope.briefId,
  snapshot_hash: scope.snapshot,
  manifest,
};

describe('F6 reviewed export contracts', () => {
  it('accepts only exact version-bound release manifest and supported formats', () => {
    expect(parseRelease(record, scope).manifest.review_count).toBe(1);
    expect(() =>
      parseRelease({ ...record, snapshot_hash: 'f'.repeat(64) }, scope),
    ).toThrow();
    expect(() =>
      parseRelease(
        {
          ...record,
          manifest: { ...manifest, review_count: 0 },
        },
        scope,
      ),
    ).toThrow();
    expect(() =>
      parseRelease(
        {
          ...record,
          manifest: {
            ...manifest,
            artifacts: {
              ...manifest.artifacts,
              docx: { ...artifact('docx'), byte_length: 6_000_000 },
            },
          },
        },
        scope,
      ),
    ).toThrow();
    expect(() =>
      parseRelease(
        {
          ...record,
          manifest: { ...manifest, sources: [] },
        },
        scope,
      ),
    ).toThrow();
  });
  it('rejects unsafe source links and incorrect physical page bindings', () => {
    expect(() =>
      parseRelease(
        {
          ...record,
          manifest: {
            ...manifest,
            source_links: [
              {
                ...manifest.source_links[0],
                original_path: 'https://foreign.invalid',
              },
            ],
          },
        },
        scope,
      ),
    ).toThrow();
    expect(() =>
      parseRelease(
        {
          ...record,
          manifest: {
            ...manifest,
            reference_links: [
              {
                ...manifest.reference_links[0],
                pdf_page: null,
                page_space: 'physical_pdf_page',
              },
            ],
          },
        },
        scope,
      ),
    ).toThrow();
  });
  it('keeps a historical release bound to its own snapshot', () => {
    const old = 'f'.repeat(64);
    const historical = {
      ...record,
      snapshot_hash: old,
      manifest: {
        ...manifest,
        snapshot_hash: old,
        source_links: manifest.source_links.map((link) => ({
          ...link,
          original_path: link.original_path.replace(scope.snapshot, old),
        })),
        reference_links: manifest.reference_links.map((link) => ({
          ...link,
          viewer_path: link.viewer_path.replace(scope.snapshot, old),
        })),
      },
    };
    expect(
      parseReleaseList({ releases: [historical] }, scope)[0]?.snapshot_hash,
    ).toBe(old);
    expect(() =>
      parseReleaseList({ releases: [{ ...historical, manifest }] }, scope),
    ).toThrow();
    expect(parseReleaseStatus({ state: 'absent' }, scope)).toBeNull();
  });
  it('requires current signed readiness and an explicit human review', () => {
    const preview = {
      schema: 'caseproof-release-preview-v1',
      case_id: scope.caseId,
      brief_id: scope.briefId,
      snapshot_hash: scope.snapshot,
      finding_count: 1,
      review_count: 0,
      release_ready: false,
      coverage: {},
      formats: ['json', 'markdown', 'docx'],
      limitations: ['Not certified'],
    };
    expect(parseReleasePreview(preview, scope).release_ready).toBe(false);
    expect(() =>
      parseReleasePreview({ ...preview, release_ready: true }, scope),
    ).toThrow();
    expect(() =>
      parseReleasePreview(
        { ...preview, formats: ['json', 'markdown', 'pdf'] },
        scope,
      ),
    ).toThrow();
  });
});

describe('F6 authenticated binary downloads', () => {
  function session() {
    const s = new SessionController();
    s.connect({ getBearer: async () => 'signed' });
    return s;
  }
  const path = `/v2/matters/${scope.caseId}/briefs/${scope.briefId}/dossier/releases/${id}/artifacts/docx`;
  const mime = media.docx;
  async function fixture() {
    const bytes = new TextEncoder().encode('frozen binary output');
    const digest = Array.from(
      new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)),
      (b) => b.toString(16).padStart(2, '0'),
    ).join('');
    return {
      bytes,
      digest,
      binding: {
        export: true as const,
        media: mime as typeof media.docx,
        sha256: digest,
        snapshot: scope.snapshot,
        length: bytes.length,
      },
    };
  }
  it('offers bytes only after checking digest, scope, MIME and declared length', async () => {
    const { bytes, digest, binding } = await fixture();
    const send = vi.fn<typeof fetch>(
      async () =>
        new Response(bytes, {
          headers: {
            'Content-Type': mime,
            'X-CaseProof-Snapshot': scope.snapshot,
            'X-CaseProof-Export-SHA256': digest,
            'X-CaseProof-Export-Size': String(bytes.length),
          },
        }),
    );
    const output = await new ApiClient(session(), send).artifact(
      path,
      binding,
      new AbortController().signal,
    );
    expect(Array.from(output)).toEqual(Array.from(bytes));
    expect(send.mock.calls[0]?.[1]).toMatchObject({
      cache: 'no-store',
      credentials: 'omit',
      redirect: 'error',
      method: 'GET',
    });
  });
  it('rejects modified bytes even if response headers claim the original digest', async () => {
    const { bytes, digest, binding } = await fixture();
    const altered = new Uint8Array(bytes);
    altered[0] = altered[0]! ^ 1;
    const send = vi.fn<typeof fetch>(
      async () =>
        new Response(altered, {
          headers: {
            'Content-Type': mime,
            'X-CaseProof-Snapshot': scope.snapshot,
            'X-CaseProof-Export-SHA256': digest,
            'X-CaseProof-Export-Size': String(bytes.length),
          },
        }),
    );
    await expect(
      new ApiClient(session(), send).artifact(
        path,
        binding,
        new AbortController().signal,
      ),
    ).rejects.toThrow();
  });
  it('does not sign out a valid report reader on an export-only grant denial', async () => {
    const s = session();
    const send = vi.fn<typeof fetch>(
      async () => new Response(null, { status: 403 }),
    );
    await expect(new ApiClient(s, send).get(path)).rejects.toThrow(
      'unavailable',
    );
    expect(s.getSnapshot().connected).toBe(true);
  });
  it('rejects external or malformed release destinations without disclosure', async () => {
    const { binding } = await fixture();
    const send = vi.fn<typeof fetch>();
    await expect(
      new ApiClient(session(), send).artifact(
        'https://outside.example/v2/matters/x',
        binding,
        new AbortController().signal,
      ),
    ).rejects.toThrow();
    expect(send).not.toHaveBeenCalled();
  });
});
