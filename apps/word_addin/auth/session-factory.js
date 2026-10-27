/* Construct a PKCE Supabase client using ephemeral, process-local storage. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(require('./office-auth.js'));
  else root.CaseProofSessionFactory = factory(root.CaseProofOfficeAuth);
})(typeof globalThis === 'object' ? globalThis : this, function (officeAuth) {
  'use strict';
  function createMemoryStorage() {
    const values = new Map();
    return { getItem: key => values.get(key) ?? null,
      setItem: (key, value) => { values.set(key, value); },
      removeItem: key => { values.delete(key); } };
  }
  function createSession({ createClient, projectUrl, publishableKey, office, origin }) {
    const url = new URL(projectUrl);
    if (url.protocol !== 'https:' || !url.hostname.endsWith('.supabase.co') ||
        url.username || url.password || url.pathname !== '/' || url.search || url.hash ||
        typeof publishableKey !== 'string' || !publishableKey.startsWith('sb_publishable_')) {
      throw new Error('A Supabase project URL and publishable key are required.');
    }
    const supabase = createClient(url.origin, publishableKey, { auth: {
      flowType: 'pkce', storage: createMemoryStorage(), persistSession: true,
      autoRefreshToken: false, detectSessionInUrl: false,
    } });
    const auth = officeAuth.createOfficeAuth({ supabase, office, origin, authOrigin: url.origin });
    function matter(caseId, briefVersionId) {
      if (typeof caseId !== 'string' || !caseId || caseId.length > 128 ||
          typeof briefVersionId !== 'string' || !briefVersionId || briefVersionId.length > 128) {
        throw new Error('A matter and brief are required.');
      }
      // IDs are selectors only. The backend derives identity and enforces grants.
      return Object.freeze({ caseId, briefVersionId, getBearer: auth.getBearer });
    }
    return Object.freeze({ login: auth.login, signOut: auth.signOut, matter });
  }
  return { createMemoryStorage, createSession };
});
