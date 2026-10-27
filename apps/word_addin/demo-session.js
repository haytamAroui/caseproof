/* Public synthetic demo only; these values are never real credentials. */
if ((location.hostname === 'localhost' || location.hostname === '127.0.0.1') &&
    location.port === '3000' && new URLSearchParams(location.search).get('demo') === '1') {
  window.caseproofSession = Object.freeze({
    mode: 'synthetic', caseId: 'synthetic-matter', briefVersionId: 'synthetic-brief',
    getBearer: async () => 'synthetic-demo-only',
  });
}
