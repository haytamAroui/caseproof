const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createSession, createMemoryStorage } = require('./session-factory.js');

test('memory storage is per session and supports PKCE verifier operations', () => {
  const a = createMemoryStorage(); const b = createMemoryStorage();
  a.setItem('pkce-verifier', 'fixture');
  assert.equal(a.getItem('pkce-verifier'), 'fixture');
  assert.equal(b.getItem('pkce-verifier'), null);
  a.removeItem('pkce-verifier');
  assert.equal(a.getItem('pkce-verifier'), null);
});

test('uses PKCE and isolated memory; never accepts secret keys', () => {
  let options;
  const createClient = (_url, _key, opts) => { options = opts; return { auth: {} }; };
  const base = { createClient, projectUrl: 'https://example.supabase.co', office: {}, origin: 'https://word.example' };
  assert.throws(() => createSession({ ...base, publishableKey: 'sb_secret_bad' }), /publishable/);
  assert.throws(() => createSession({ ...base, projectUrl: 'https://attacker.example', publishableKey: 'sb_publishable_test' }), /publishable/);
  const session = createSession({ ...base, publishableKey: 'sb_publishable_test' });
  assert.equal(options.auth.flowType, 'pkce');
  assert.equal(options.auth.autoRefreshToken, false);
  assert.equal(options.auth.storage.getItem('refresh'), null);
  assert.throws(() => session.matter('', 'draft'), /matter/);
  assert.equal(session.matter('case-1', 'draft-1').caseId, 'case-1');
});
