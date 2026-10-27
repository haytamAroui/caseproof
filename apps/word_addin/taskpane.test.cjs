const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

function setup(text) {
  const elements = Object.fromEntries(['inspect', 'status', 'result', 'selection'].map(id => [id, {
    disabled: false, hidden: false, textContent: '',
    addEventListener(_name, handler) { this.click = handler; },
  }]));
  const context = {
    document: { getElementById: id => elements[id] },
    Office: { HostType: { Word: 'Word' }, context: { requirements: { isSetSupported: () => true } },
      onReady(fn) { fn({ host: 'Word' }); } },
    Word: { run: fn => fn({ document: { getSelection: () => ({ text, load() {} }) }, sync: async () => {} }) },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'taskpane.js'), 'utf8'), context);
  return elements;
}

test('renders selection as text and labels example as unverified', async () => {
  const el = setup('<img src=x onerror=alert(1)>');
  await el.inspect.click();
  assert.equal(el.selection.textContent, '<img src=x onerror=alert(1)>');
  assert.equal(el.result.hidden, false);
  assert.match(el.status.textContent, /not a verified match/);
});

test('rejects empty and oversized selections', async () => {
  for (const text of ['  ', 'x'.repeat(1001)]) {
    const el = setup(text);
    await el.inspect.click();
    assert.equal(el.result.hidden, true);
    assert.match(el.status.textContent, /at most 1,000/);
  }
});
