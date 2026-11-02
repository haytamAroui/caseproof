import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { ApiClient, parseOrganizations, parseCreated } from '../../shared/api';
import { useSessionController } from '../../shared/session';
import { Button, Notice } from '../../shared/ui';
export function CreateMatter({ api }: { api: ApiClient }) {
  const session = useSessionController();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const operationId = params.get('operation');
  useEffect(() => {
    if (!operationId || !/^[0-9a-f-]{36}$/.test(operationId))
      setParams({ operation: crypto.randomUUID() }, { replace: true });
  }, [operationId, setParams]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [uncertain, setUncertain] = useState(false);
  const operation = useRef<{
    request: string;
    org: string;
    name: string;
  } | null>(null);
  const abort = useRef(new AbortController());
  const lock = useRef(false);
  useEffect(() => {
    const a = abort.current;
    return () => a.abort();
  }, []);
  const query = useQuery({
    queryKey: ['create-organizations'],
    queryFn: async ({ signal }) =>
      parseOrganizations(
        await api.get('/v2/workspace/intake/organizations', signal),
      ),
  });
  return (
    <section className="open-report">
      <Link to="/">Back to permitted matters</Link>
      <h1>Create a private matter</h1>
      <p>
        Choose an organization available to your signed account. Matter creation
        does not upload files or run verification.
      </p>
      {query.isPending ? (
        <Notice>Loading permitted organizations…</Notice>
      ) : query.isError ? (
        <>
          <Notice error>Organizations are unavailable.</Notice>
          <Button
            onClick={() => {
              void query.refetch();
            }}
          >
            Refresh organizations
          </Button>
        </>
      ) : !query.data.organizations.length ? (
        <Notice>
          No organization permits matter creation for this account.
        </Notice>
      ) : (
        <form
          noValidate
          onSubmit={async (event) => {
            event.preventDefault();
            if (lock.current) return;
            const form = event.currentTarget,
              data = new FormData(form);
            const org = String(data.get('org') ?? ''),
              name = String(data.get('name') ?? '').trim();
            if (!org || !name || name.length > 160) {
              setMessage(
                'Choose an organization and enter a matter title (up to 160 characters).',
              );
              (
                form.elements.namedItem(!org ? 'org' : 'name') as HTMLElement
              ).focus();
              return;
            }
            setUncertain(true);
            operation.current ??= {
              request: operationId ?? crypto.randomUUID(),
              org,
              name,
            };
            const op = operation.current;
            if (op.org !== org || op.name !== name) {
              setMessage(
                'The previous creation outcome is unknown. Restore its values and reconcile before creating another matter.',
              );
              return;
            }
            lock.current = true;
            setBusy(true);
            setMessage('Creating matter…');
            const epoch = session.getSnapshot().epoch;
            try {
              const result = parseCreated(
                await api.post(
                  '/v2/workspace/intake/matters',
                  { org_id: op.org, name: op.name, request_id: op.request },
                  abort.current.signal,
                ),
                op.request,
              );
              session.assert(epoch);
              await navigate(`/matters/${result.case_id}/sources`);
            } catch {
              if (
                !abort.current.signal.aborted &&
                session.getSnapshot().epoch === epoch
              )
                setMessage(
                  'Creation outcome unknown. Reconcile creation with the same title and organization; no automatic retry was made.',
                );
            } finally {
              lock.current = false;
              if (
                !abort.current.signal.aborted &&
                session.getSnapshot().epoch === epoch
              )
                setBusy(false);
            }
          }}
        >
          <label>
            Organization
            <select name="org" disabled={busy} defaultValue="">
              <option value="">Choose organization</option>
              {query.data.organizations.map((o) => (
                <option key={o.org_id} value={o.org_id}>
                  {o.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Matter title
            <input
              name="name"
              maxLength={160}
              disabled={busy}
              aria-describedby="create-status"
            />
          </label>
          <Button type="submit" disabled={busy}>
            {busy
              ? 'Creating matter…'
              : uncertain
                ? 'Reconcile creation'
                : 'Create matter'}
          </Button>
        </form>
      )}
      {message && (
        <div id="create-status">
          <Notice>{message}</Notice>
        </div>
      )}
    </section>
  );
}
