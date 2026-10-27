const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const { webcrypto, createHash } = require('node:crypto');

function element() {
  return { disabled: false, hidden: false, textContent: '', value: '', children: [],
    addEventListener(_event, fn) { this.click = fn; },
    append(...nodes) { this.children.push(...nodes); },
    appendChild(node) { this.children.push(node); },
    replaceChildren() { this.children = []; },
  };
}
function setup(options = {}) {
  const elements = Object.fromEntries(['inspect', 'query', 'status', 'result', 'selection', 'coverage', 'hits']
    .map(id => [id, element()]));
  elements.query.value = 'betaling';
  const state = { selected: 'The payment is due.', body: 'The payment is due.', writes: [], calls: 0, downloads: 0, syncs: 0 };
  const original = Buffer.from('fixture-original');
  const originalHash = createHash('sha256').update(original).digest('hex');
  const hit = { source_id: 's1', source_version_id: 'v1', representation_id: 'r1',
    source_sha256: originalHash, locator: 'page:0', page: 1, start: 0, end: 25,
    text: '<script>evidence</script>', citation: { exhibit_id: 'e1', label: 'Stuk 1', pdf_page: 1 } };
  const response = { schema: 'caseproof-evidence-search-v1', case_id: 'case', brief_version_id: 'draft',
    exhibit_revision: 1, coverage: 'complete', omitted_sources: 0, hits: [hit] };
  let bearerCalls = 0;
  const provider = { mode: options.mode || 'synthetic', caseId: 'case', briefVersionId: 'draft', getBearer: async () => {
    bearerCalls++;
    if (options.logoutDuringDownloadToken && bearerCalls === 2) state.endSession();
    return 'signed-token';
  } };
  const context = {
    document: { getElementById: id => elements[id], createElement: tag => {
      const node = element(); if (tag === 'a') node.click = () => { state.downloads++; }; return node;
    } },
    crypto: webcrypto, Blob, Uint8Array, setTimeout: fn => fn(),
    URL: { createObjectURL: () => 'blob:fixture', revokeObjectURL() {} },
    window: { caseproofSession: options.noSession ? null : provider,
      addEventListener(name, fn) { if (name === 'caseproof:session-ended') state.endSession = fn; } },
    Office: { HostType: { Word: 'Word' }, context: { requirements: { isSetSupported: () => true } },
      onReady(fn) { fn({ host: 'Word' }); } },
    Word: { run: fn => {
      let writesBefore = state.writes.length;
      const range = { get text() { return state.selected; }, load() {},
        insertText(text) { state.writes.push(text); } };
      return fn({ document: { getSelection: () => range,
        body: { get text() { return state.body; }, load() {} } },
        sync: async () => {
          state.syncs++;
          if (options.logoutDuringInsert && state.syncs === 2) state.endSession();
          if (options.unknown && state.writes.length > writesBefore) throw new Error('lost');
        } });
    } },
    fetch: async (url, request) => {
      state.calls++;
      assert.ok(url.startsWith('/v2/matters/'));
      assert.equal(request.redirect, 'error');
      if (!request.method) return { ok: true, headers: { get: name => ({
        'X-CaseProof-Original-SHA256': originalHash, 'Content-Length': String(original.length),
        'X-CaseProof-Original-Media-Type': 'text/plain',
      })[name] }, arrayBuffer: async () => {
        if (options.tampered) return Uint8Array.from(Buffer.alloc(original.length, 1)).buffer;
        return Uint8Array.from(original).buffer;
      } };
      return { ok: true, json: async () => options.changed && state.calls > 1 ?
        { ...response, exhibit_revision: 2 } : response };
    },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'taskpane.js'), 'utf8'), context);
  return { elements, state };
}
async function start(options) {
  const rig = setup(options);
  await rig.elements.inspect.click();
  return rig;
}
function action(rig) { return rig.elements.hits.children[0].children[2]; }

test('search and insert revalidate source and document and render plain text', async () => {
  const rig = await start();
  assert.equal(rig.elements.hits.children[0].children[1].textContent, '<script>evidence</script>');
  await action(rig).click();
  assert.deepEqual(rig.state.writes, [' (Stuk 1, p. 1)']);
  assert.equal(rig.state.calls, 2);
  assert.match(rig.elements.status.textContent, /inserted/);
});
test('changed exhibit revision or document prevents insertion', async () => {
  const changed = await start({ changed: true });
  await action(changed).click();
  assert.equal(changed.state.writes.length, 0);
  const stale = await start();
  stale.state.body += ' changed';
  await action(stale).click();
  assert.equal(stale.state.writes.length, 0);
});
test('sign out during the final Word read prevents insertion', async () => {
  const rig = await start({ logoutDuringInsert: true });
  await action(rig).click();
  assert.equal(rig.state.writes.length, 0);
  assert.match(rig.elements.status.textContent, /session changed/i);
});
test('unknown edit outcome prevents duplicate retry', async () => {
  const rig = await start({ unknown: true });
  const button = action(rig);
  await button.click();
  await button.click();
  assert.equal(rig.state.writes.length, 1);
  assert.match(rig.elements.status.textContent, /outcome is unknown/);
});
test('requires a session and a unique selection', async () => {
  const noSession = await start({ noSession: true });
  assert.match(noSession.elements.status.textContent, /No authenticated/);
  const duplicate = setup();
  duplicate.state.body = 'The payment is due. The payment is due.';
  await duplicate.elements.inspect.click();
  assert.match(duplicate.elements.status.textContent, /unique passage/);
  assert.equal(duplicate.state.calls, 0);
});

test('non-synthetic session cannot insert', async () => {
  const rig = await start({ mode: 'live' });
  assert.equal(action(rig).disabled, true);
  await action(rig).click();
  assert.equal(rig.state.writes.length, 0);
});

test('original download verifies source hash and rejects tampered content', async () => {
  const good = await start();
  await good.elements.hits.children[0].children[3].click();
  assert.equal(good.state.downloads, 1);
  assert.match(good.elements.status.textContent, /downloaded/);
  const bad = await start({ tampered: true });
  await bad.elements.hits.children[0].children[3].click();
  assert.equal(bad.state.downloads, 0);
  assert.match(bad.elements.status.textContent, /integrity/);
});
test('sign out while obtaining download token sends no original request', async () => {
  const rig = await start({ logoutDuringDownloadToken: true });
  await rig.elements.hits.children[0].children[3].click();
  assert.equal(rig.state.calls, 1);
  assert.equal(rig.state.downloads, 0);
  assert.match(rig.elements.status.textContent, /session changed/i);
});
