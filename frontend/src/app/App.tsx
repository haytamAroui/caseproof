import { useEffect, useState } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import {
  BrowserRouter,
  Link,
  Route,
  Routes,
  useNavigate,
  useParams,
} from 'react-router';
import { MattersScreen } from '../features/matters';
import { ReportScreen } from '../features/verification';
import { ApiClient } from '../shared/api';
import {
  SessionContext,
  SessionController,
  useSession,
  useSessionController,
} from '../shared/session';
import type { SessionHost } from '../shared/session';
import { Button, Notice } from '../shared/ui';
import { createQueryClient } from './query';
declare global {
  interface Window {
    caseproofSession?: SessionHost;
  }
}
function OpenReport() {
  const navigate = useNavigate();
  const { caseId } = useParams();
  const [error, setError] = useState('');
  const [invalid, setInvalid] = useState<string[]>([]);
  return (
    <section className="open-report">
      <p className="eyebrow">Evidence workspace</p>
      <h1>Open a preserved report</h1>
      <p>
        Open an existing authorized snapshot. Report history is not connected
        yet; the brief version and frozen snapshot identifiers are required.
      </p>
      <Link to="/">Back to permitted matters</Link>
      <form
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          const data = new FormData(event.currentTarget);
          const values = ['matter', 'brief', 'snapshot'].map((k) =>
            String(data.get(k) ?? '').trim(),
          );
          if (!values.every(Boolean)) {
            setError('Enter all three report identifiers.');
            const missing = ['matter', 'brief', 'snapshot'].filter(
              (_, i) => !values[i],
            );
            setInvalid(missing);
            const input = event.currentTarget.elements.namedItem(
              missing[0] ?? 'matter',
            );
            if (input instanceof HTMLInputElement) input.focus();
            return;
          }
          navigate(
            `/matters/${encodeURIComponent(values[0]!)}/briefs/${encodeURIComponent(values[1]!)}?snapshot=${encodeURIComponent(values[2]!)}`,
          );
        }}
      >
        {['matter', 'brief', 'snapshot'].map((name) => (
          <label key={name}>
            {name === 'snapshot'
              ? 'Snapshot SHA-256'
              : `${name === 'matter' ? 'Matter' : 'Brief version'} ID`}
            <input
              name={name}
              defaultValue={name === 'matter' ? caseId : undefined}
              readOnly={name === 'matter' && Boolean(caseId)}
              autoComplete="off"
              spellCheck={false}
              aria-invalid={invalid.includes(name)}
              aria-describedby={error ? 'report-error' : undefined}
              onInput={() => {
                setError('');
                setInvalid([]);
              }}
            />
          </label>
        ))}
        {error && (
          <div id="report-error">
            <Notice error>{error}</Notice>
          </div>
        )}
        <Button type="submit">Open report</Button>
      </form>
    </section>
  );
}
function ScopedOpenReport() {
  const { caseId } = useParams();
  return <OpenReport key={caseId ?? 'manual'} />;
}
function Workspace({ api }: { api: ApiClient }) {
  const session = useSession();
  const controller = useSessionController();
  const navigate = useNavigate();
  useEffect(
    () =>
      controller.onClear(() => {
        if (session.connected) void navigate('/', { replace: true });
      }),
    [controller, navigate, session.connected],
  );
  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header className="app-header">
        <Link to="/" className="brand">
          CaseProof <span>Evidence workspace</span>
        </Link>
        {session.connected && (
          <Button onClick={() => controller.clear()}>End session</Button>
        )}
      </header>
      <main id="main" tabIndex={-1}>
        {session.connected ? (
          <Routes>
            <Route path="/" element={<MattersScreen api={api} />} />
            <Route path="/reports/open" element={<ScopedOpenReport />} />
            <Route path="/matters/:caseId" element={<ScopedOpenReport />} />
            <Route
              path="/matters/:caseId/briefs/:briefId"
              element={<ReportScreen api={api} />}
            />
            <Route
              path="*"
              element={
                <>
                  <h1>Page not found</h1>
                  <Link to="/">Open a report</Link>
                </>
              }
            />
          </Routes>
        ) : (
          <section className="open-report">
            <p className="eyebrow">Private evidence review</p>
            <h1>Connect your workspace session</h1>
            <p>
              A trusted host must supply your authenticated session. Connecting
              cannot grant matter access.
            </p>
            <Connect />
          </section>
        )}
      </main>
      <footer>Development foundation · Synthetic acceptance only</footer>
    </>
  );
}
function Connect() {
  const controller = useSessionController();
  const [message, setMessage] = useState('');
  return (
    <>
      <Button
        onClick={() => {
          if (!window.caseproofSession) {
            setMessage(
              'No session provider is configured. Open this workspace through the development host.',
            );
            return;
          }
          controller.connect(window.caseproofSession);
        }}
      >
        Connect session
      </Button>
      {message && <Notice>{message}</Notice>}
    </>
  );
}
export function App() {
  const [composition] = useState(() => {
    const session = new SessionController();
    const query = createQueryClient();
    session.onClear(() => {
      void query.cancelQueries();
      query.clear();
    });
    return { session, query, api: new ApiClient(session) };
  });
  useEffect(() => () => composition.session.clear(), [composition]);
  return (
    <SessionContext.Provider value={composition.session}>
      <QueryClientProvider client={composition.query}>
        <BrowserRouter basename="/workspace">
          <Workspace api={composition.api} />
        </BrowserRouter>
      </QueryClientProvider>
    </SessionContext.Provider>
  );
}
