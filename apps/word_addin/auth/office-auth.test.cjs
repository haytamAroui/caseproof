const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createOfficeAuth } = require('./office-auth.js');

function rig(opts = {}) {
  let handler, canceled, dialogUrl, exchangeCount = 0, refreshCount = 0;
  const now = Math.floor(Date.now() / 1000);
  const sdk = { auth: {
    signInWithOAuth: async () => ({ data: { url: opts.url || 'https://project.supabase.co/auth/v1/authorize?provider=google' } }),
    exchangeCodeForSession: async () => { exchangeCount++; return { data: { session: { access_token: 'signed-token', expires_at: now + 3600 } } }; },
    refreshSession: async () => { refreshCount++; return { data: { session: { access_token: 'refreshed', expires_at: now + 3600 } } }; },
    signOut: async () => ({ error: null }),
  } };
  const office = {
    AsyncResultStatus: { Succeeded: 'ok' },
    EventType: { DialogMessageReceived: 'message', DialogEventReceived: 'closed' },
    context: { ui: { displayDialogAsync(url, _options, cb) {
      dialogUrl = url;
      cb({ status: 'ok', value: { close() {}, addEventHandler(name, fn) {
        if (name === 'message') handler = fn; else canceled = fn;
      } } });
    } } },
  };
  const auth = createOfficeAuth({ supabase: sdk, office, origin: 'https://word.example',
    authOrigin: 'https://project.supabase.co', timeoutMs: 500 });
  return { auth, sdk, get handler() { return handler; }, get canceled() { return canceled; },
    get dialogUrl() { return dialogUrl; }, get exchangeCount() { return exchangeCount; },
    get refreshCount() { return refreshCount; } };
}
async function opened(r) {
  const pending = r.auth.login();
  await Promise.resolve(); await Promise.resolve();
  return pending;
}
// Do not await opened: it returns the unresolved login promise.
function start(r) { const pending = r.auth.login(); return pending; }
async function ready() { await Promise.resolve(); await Promise.resolve(); }

test('same-origin bootstrap, origin validation and in-memory session', async () => {
  const r = rig(); const pending = start(r); await ready();
  assert.ok(r.dialogUrl.startsWith('https://word.example/auth-callback.html#start='));
  r.handler({ origin: 'https://word.example', message: JSON.stringify({ type: 'caseproof-auth-code', code: 'fixture' }) });
  await pending;
  assert.equal(await r.auth.getBearer(), 'signed-token');
  assert.equal(r.exchangeCount, 1);
  await r.auth.signOut();
  await assert.rejects(r.auth.getBearer(), /Sign in/);
});

test('rejects untrusted callback before exchanging code', async () => {
  const r = rig(); const pending = start(r); await ready();
  r.handler({ origin: 'https://attacker.example', message: JSON.stringify({ type: 'caseproof-auth-code', code: 'fixture' }) });
  await assert.rejects(pending, /Untrusted/);
  assert.equal(r.exchangeCount, 0);
});

test('rejects unexpected provider origin', async () => {
  const r = rig({ url: 'https://attacker.example/authorize' });
  await assert.rejects(r.auth.login(), /Unexpected authentication origin/);
});

test('sign out while dialog open cannot restore session', async () => {
  const r = rig(); const pending = start(r); await ready();
  await r.auth.signOut();
  r.handler({ origin: 'https://word.example', message: JSON.stringify({ type: 'caseproof-auth-code', code: 'fixture' }) });
  await assert.rejects(pending, /cancelled/);
  assert.equal(r.exchangeCount, 0);
  await assert.rejects(r.auth.getBearer(), /Sign in/);
});

test('dialog cancellation and parallel sign-in fail closed', async () => {
  const r = rig(); const pending = start(r); await ready();
  await assert.rejects(r.auth.login(), /already in progress/);
  r.canceled();
  await assert.rejects(pending, /cancelled/);
});

test('near-expired session is refreshed once for concurrent callers', async () => {
  const r = rig();
  r.sdk.auth.exchangeCodeForSession = async () => ({ data: { session: {
    access_token: 'old', expires_at: Math.floor(Date.now() / 1000) + 1,
  } } });
  const pending = start(r); await ready();
  r.handler({ origin: 'https://word.example', message: JSON.stringify({ type: 'caseproof-auth-code', code: 'fixture' }) });
  await pending;
  assert.deepEqual(await Promise.all([r.auth.getBearer(), r.auth.getBearer()]), ['refreshed', 'refreshed']);
  assert.equal(r.refreshCount, 1);
});

test('late refresh does not restore a signed-out session', async () => {
  const r = rig(); let release;
  r.sdk.auth.exchangeCodeForSession = async () => ({ data: { session: {
    access_token: 'old', expires_at: Math.floor(Date.now() / 1000) + 1,
  } } });
  r.sdk.auth.refreshSession = () => new Promise(resolve => { release = resolve; });
  const pending = start(r); await ready();
  r.handler({ origin: 'https://word.example', message: JSON.stringify({ type: 'caseproof-auth-code', code: 'fixture' }) });
  await pending;
  const refreshing = r.auth.getBearer();
  await r.auth.signOut();
  release({ data: { session: { access_token: 'late', expires_at: Math.floor(Date.now() / 1000) + 3600 } } });
  await assert.rejects(refreshing, /ended/);
  await assert.rejects(r.auth.getBearer(), /Sign in/);
});
