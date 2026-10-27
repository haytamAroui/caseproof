/*
 * Office dialog/PKCE integration adapted from Vaquill AI for Word
 * (Apache-2.0), src/auth/dialog-login.ts, commit 0740ec39ffd1e1e1ef54088a11d157cf35aa541b.
 * Copyright 2026 Vaquill AI; modifications by CaseProof contributors.
 * See THIRD_PARTY_NOTICES.md and third_party/Vaquill-LICENSE.txt.
 *
 * The caller supplies a configured Supabase client with PKCE and in-memory
 * storage, a trusted provider and origin; no credentials belong in this file.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.CaseProofOfficeAuth = factory();
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  function createOfficeAuth({ supabase, office, origin, authOrigin, provider = 'google', timeoutMs = 180000 }) {
    const expectedOrigin = new URL(origin).origin;
    const trustedAuthOrigin = new URL(authOrigin).origin;
    if (!expectedOrigin.startsWith('https://') || !trustedAuthOrigin.startsWith('https://')) {
      throw new Error('HTTPS origins are required.');
    }
    let session = null;
    let active = false;
    let revision = 0;
    let refreshing = null;
    async function login() {
      if (active) throw new Error('A sign-in is already in progress.');
      active = true;
      const operation = ++revision;
      try {
        const redirectTo = `${expectedOrigin}/auth-callback.html`;
        const started = await supabase.auth.signInWithOAuth({
          provider, options: { redirectTo, skipBrowserRedirect: true },
        });
        if (operation !== revision) throw new Error('Sign-in was cancelled.');
        if (started.error || !started.data?.url) throw new Error('Could not start sign-in.');
        const authorizationUrl = new URL(started.data.url);
        if (authorizationUrl.origin !== trustedAuthOrigin || authorizationUrl.protocol !== 'https:') {
          throw new Error('Unexpected authentication origin.');
        }
        // Office requires the first dialog page to be on the task pane origin.
        // A URL fragment is used only as a one-time start instruction; it is
        // not sent to the local server or included in application logs.
        const bootstrap = `${redirectTo}#start=${encodeURIComponent(authorizationUrl.href)}`;
        const code = await new Promise((resolve, reject) => {
          office.context.ui.displayDialogAsync(bootstrap, { height: 60, width: 40 }, (result) => {
            if (result.status !== office.AsyncResultStatus.Succeeded) {
              reject(new Error('Could not open the sign-in dialog.')); return;
            }
            const dialog = result.value;
            let settled = false;
            const finish = (error, value) => {
              if (settled) return;
              settled = true;
              clearTimeout(timer);
              try { dialog.close(); } catch (_) { /* already closed */ }
              if (error) reject(error); else resolve(value);
            };
            const timer = setTimeout(() => finish(new Error('Sign-in timed out.')), timeoutMs);
            dialog.addEventHandler(office.EventType.DialogMessageReceived, (event) => {
              // Fail closed if the host does not expose the callback origin.
              if (event.origin !== expectedOrigin) { finish(new Error('Untrusted sign-in response.')); return; }
              try {
                const message = JSON.parse(event.message);
                if (message.type !== 'caseproof-auth-code' || typeof message.code !== 'string' ||
                    !message.code || message.code.length > 4096) throw new Error();
                finish(null, message.code);
              } catch (_) { finish(new Error('Invalid sign-in response.')); }
            });
            dialog.addEventHandler(office.EventType.DialogEventReceived, () => finish(new Error('Sign-in cancelled.')));
          });
        });
        if (operation !== revision) throw new Error('Sign-in was cancelled.');
        const exchanged = await supabase.auth.exchangeCodeForSession(code);
        if (operation !== revision) {
          // A late exchange must not resurrect a signed-out session.
          await supabase.auth.signOut({ scope: 'local' });
          throw new Error('Sign-in was cancelled.');
        }
        if (exchanged.error || !exchanged.data?.session?.access_token) throw new Error('Sign-in failed.');
        session = exchanged.data.session;
      } finally { active = false; }
    }
    async function getBearer() {
      if (!session) throw new Error('Sign in first.');
      const now = Math.floor(Date.now() / 1000);
      if (typeof session.expires_at !== 'number' || session.expires_at <= now + 60) {
        const operation = revision;
        if (!refreshing) {
          refreshing = supabase.auth.refreshSession().finally(() => { refreshing = null; });
        }
        const refreshed = await refreshing;
        if (operation !== revision) throw new Error('Session has ended.');
        if (refreshed.error || !refreshed.data?.session?.access_token) {
          session = null; throw new Error('Session expired.');
        }
        session = refreshed.data.session;
      }
      return session.access_token;
    }
    async function signOut() {
      revision++;
      session = null;
      const result = await supabase.auth.signOut({ scope: 'local' });
      if (result.error) throw new Error('Local sign-out could not be confirmed.');
    }
    return Object.freeze({ login, getBearer, signOut });
  }
  return { createOfficeAuth };
});
