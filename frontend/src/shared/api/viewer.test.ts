import { expect, it, vi } from 'vitest';
import { ApiClient } from './transport';
import { SessionController } from '../session';
it('requires actual PDF digest/length/snapshot and rejects forged bytes', async () => {
  const bytes = new TextEncoder().encode('%PDF-1.7 synthetic transport');
  const sha = Array.from(
    new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)),
    (b) => b.toString(16).padStart(2, '0'),
  ).join('');
  const snapshot = 'a'.repeat(64);
  const session = new SessionController();
  session.connect({ getBearer: async () => 'synthetic' });
  const send = vi.fn<typeof fetch>(
    async () =>
      new Response(bytes, {
        headers: {
          'Content-Type': 'application/pdf',
          'X-CaseProof-Snapshot': snapshot,
          'X-CaseProof-Original-SHA256': sha,
        },
      }),
  );
  const api = new ApiClient(session, send);
  expect(
    await api.pdf(
      '/v2/source',
      { sha256: sha, snapshot, length: bytes.length },
      new AbortController().signal,
    ),
  ).toEqual(bytes);
  await expect(
    api.pdf(
      '/v2/source',
      { sha256: 'b'.repeat(64), snapshot, length: bytes.length },
      new AbortController().signal,
    ),
  ).rejects.toThrow();
  await expect(
    api.pdf(
      '/v2/source',
      { sha256: sha, snapshot: 'b'.repeat(64), length: bytes.length },
      new AbortController().signal,
    ),
  ).rejects.toThrow();
  await expect(
    api.pdf(
      '/v2/source',
      { sha256: sha, snapshot, length: 20_000_001 },
      new AbortController().signal,
    ),
  ).rejects.toThrow();
  const altered = bytes.slice();
  altered[altered.length - 1] = 88;
  const forged = new ApiClient(
    session,
    async () =>
      new Response(altered, {
        headers: {
          'Content-Type': 'application/pdf',
          'X-CaseProof-Snapshot': snapshot,
          'X-CaseProof-Original-SHA256': sha,
        },
      }),
  );
  await expect(
    forged.pdf(
      '/v2/source',
      { sha256: sha, snapshot, length: bytes.length },
      new AbortController().signal,
    ),
  ).rejects.toThrow();
});

it('fences a late binary response after session end', async () => {
  const session = new SessionController();
  session.connect({ getBearer: async () => 'synthetic' });
  let finish!: (response: Response) => void;
  const send = vi.fn<typeof fetch>(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const pending = new ApiClient(session, send).pdf(
    '/v2/source',
    { sha256: 'a'.repeat(64), snapshot: 'b'.repeat(64), length: 5 },
    new AbortController().signal,
  );
  await vi.waitFor(() => expect(send).toHaveBeenCalledOnce());
  session.clear();
  finish(
    new Response('%PDF-', { headers: { 'Content-Type': 'application/pdf' } }),
  );
  await expect(pending).rejects.toThrow('Session ended');
  expect(send.mock.calls[0]?.[1]?.signal?.aborted).toBe(true);
});

it('rejects mapped-without-page and unmapped-with-page viewer contexts', async () => {
  const { parseViewer } = await import('./viewer');
  const scope = {
    caseId: 'case',
    briefId: 'brief',
    snapshot: 'a'.repeat(64),
    referenceId: 'ref',
  };
  const context = {
    schema: 'caseproof-viewer-v1',
    case_id: scope.caseId,
    brief_id: scope.briefId,
    snapshot_hash: scope.snapshot,
    reference_id: scope.referenceId,
    version_id: 'source',
    original_sha256: 'b'.repeat(64),
    byte_length: 5,
    page_mapping: 'mapped',
    pdf_page: 1,
    legacy_region_count: 0,
    geometry_policy: 'derived_pdf_text_only_legacy_raster_not_projected',
  };
  expect(parseViewer(context, scope).pdf_page).toBe(1);
  expect(() => parseViewer({ ...context, pdf_page: null }, scope)).toThrow();
  expect(() =>
    parseViewer({ ...context, page_mapping: 'unmapped' }, scope),
  ).toThrow();
  expect(
    parseViewer({ ...context, page_mapping: 'unmapped', pdf_page: null }, scope)
      .pdf_page,
  ).toBeNull();
});
