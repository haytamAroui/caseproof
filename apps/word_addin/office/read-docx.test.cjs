const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readDocx } = require('./read-docx.js');
function fixture(chunks, options = {}) {
  let closes = 0, reads = [];
  const file = { sliceCount: chunks.length, closeAsync(cb) { closes++; cb(); },
    getSliceAsync(i, cb) { reads.push(i); cb(options.failure === i ? { status: 'failed' } :
      { status: 'ok', value: { index: options.wrongIndex === i ? i + 1 : i, data: chunks[i] } }); } };
  const office = { FileType: { Compressed: 'compressed' }, AsyncResultStatus: { Succeeded: 'ok' },
    context: { document: { getFileAsync(_type, _opts, cb) { cb({ status: 'ok', value: file }); } } } };
  return { office, get closes() { return closes; }, get reads() { return reads; } };
}
test('assembles slices in order and closes the Office file', async () => {
  const f = fixture([[1, 2], [3]]); const bytes = await readDocx(f.office);
  assert.deepEqual([...bytes], [1, 2, 3]); assert.deepEqual(f.reads, [0, 1]); assert.equal(f.closes, 1);
});
test('fails closed on read errors, invalid order and size limit', async () => {
  for (const f of [fixture([[1], [2]], { failure: 1 }), fixture([[1]], { wrongIndex: 0 })]) {
    await assert.rejects(readDocx(f.office)); assert.equal(f.closes, 1);
  }
  const f = fixture([[1, 2, 3]]); await assert.rejects(readDocx(f.office, 2)); assert.equal(f.closes, 1);
});
