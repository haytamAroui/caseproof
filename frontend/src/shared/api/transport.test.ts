import { describe, it, expect, vi } from 'vitest';
import { SessionController } from '../session';
import { ApiClient } from './transport';
import { parseDossier } from './contracts';
const session = () => {
  const s = new SessionController();
  s.connect({ getBearer: async () => 'synthetic-only' });
  return s;
};
describe('API confidentiality and lifecycle', () => {
  it('rejects a late response after signout', async () => {
    const s = session();
    let finish!: (value: Response) => void;
    const send = vi.fn<typeof fetch>(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    const pending = new ApiClient(s, send).get('/v2/report');
    await vi.waitFor(() => expect(send).toHaveBeenCalledOnce());
    s.clear();
    finish(Response.json({ private: 'old' }));
    await expect(pending).rejects.toThrow('Session ended');
    expect(send.mock.calls[0]?.[1]?.signal?.aborted).toBe(true);
  });
  it('clears on an invalid bearer (401), and does not retry', async () => {
    const s = session();
    const cleanup = vi.fn();
    s.onClear(cleanup);
    const send = vi.fn<typeof fetch>(
      async () => new Response(null, { status: 401 }),
    );
    await expect(new ApiClient(s, send).get('/v2/report')).rejects.toThrow(
      'unavailable',
    );
    expect(send).toHaveBeenCalledOnce();
    expect(cleanup).toHaveBeenCalledOnce();
    expect(s.getSnapshot().connected).toBe(false);
  });
  it.each([403, 404])(
    'preserves a signed reader session on scoped denial %s',
    async (status) => {
      const s = session();
      const cleanup = vi.fn();
      s.onClear(cleanup);
      const send = vi.fn<typeof fetch>(
        async () => new Response(null, { status }),
      );
      const recoveryPath = [
        '/v2/matters/case/briefs/brief/dossier/snapshots/',
        'a'.repeat(64),
        '/references/ref-1/correction-operations',
      ].join('');
      await expect(new ApiClient(s, send).get(recoveryPath)).rejects.toThrow(
        'unavailable',
      );
      expect(send).toHaveBeenCalledOnce();
      expect(cleanup).not.toHaveBeenCalled();
      expect(s.getSnapshot().connected).toBe(true);
    },
  );
  it('clears a revoked matter (403) without retrying', async () => {
    const s = session();
    const cleanup = vi.fn();
    s.onClear(cleanup);
    const send = vi.fn<typeof fetch>(
      async () => new Response(null, { status: 403 }),
    );
    await expect(new ApiClient(s, send).get('/v2/report')).rejects.toThrow(
      'unavailable',
    );
    expect(send).toHaveBeenCalledOnce();
    expect(cleanup).toHaveBeenCalledOnce();
    expect(s.getSnapshot().connected).toBe(false);
  });
  it('rejects external destinations before requesting credentials', async () => {
    const getBearer = vi.fn(async () => 'secret');
    const s = new SessionController();
    s.connect({ getBearer });
    await expect(
      new ApiClient(s).get('https://outside.test/v2/report'),
    ).rejects.toThrow('same-origin');
    expect(getBearer).not.toHaveBeenCalled();
  });
  it('cancels oversized streams before accepting content', async () => {
    const s = session();
    const cancelled = vi.fn();
    const stream = new ReadableStream({
      start(c) {
        c.enqueue(new Uint8Array(2_000_001));
      },
      cancel: cancelled,
    });
    const send = vi.fn<typeof fetch>(
      async () =>
        new Response(stream, {
          headers: { 'Content-Type': 'application/json' },
        }),
    );
    await expect(new ApiClient(s, send).get('/v2/report')).rejects.toThrow();
    expect(cancelled).toHaveBeenCalledOnce();
  });
  it('uses no-store, no cookies, and rejects redirects', async () => {
    const s = session();
    const send = vi.fn<typeof fetch>(async () => Response.json({}));
    await new ApiClient(s, send).get('/v2/report');
    expect(send.mock.calls[0]?.[1]).toMatchObject({
      cache: 'no-store',
      credentials: 'omit',
      redirect: 'error',
    });
  });
  it('rejects a token resolved after session replacement', async () => {
    const s = new SessionController();
    let finish!: (s: string) => void;
    s.connect({
      getBearer: () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    });
    const send = vi.fn<typeof fetch>();
    const pending = new ApiClient(s, send).get('/v2/report');
    s.connect({ getBearer: async () => 'new' });
    finish('old');
    await expect(pending).rejects.toThrow('Session ended');
    expect(send).not.toHaveBeenCalled();
  });
});
describe('runtime contract', () => {
  const report = {
    schema: 'caseproof-dossier-v1',
    case_id: 'c',
    brief_id: 'b',
    snapshot_hash: 'a'.repeat(64),
    coverage: {},
    findings: [
      {
        reference_id: 'r',
        literal: 'Exhibit A',
        identity: 'not_assessed',
        page_mapping: 'unmapped',
        fidelity: 'not_assessed',
        support: 'not_assessed',
      },
    ],
  };
  it('keeps unsupported references unassessed', () =>
    expect(parseDossier(report).findings[0]?.identity).toBe('not_assessed'));
  it('fails closed for unknown state and duplicate reference identifiers', () => {
    expect(() =>
      parseDossier({
        ...report,
        findings: [{ ...report.findings[0], identity: 'verified' }],
      }),
    ).toThrow();
    expect(() =>
      parseDossier({
        ...report,
        findings: [...report.findings, ...report.findings],
      }),
    ).toThrow();
  });
});

it('consequential POST is sent once with the session fence and never automatically retried', async () => {
  const session = new SessionController();
  session.connect({ getBearer: async () => 'synthetic' });
  let calls = 0;
  const api = new ApiClient(session, async (_path, init) => {
    calls++;
    expect(init?.method).toBe('POST');
    expect(init?.credentials).toBe('omit');
    expect(JSON.parse(String(init?.body))).toEqual({ request_id: 'stable' });
    throw new Error('Lost acknowledgement');
  });
  await expect(
    api.post('/v2/workspace/intake/matters', { request_id: 'stable' }),
  ).rejects.toThrow('Lost acknowledgement');
  expect(calls).toBe(1);
});

describe('cancelled matter reads', () => {
  it.each([200, 401, 403, 404])(
    'discards a late HTTP %s after leaving a matter without ending the active session',
    async (status) => {
      const s = session();
      const abort = new AbortController();
      let finish!: (response: Response) => void;
      const send = vi.fn<typeof fetch>(
        () =>
          new Promise((resolve) => {
            finish = resolve;
          }),
      );
      const pending = new ApiClient(s, send).get('/v2/report', abort.signal);
      await vi.waitFor(() => expect(send).toHaveBeenCalledOnce());
      abort.abort();
      finish(Response.json({ private: 'previous matter' }, { status }));
      await expect(pending).rejects.toThrow();
      expect(s.getSnapshot().connected).toBe(true);
      expect(send).toHaveBeenCalledOnce();
    },
  );
  it('rejects a cancelled body stream even when the transport ignores abort', async () => {
    const s = session();
    const abort = new AbortController();
    let stream!: ReadableStreamDefaultController<Uint8Array>;
    const cancel = vi.fn();
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        stream = controller;
      },
      cancel,
    });
    const send = vi.fn<typeof fetch>(
      async () =>
        new Response(body, { headers: { 'Content-Type': 'application/json' } }),
    );
    const pending = new ApiClient(s, send).get('/v2/report', abort.signal);
    await vi.waitFor(() => expect(body.locked).toBe(true));
    abort.abort();
    stream.enqueue(new TextEncoder().encode('{"private":"old"}'));
    await expect(pending).rejects.toThrow();
    expect(cancel).toHaveBeenCalledOnce();
    expect(s.getSnapshot().connected).toBe(true);
  });
});

