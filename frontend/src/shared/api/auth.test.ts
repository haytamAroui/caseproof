import { describe, expect, it, vi } from 'vitest';
import { AuthTransport } from './transport';
import { parseSession } from './session';
describe('same-origin sign-in transport', () => {
  it('uses an exact origin path, no cookies, no redirects and no retry', async () => {
    const send = vi.fn<typeof fetch>(async () =>
      Response.json({
        access_token: 'synthetic',
        expires_at: Math.floor(Date.now() / 1000) + 30,
      }),
    );
    const result = await new AuthTransport(send).login(
      'u@e.com',
      'private-fixture',
      new AbortController().signal,
    );
    expect(parseSession(result).access_token).toBe('synthetic');
    expect(send).toHaveBeenCalledOnce();
    expect(send.mock.calls[0]?.[0]).toBe('/v2/workspace/session');
    expect(send.mock.calls[0]?.[1]).toMatchObject({
      method: 'POST',
      credentials: 'omit',
      redirect: 'error',
      cache: 'no-store',
    });
  });
  it('does not expose raw malformed response content in an error', async () => {
    const send = vi.fn<typeof fetch>(
      async () =>
        new Response('private-fixture-not-json', {
          headers: { 'Content-Type': 'application/json' },
        }),
    );
    await expect(
      new AuthTransport(send).login(
        'u@e.com',
        'secret',
        new AbortController().signal,
      ),
    ).rejects.toThrow('Invalid sign-in response.');
  });
  it('rejects expired and unknown-field sessions', () => {
    expect(() => parseSession({ access_token: 'x', expires_at: 1 })).toThrow();
    expect(() =>
      parseSession({
        access_token: 'x',
        expires_at: 9999999999,
        refresh_token: 'must-not-arrive',
      }),
    ).toThrow();
  });
});
