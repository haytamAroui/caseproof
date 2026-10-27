/* Dialog-only callback; never persist the authorization code. */
(async () => {
  const status = document.getElementById('status');
  const fragment = new URLSearchParams(location.hash.slice(1));
  const start = fragment.get('start');
  if (start) {
    // Do not turn the callback into an arbitrary open redirect: match the
    // same-origin public configuration, not an origin supplied in the URL.
    try {
      const url = new URL(start);
      const response = await fetch('/caseproof-public-config.json', { cache: 'no-store', redirect: 'error' });
      if (!response.ok) throw new Error();
      const config = await response.json();
      const project = new URL(config.projectUrl);
      if (url.protocol !== 'https:' || !project.hostname.endsWith('.supabase.co') ||
          url.origin !== project.origin || url.pathname !== '/auth/v1/authorize') throw new Error();
      history.replaceState(null, '', location.pathname);
      location.replace(url.href);
    } catch (_) { status.textContent = 'Could not start sign-in.'; }
    return;
  }
  const params = new URLSearchParams(location.search);
  const code = params.get('code');
  history.replaceState(null, '', location.pathname);
  if (!code || code.length > 4096 || typeof Office === 'undefined') {
    status.textContent = 'Sign-in could not be completed. Return to Word and try again.';
    return;
  }
  Office.onReady(() => {
    Office.context.ui.messageParent(JSON.stringify({ type: 'caseproof-auth-code', code }),
      { targetOrigin: location.origin });
    status.textContent = 'Return to Word.';
  });
})();