describe('signed DOCX candidate transport', () => {
  const snapshot = 'a'.repeat(64);
  const original = 'b'.repeat(64);
  const path = '/v2/matters/case/briefs/brief/dossier/editor/candidate';

  it('downloads only a SHA-bound, snapshot-bound binary candidate', async () => {
    const bytes = new TextEncoder().encode('PK safe derivative');
    const hash = Array.from(
      new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)),
      (b) => b.toString(16).padStart(2, '0'),
    ).join('');
    const send = vi.fn<typeof fetch>(
      async () =>
        new Response(new Blob([new Uint8Array(bytes)]), {
          headers: {
            'Content-Type':
              'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'X-CaseProof-Snapshot': snapshot,
            'X-CaseProof-Original-SHA256': original,
            'X-CaseProof-Edit-Candidate-SHA256': hash,
          },
        }),
    );
    const api = new ApiClient(session(), send);
    const command = { snapshot_hash: snapshot, original_sha256: original };
    const result = await api.editorCandidate(
      path,
      command,
      { sha256: hash, byte_length: bytes.length },
      new AbortController().signal,
    );
    expect(Array.from(result)).toEqual(Array.from(bytes));
    expect(send).toHaveBeenCalledOnce();
    expect(send.mock.calls[0]?.[1]).toMatchObject({
      method: 'POST',
      credentials: 'omit',
      cache: 'no-store',
      redirect: 'error',
      headers: {
        'If-Match': `snapshot_id:${snapshot}`,
      },
    });
  });

  it('rejects non-matching candidate digest, bytes, and external paths', async () => {
    const bytes = new TextEncoder().encode('PK untrusted bytes');
    const send = vi.fn<typeof fetch>(
      async () =>
        new Response(new Blob([new Uint8Array(bytes)]), {
          headers: {
            'Content-Type':
              'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'X-CaseProof-Snapshot': snapshot,
            'X-CaseProof-Original-SHA256': original,
            'X-CaseProof-Edit-Candidate-SHA256': 'c'.repeat(64),
          },
        }),
    );
    const api = new ApiClient(session(), send);
    const command = { snapshot_hash: snapshot, original_sha256: original };
    await expect(
      api.editorCandidate(
        path,
        command,
        { sha256: 'c'.repeat(64), byte_length: bytes.length },
        new AbortController().signal,
      ),
    ).rejects.toThrow();
    await expect(
      api.editorCandidate(
        '/v2/matters/case/briefs/brief/dossier/corrections/commit',
        command,
        { sha256: 'c'.repeat(64), byte_length: bytes.length },
        new AbortController().signal,
      ),
    ).rejects.toThrow();
    expect(send).toHaveBeenCalledOnce();
  });

  it.each([403, 404])(
    'does not sign out report readers on editor denial %s',
    async (status) => {
      const s = session();
      const clear = vi.fn();
      s.onClear(clear);
      const send = vi.fn<typeof fetch>(
        async () => new Response(null, { status }),
      );
      await expect(
        new ApiClient(s, send).get(
          `/v2/matters/case/briefs/brief/dossier/editor/blocks?snapshot_hash=${snapshot}`,
        ),
      ).rejects.toThrow();
      expect(clear).not.toHaveBeenCalled();
      expect(s.getSnapshot().connected).toBe(true);
    },
  );
});

