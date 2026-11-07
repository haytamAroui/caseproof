import { CorrectionPanel, CorrectionRecovery } from '../features/corrections';
import { ScopedDocxEditor } from '../features/docx-editor';
import { ExportsScreen } from '../features/exports';
import { useEffect, useState } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import {
  BrowserRouter,
  Link,
  Route,
  Routes,
  useNavigate,
  useLocation,
  useParams,
  useSearchParams,
} from 'react-router';
import { SignIn } from '../features/auth';
import {
  MattersScreen,
  ReportsScreen,
  CreateMatter,
} from '../features/matters';
import { IntakeScreen, InventoryScreen } from '../features/intake';
import { SourceViewer } from '../features/evidence';
import { ReportScreen } from '../features/verification';
import { DraftContext, ReviewPanel } from '../features/review';
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
import { MatterJourney } from './MatterJourney';
import { recoveryDestination } from './recovery';
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
        Open an existing snapshot by its identifiers. You can also select a
        permitted matter to browse its preserved reports. Access is checked
        again when a report opens.
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
function ReviewWorkspace({ api }: { api: ApiClient }) {
  const { caseId = '', briefId = '' } = useParams();
  const [params] = useSearchParams();
  const snapshot = params.get('snapshot') ?? '';
  return (
    <ReportScreen
      api={api}
      renderDraft={(finding, historical) =>
        historical ? (
          <CorrectionRecovery
            api={api}
            scope={{ caseId, briefId, snapshot }}
            referenceId={finding.reference_id}
          />
        ) : (
          <DraftContext
            api={api}
            caseId={caseId}
            briefId={briefId}
            snapshot={snapshot}
            referenceId={finding.reference_id}
            literal={finding.literal}
            renderCorrection={(originalSha) => (
              <CorrectionPanel
                key={`${caseId}:${briefId}:${snapshot}:${finding.reference_id}:${originalSha}`}
                api={api}
                scope={{ caseId, briefId, snapshot }}
                finding={finding}
                originalSha={originalSha}
              />
            )}
          />
        )
      }
      renderReview={(finding, historical, inspected, onNext) =>
        historical ? null : finding.visual_assessment === undefined ? (
          <Notice error>
            Visual review metadata is unavailable. Human disposition is disabled
            for this snapshot.
          </Notice>
        ) : (
          <ReviewPanel
            key={`${caseId}:${briefId}:${snapshot}:${finding.reference_id}`}
            api={api}
            scope={{ caseId, briefId, snapshot }}
            finding={finding}
            inspected={inspected}
            onNext={onNext}
          />
        )
      }
      renderSource={(finding, historical, onInspected) => (
        <SourceViewer
          key={`${caseId}:${briefId}:${snapshot}:${finding.reference_id}:${historical}`}
          api={api}
          scope={{
            caseId,
            briefId,
            snapshot,
            referenceId: finding.reference_id,
            historical,
          }}
          finding={finding}
          onInspected={onInspected}
        />
      )}
    />
  );
}
function Workspace({ api }: { api: ApiClient }) {
  const session = useSession();
  const controller = useSessionController();
  const navigate = useNavigate();
  const [logoutMessage, setLogoutMessage] = useState('');
  const location = useLocation();
  const [returnTo, setReturnTo] = useState<string | null>(null);
  useEffect(
    () =>
      controller.onClear(() => {
        if (session.connected) {
          setReturnTo(recoveryDestination(location.pathname, location.search));
          void navigate('/', { replace: true });
        }
      }),
    [
      controller,
      navigate,
      session.connected,
      location.pathname,
      location.search,
    ],
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
        {session.connected && (
          <MatterJourney
            pathname={location.pathname}
            search={location.search}
            hash={location.hash}
          />
        )}
        {session.connected && returnTo && (
          <section aria-label="Session recovery">
            <Notice>
              Your previous session ended. Private views were cleared. You can
              reopen the previous location with a fresh access check.
            </Notice>
            <Button
              onClick={() => {
                const target = returnTo;
                setReturnTo(null);
                void navigate(target);
              }}
            >
              Reopen previous location
            </Button>
            <Button onClick={() => setReturnTo(null)}>Dismiss recovery</Button>
          </section>
        )}
        {session.connected ? (
          <Routes>
            <Route path="/" element={<MattersScreen api={api} />} />
            <Route path="/matters/new" element={<CreateMatter api={api} />} />
            <Route
              path="/matters/:caseId/sources"
              element={<IntakeScreen api={api} />}
            />
            <Route
              path="/matters/:caseId/inventory"
              element={<InventoryScreen api={api} />}
            />
            <Route path="/reports/open" element={<ScopedOpenReport />} />
            <Route
              path="/matters/:caseId"
              element={<ReportsScreen api={api} />}
            />
            <Route
              path="/matters/:caseId/exports"
              element={<ExportsScreen api={api} />}
            />
            <Route
              path="/matters/:caseId/briefs/:briefId/edit"
              element={<ScopedDocxEditor api={api} />}
            />
            <Route
              path="/matters/:caseId/briefs/:briefId"
              element={<ReviewWorkspace api={api} />}
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
              Sign in to your workspace. Your account must have access to each
              matter.
            </p>
            <details>
              <summary>Processing and access limits</summary>
              <p>
                Development workspace for synthetic acceptance. A local
                interface does not establish where documents are processed.
                Processing location, retention, backups and confidential use
                require a separately approved deployment policy. Ending a
                session clears this workspace; downloaded files cannot be
                recalled.
              </p>
            </details>
            {returnTo && (
              <Notice>
                Session ended. Sign in again to choose whether to reopen your
                previous location. No form values or document bytes are
                restored.
              </Notice>
            )}
            {logoutMessage && <Notice>{logoutMessage}</Notice>}
            <SignIn onLogoutFailure={setLogoutMessage} />
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
