const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

function setup(options = {}) {
  const elements = Object.fromEntries(['live-session', 'session-status', 'login', 'logout', 'matter-id', 'brief-id']
    .map(id => [id, { hidden: false, disabled: true, value: '', textContent: '',
      addEventListener(_type, fn) { this.click = fn; } }]));
  elements['matter-id'].value = 'case-1'; elements['brief-id'].value = 'brief-1';
  let loggedOut = 0, dispatched = 0, configCalls = 0;
  const win = { dispatchEvent() { dispatched++; }, CaseProofLiveAuth: { create(config) {
    assert.equal(config.projectUrl, 'https://test.supabase.co');
    return { matter: (caseId, briefVersionId) => ({ caseId, briefVersionId, getBearer: async () => 'private-token' }),
      login: async () => {}, signOut: async () => { loggedOut++; } };
  } } };
  const ctx = { window: win, document: { getElementById: id => elements[id] },
    location: { search: options.demo ? '?demo=1' : '' }, URLSearchParams,
    Office: { HostType: { Word: 'Word' }, onReady: fn => fn({ host: 'Word' }) },
    Event: class { constructor(type) { this.type = type; } },
    fetch: async () => { configCalls++; return { ok: !options.unconfigured,
      json: async () => ({ projectUrl: 'https://test.supabase.co', publishableKey: 'sb_publishable_test' }) }; },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'live-ui.js'), 'utf8'), ctx);
  return { elements, win, get loggedOut() { return loggedOut; }, get dispatched() { return dispatched; },
    get configCalls() { return configCalls; } };
}

test('sign-in binds matter only after login and sign-out clears it', async () => {
  const r = setup();
  await r.elements.login.click();
  assert.equal(r.win.caseproofSession.caseId, 'case-1');
  assert.equal(r.win.caseproofSession.mode, 'dev-live');
  assert.equal(r.elements['matter-id'].disabled, true);
  assert.equal(r.elements.login.disabled, true);
  assert.doesNotMatch(r.elements['session-status'].textContent, /private-token/);
  await r.elements.logout.click();
  assert.equal(r.win.caseproofSession, null);
  assert.equal(r.elements['matter-id'].disabled, false);
  assert.equal(r.dispatched, 1); assert.equal(r.loggedOut, 1);
});

test('unconfigured server fails closed and demo never opens login', async () => {
  const a = setup({ unconfigured: true });
  await a.elements.login.click();
  assert.equal(a.win.caseproofSession, null);
  assert.match(a.elements['session-status'].textContent, /not configured/);
  const b = setup({ demo: true });
  assert.equal(b.elements['live-session'].hidden, true);
  assert.equal(b.configCalls, 0);
});
