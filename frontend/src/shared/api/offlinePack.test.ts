import { expect, it, vi } from 'vitest';
import { ApiClient } from './transport';
import { SessionController } from '../session';

const path = '/v2/matters/m/briefs/b/offline-pack';
async function setup(
  headers: Record<string, string>,
  body: Uint8Array<ArrayBuffer>,
) {
  const sha = Array.from(
    new Uint8Array(await crypto.subtle.digest('SHA-256', body)),
    (b) => b.toString(16).padStart(2, '0'),
  ).join('');
  const snapshot = 'a'.repeat(64);
  const session = new SessionController();
  session.connect({ getBearer: async () => 'synthetic' });
  const send = vi.fn<typeof fetch>(
    async () =>
      new Response(body, {
        headers: {
          'Content-Type': 'application/zip',
          'X-CaseProof-Snapshot': snapshot,
          'X-CaseProof-Pack-SHA256': sha,
          'X-CaseProof-Pack-Size': String(body.length),
          ...headers,
        },
      }),
  );
  return { api: new ApiClient(session, send), sha, snapshot };
}
const zip = new TextEncoder().encode('PK synthetic pack bytes');
const signal = () => new AbortController().signal;

it('accepts only a pack whose bytes, size, snapshot and headers match the manifest', async () => {
  const { api, sha, snapshot } = await setup({}, zip);
  expect(
    await api.offlinePack(
      path,
      { sha256: sha, snapshot, length: zip.length },
      signal(),
    ),
  ).toEqual(zip);
  await expect(
    api.offlinePack(
      path,
      { sha256: 'b'.repeat(64), snapshot, length: zip.length },
      signal(),
    ),
  ).rejects.toThrow();
  await expect(
    api.offlinePack(
      path,
      { sha256: sha, snapshot: 'c'.repeat(64), length: zip.length },
      signal(),
    ),
  ).rejects.toThrow();
  await expect(
    api.offlinePack(
      path,
      { sha256: sha, snapshot, length: zip.length + 1 },
      signal(),
    ),
  ).rejects.toThrow();
});

it('rejects a pack whose bytes differ from the advertised digest, a wrong media type and a foreign path', async () => {
  const tampered = await setup({}, zip);
  const other = new TextEncoder().encode('PK synthetic pack bytez');
  const lied = await setup({ 'X-CaseProof-Pack-SHA256': tampered.sha }, other);
  await expect(
    lied.api.offlinePack(
      path,
      { sha256: tampered.sha, snapshot: lied.snapshot, length: other.length },
      signal(),
    ),
  ).rejects.toThrow();
  const { api, sha, snapshot } = await setup(
    { 'Content-Type': 'text/html' },
    zip,
  );
  await expect(
    api.offlinePack(
      path,
      { sha256: sha, snapshot, length: zip.length },
      signal(),
    ),
  ).rejects.toThrow();
  await expect(
    api.offlinePack(
      '/v2/matters/m/briefs/b/dossier',
      { sha256: sha, snapshot, length: zip.length },
      signal(),
    ),
  ).rejects.toThrow();
});
