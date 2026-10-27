const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
async function setup({ hash = '', search = '' } = {}) {
  const status = { textContent: '' }; let replaced = null, posted = null, cleaned = 0;
  const location = { hash, search, pathname: '/auth-callback.html', origin: 'https://word.example',
    replace(url) { replaced = url; } };
  const context = { URL, URLSearchParams, location, document: { getElementById: () => status },
    history: { replaceState() { cleaned++; } },
    fetch: async () => ({ ok: true, json: async () => ({ projectUrl: 'https://project.supabase.co' }) }),
    Office: { onReady: callback => callback(), context: { ui: { messageParent(message, options) {
      posted = { message, options };
    } } } } };
  await vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'office-callback.js'), 'utf8'), context);
  return { status, get replaced() { return replaced; }, get posted() { return posted; }, get cleaned() { return cleaned; } };
}
test('bootstrap accepts only the configured Supabase origin', async () => {
  const good = await setup({ hash: '#start=' + encodeURIComponent('https://project.supabase.co/auth/v1/authorize?provider=google') });
  assert.match(good.replaced, /^https:\/\/project\.supabase\.co/); assert.equal(good.cleaned, 1);
  const bad = await setup({ hash: '#start=' + encodeURIComponent('https://attacker.example/steal') });
  assert.equal(bad.replaced, null); assert.match(bad.status.textContent, /Could not/);
});
test('callback removes URL query and sends code only to taskpane origin', async () => {
  const r = await setup({ search: '?code=synthetic-code' });
  assert.equal(r.cleaned, 1); assert.equal(r.posted.options.targetOrigin, 'https://word.example');
  assert.equal(JSON.parse(r.posted.message).code, 'synthetic-code');
  const bad = await setup({ search: '?error=denied' });
  assert.equal(bad.posted, null); assert.equal(bad.cleaned, 1);
});
