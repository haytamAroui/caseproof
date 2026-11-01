import { useEffect, useState } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Link, Route, Routes, useNavigate } from 'react-router';
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
  const [error, setError] = useState('');
  return (
    <section className="open-report">
      <p className="eyebrow">Evidence workspace</p>
      <h1>Open a preserved report</h1>
      <p>
        Open an existing authorized snapshot. New matter intake will follow in
        the next slice.
      </p>
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
            <input name={name} autoComplete="off" spellCheck={false} />
          </label>
        ))}
        {error && <Notice error>{error}</Notice>}
        <Button type="submit">Open report</Button>
      </form>
    </section>
  );
}
function Workspace({ api }: { api: ApiClient }) {
  const session = useSession();
  const controller = useSessionController();
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
            <Route path="/" element={<OpenReport />} />
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
