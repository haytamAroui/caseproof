/*
 * Office file-slice workflow adapted from Vaquill AI for Word,
 * src/office/file.ts (Apache-2.0), commit 0740ec39ffd1e1e1ef54088a11d157cf35aa541b.
 * Copyright 2026 Vaquill AI; modifications by CaseProof contributors.
 * See THIRD_PARTY_NOTICES.md and third_party/Vaquill-LICENSE.txt.
 * No content is logged, persisted, or uploaded by this helper.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.CaseProofWordFile = factory();
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  function readDocx(office, maxBytes = 25 * 1024 * 1024) {
    if (!Number.isSafeInteger(maxBytes) || maxBytes < 1 || maxBytes > 25 * 1024 * 1024) {
      return Promise.reject(new Error('Invalid document size limit.'));
    }
    const sliceSize = 65536;
    return new Promise((resolve, reject) => {
      office.context.document.getFileAsync(office.FileType.Compressed, { sliceSize }, result => {
        if (result.status !== office.AsyncResultStatus.Succeeded || !result.value) {
          reject(new Error('Could not read the Word document.')); return;
        }
        const file = result.value;
        let finished = false, total = 0;
        const chunks = [];
        const close = () => { try { file.closeAsync(() => {}); } catch (_) { /* best effort */ } };
        const fail = () => {
          if (finished) return;
          finished = true; close(); reject(new Error('Could not read a bounded Word document.'));
        };
        if (!Number.isSafeInteger(file.sliceCount) || file.sliceCount < 1 ||
            file.sliceCount > Math.ceil(maxBytes / sliceSize) + 1) { fail(); return; }
        const next = index => {
          try {
            file.getSliceAsync(index, part => {
              if (finished) return;
              if (part.status !== office.AsyncResultStatus.Succeeded || !part.value ||
                  part.value.index !== index || !Array.isArray(part.value.data) ||
                  part.value.data.length > sliceSize ||
                  part.value.data.some(x => !Number.isInteger(x) || x < 0 || x > 255)) { fail(); return; }
              const bytes = Uint8Array.from(part.value.data);
              total += bytes.length;
              if (total > maxBytes) { fail(); return; }
              chunks.push(bytes);
              if (index + 1 < file.sliceCount) { next(index + 1); return; }
              const output = new Uint8Array(total);
              let offset = 0;
              for (const chunk of chunks) { output.set(chunk, offset); offset += chunk.length; }
              finished = true; close(); resolve(output);
            });
          } catch (_) { fail(); }
        };
        next(0);
      });
    });
  }
  return { readDocx };
});
