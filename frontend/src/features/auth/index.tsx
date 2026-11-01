import { useEffect, useRef, useState } from 'react';
import { AuthTransport, parseSession } from '../../shared/api';
import { useSessionController } from '../../shared/session';
import { Button, Notice } from '../../shared/ui';

export function SignIn({
  onLogoutFailure,
}: {
  onLogoutFailure: (message: string) => void;
}) {
  const session = useSessionController();
  const request = useRef<AbortController | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [invalid, setInvalid] = useState<string[]>([]);
  const [visible, setVisible] = useState(false);
  useEffect(() => () => request.current?.abort(), []);
  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        if (busy) return;
        const form = event.currentTarget;
        const data = new FormData(form);
        const email = String(data.get('email') ?? '').trim();
        const password = String(data.get('password') ?? '');
        const missing = [
          ...(!email.includes('@') ? ['email'] : []),
          ...(!password ? ['password'] : []),
        ];
        if (missing.length) {
          setInvalid(missing);
          setError('Enter your email address and password.');
          const input = form.elements.namedItem(missing[0]!);
          if (input instanceof HTMLInputElement) input.focus();
          return;
        }
        const controller = new AbortController();
        request.current?.abort();
        request.current = controller;
        const epoch = session.getSnapshot().epoch;
        const transport = new AuthTransport();
        setBusy(true);
        setError('');
        setInvalid([]);
        void transport
          .login(email, password, controller.signal)
          .then(parseSession)
          .then((result) => {
            if (
              controller.signal.aborted ||
              session.getSnapshot().epoch !== epoch
            ) {
              void transport
                .logout(result.access_token)
                .catch(() =>
                  onLogoutFailure(
                    'Workspace cleared. Provider sign-out could not be confirmed.',
                  ),
                );
              return;
            }
            let token = result.access_token;
            const host = {
              expiresAt: result.expires_at * 1000,
              getBearer: async () => token,
              clear: () => {
                const ending = token;
                token = '';
                if (ending)
                  void transport
                    .logout(ending)
                    .catch(() =>
                      onLogoutFailure(
                        'Workspace cleared. Provider sign-out could not be confirmed.',
                      ),
                    );
              },
            };
            form.reset();
            session.connect(host);
          })
          .catch((reason: unknown) => {
            if (!controller.signal.aborted)
              setError(
                reason instanceof Error
                  ? reason.message
                  : 'Sign-in failed. Try again.',
              );
          })
          .finally(() => {
            if (!controller.signal.aborted) {
              setBusy(false);
              const input = form.elements.namedItem('password');
              if (input instanceof HTMLInputElement) input.value = '';
            }
          });
      }}
    >
      <label>
        Email address
        <input
          name="email"
          type="email"
          autoComplete="username"
          disabled={busy}
          aria-invalid={invalid.includes('email')}
          aria-describedby={error ? 'signin-error' : undefined}
        />
      </label>
      <label>
        Password
        <input
          name="password"
          type={visible ? 'text' : 'password'}
          autoComplete="current-password"
          disabled={busy}
          aria-invalid={invalid.includes('password')}
          aria-describedby={error ? 'signin-error' : undefined}
        />
      </label>
      <Button aria-pressed={visible} onClick={() => setVisible((v) => !v)}>
        {visible ? 'Hide password' : 'Show password'}
      </Button>
      {error && (
        <div id="signin-error">
          <Notice error>{error}</Notice>
        </div>
      )}
      <Button type="submit" disabled={busy} aria-busy={busy}>
        {busy ? 'Signing in…' : 'Sign in'}
      </Button>
      <p className="small">
        Sign in with an existing workspace account. Reloading requires a fresh
        sign-in. Session material is kept in memory only.
      </p>
    </form>
  );
}
