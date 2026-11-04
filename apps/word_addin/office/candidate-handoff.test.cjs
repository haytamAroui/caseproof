const test = require('node:test');
const assert = require('node:assert/strict');
const { webcrypto } = require('node:crypto');
const { capture, MAX_BYTES } = require('./candidate-handoff.js');

test('Word candidate bytes are digested and not persisted or uploaded', async () => {
  const document = Uint8Array.from([80, 75, 3, 4, 1, 2, 3]);
  let calls = 0;
  const reader = {
    async readDocx(office, sizeLimit) {
      calls++;
      assert.equal(office.kind, 'word');
      assert.equal(sizeLimit, MAX_BYTES);
      return document;
    },
  };
  const receipt = await capture({ kind: 'word' }, reader, webcrypto);
  assert.equal(calls, 1);
  assert.equal(receipt.bytes, document);
  assert.equal(receipt.byte_length, document.length);
  assert.match(receipt.sha256, /^[0-9a-f]{64}$/);
  assert.equal(receipt.persisted, false);
  assert.equal(receipt.activated, false);
  assert.equal(receipt.requires_authorized_import_and_recheck, true);
});

test('empty, wrong format, oversized and missing crypto fail closed', async () => {
  await assert.rejects(() => capture({}, { readDocx: async () => new Uint8Array([0, 1, 2, 3]) }, webcrypto), /unsupported/);
  await assert.rejects(() => capture({}, { readDocx: async () => new Uint8Array([80, 75, 0]) }, webcrypto), /unsupported/);
  await assert.rejects(() => capture({}, { readDocx: async () => new Uint8Array(MAX_BYTES + 1) }, webcrypto), /unsupported/);
  await assert.rejects(() => capture({}, null, webcrypto), /unavailable/);
  await assert.rejects(() => capture({}, { readDocx: async () => Uint8Array.from([80, 75, 3, 4]) }, null), /unavailable/);
});

test('reader failure cannot create a false successful receipt', async () => {
  await assert.rejects(() => capture({}, { readDocx: async () => { throw new Error('Word closed'); } }, webcrypto), /Word closed/);
});