describe('native Word binary upload security and signed session boundary', () => {
  const snapshot = 'a'.repeat(64);
  const original = 'b'.repeat(64);
  const root = '/v2/matters/case/briefs/brief/dossier/editor/native/';
  async function binding(bytes: Uint8Array) {
    const sha = Array.from(
      new Uint8Array(
        await crypto.subtle.digest('SHA-256', new Uint8Array(bytes)),
      ),
      (n) => n.toString(16).padStart(2, '0'),
    ).join('');
    return {
      snapshot_hash: snapshot,
      original_sha256: original,
      candidate_sha256: sha,
      byte_length: bytes.byteLength,
    };
  }
  it('uses bounded signed raw DOCX without cookies, query parameters or external egress', async () => {
    const bytes = new TextEncoder().encode('PK original and Word-edited text');
    const bound = await binding(bytes);
    const fetcher = vi.fn<typeof fetch>(async () =>
      Response.json({
        schema: 'caseproof-native-docx-preview-v1',
        candidate_sha256: bound.candidate_sha256,
      }),
    );
    const api = new ApiClient(session(), fetcher);
    const result = await api.nativeWordUpload(
      root + 'preview',
      bound,
      bytes,
      new AbortController().signal,
    );
    expect(result).toMatchObject({
      schema: 'caseproof-native-docx-preview-v1',
    });
    expect(fetcher).toHaveBeenCalledOnce();
    expect(fetcher.mock.calls[0]?.[0]).toBe(root + 'preview');
    const init = fetcher.mock.calls[0]?.[1];
    expect(init).toMatchObject({
      method: 'POST',
      cache: 'no-store',
      credentials: 'omit',
      redirect: 'error',
      referrerPolicy: 'no-referrer',
      headers: {
        Authorization: 'Bearer synthetic-only',
        'If-Match': `snapshot_id:${snapshot}`,
        'Content-Type':
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'X-CaseProof-Original-SHA256': original,
        'X-CaseProof-Candidate-SHA256': bound.candidate_sha256,
      },
    });
    expect(init?.body).toBeInstanceOf(Uint8Array);
  });
  it('refuses spoofed binary digests and off-domain destinations before sending', async () => {
    const bytes = new TextEncoder().encode('PK Word candidate');
    const bound = await binding(bytes);
    const send = vi.fn<typeof fetch>();
    const api = new ApiClient(session(), send);
    const abort = new AbortController();
    await expect(
      api.nativeWordUpload(
        root + 'preview',
        { ...bound, candidate_sha256: 'f'.repeat(64) },
        bytes,
        abort.signal,
      ),
    ).rejects.toThrow();
    await expect(
      api.nativeWordUpload(
        'https://attacker.invalid/v2/matters/case/briefs/brief/dossier/editor/native/preview',
        bound,
        bytes,
        abort.signal,
      ),
    ).rejects.toThrow();
    await expect(
      api.nativeWordUpload(root + 'commit', bound, bytes, abort.signal),
    ).rejects.toThrow();
    expect(send).not.toHaveBeenCalled();
  });
  it('reuses the exact commit request ID and does not sign out on scoped denial', async () => {
    const bytes = new TextEncoder().encode('PK candidate');
    const bound = await binding(bytes);
    const s = session();
    const clear = vi.fn();
    s.onClear(clear);
    const send = vi.fn<typeof fetch>(
      async () => new Response(null, { status: 403 }),
    );
    const requestId = '7a602888-fce9-48f0-8aa1-2ce30d81bc98';
    const reviewId = '5adf4a99-ac2a-44ee-8bce-00d417ef19fe';
    await expect(
      new ApiClient(s, send).nativeWordUpload(
        root + 'commit',
        bound,
        bytes,
        new AbortController().signal,
        { requestId, reviewId },
      ),
    ).rejects.toThrow();
    const h = send.mock.calls[0]?.[1]?.headers as Record<string, string>;
    expect(h['Idempotency-Key']).toBe(requestId);
    expect(h['X-CaseProof-Review-Request-ID']).toBe(reviewId);
    expect(clear).not.toHaveBeenCalled();
    expect(s.getSnapshot().connected).toBe(true);
  });
});
