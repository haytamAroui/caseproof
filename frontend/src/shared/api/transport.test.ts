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
