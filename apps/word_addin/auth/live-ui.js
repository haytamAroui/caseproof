/* Development integration. The backend must still authenticate and authorize every request. */
(() => {
  const section = document.getElementById('live-session');
  if (new URLSearchParams(location.search).get('demo') === '1') { section.hidden = true; return; }
  const message = document.getElementById('session-status');
  const login = document.getElementById('login');
  const logout = document.getElementById('logout');
  const caseInput = document.getElementById('matter-id');
  const briefInput = document.getElementById('brief-id');
  let controller = null;
  let pending = false;
  if (typeof Office === 'undefined') { message.textContent = 'Open this add-in in Word.'; return; }
  Office.onReady(info => {
    if (info.host === Office.HostType.Word) login.disabled = false;
  });
  login.addEventListener('click', async () => {
    if (pending) return;
    pending = true; login.disabled = true;
    try {
      if (!window.CaseProofLiveAuth) throw new Error('The sign-in bundle is not available.');
      // Same-origin public configuration contains only the publishable key.
      const response = await fetch('/caseproof-public-config.json', { cache: 'no-store', redirect: 'error' });
      if (!response.ok) throw new Error('Sign-in is not configured on this server.');
      const config = await response.json();
      controller = window.CaseProofLiveAuth.create({ projectUrl: config.projectUrl, publishableKey: config.publishableKey });
      const matter = controller.matter(caseInput.value.trim(), briefInput.value.trim());
      await controller.login();
      window.caseproofSession = Object.freeze({ ...matter, mode: 'dev-live' });
      logout.disabled = false;
      caseInput.disabled = true; briefInput.disabled = true;
      message.textContent = 'Signed in. Search is available for authorized matters.';
    } catch (error) {
      window.caseproofSession = null;
      controller = null;
      message.textContent = error instanceof Error ? error.message : 'Sign-in failed.';
    } finally { pending = false; login.disabled = Boolean(window.caseproofSession); }
  });
  logout.addEventListener('click', async () => {
    if (pending) return;
    pending = true; login.disabled = true; logout.disabled = true;
    window.caseproofSession = null;
    window.dispatchEvent(new Event('caseproof:session-ended'));
    try {
      if (controller) await controller.signOut();
      message.textContent = 'Signed out of this pane.';
    } catch (_) { message.textContent = 'The local session ended, but sign-out could not be confirmed.'; }
    finally { controller = null; pending = false; caseInput.disabled = false; briefInput.disabled = false; login.disabled = false; }
  });
})();
