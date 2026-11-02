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
  it('clears on revocation and does not retry', async () => {
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
