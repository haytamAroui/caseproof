import { expect, it, vi } from 'vitest';
import { SessionController } from '../../shared/session';
import { ApiClient } from '../../shared/api';
import { readReport } from './api';

const scope = { caseId: 'case', briefId: 'brief', snapshot: 'a'.repeat(64) };
const report = { schema: 'caseproof-dossier-v1', case_id: scope.caseId,
  brief_id: scope.briefId, snapshot_hash: scope.snapshot, findings: [],
  coverage: {} };

function rig(respond: (path: string) => Response) {
  const session = new SessionController();
  session.connect({ getBearer: async () => 'synthetic' });
  const send = vi.fn<typeof fetch>(async (path) => respond(String(path)));
  return { api: new ApiClient(session, send), send };
}

it('stale current snapshot opens via distinct read-only history capability', async () => {
  const { api, send } = rig((path) =>
    path.includes('/history/')
      ? Response.json({ mode: 'historical_read_only', currentness: 'not_asserted',
          source_availability: 'not_assessed', report })
      : new Response(null, { status: 409 }));
  const opened = await readReport(api, scope, new AbortController().signal);
  expect(opened.mode).toBe('historical_read_only');
  expect(opened.report.snapshot_hash).toBe(scope.snapshot);
  expect(send).toHaveBeenCalledTimes(2);
  expect(String(send.mock.calls[1]?.[0])).toContain('/history/');
});

it('authorization failure and service outage cannot fall back to historical', async () => {
  for (const status of [401, 403, 404, 503]) {
    const { api, send } = rig(() => new Response(null, { status }));
    await expect(readReport(api, scope, new AbortController().signal)).rejects.toThrow();
    expect(send).toHaveBeenCalledTimes(1);
  }
});

it('historical wrapper must preserve scope and explicit noncurrent claims', async () => {
  const { api } = rig((path) => path.includes('/history/')
    ? Response.json({ mode: 'current', currentness: 'not_asserted',
        source_availability: 'not_assessed', report })
    : new Response(null, { status: 409 }));
  await expect(readReport(api, scope, new AbortController().signal)).rejects.toThrow();
});
