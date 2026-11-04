/*
 * Local Word candidate capture. Uses Word's own paragraphs, tables, textboxes,
 * Track Changes and editing UI. Does not POST, persist, or activate a version.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.CaseProofWordCandidate = factory();
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  const MAX_BYTES = 5_242_880;

  async function capture(office, reader, cryptoApi) {
    if (!office || !reader || typeof reader.readDocx !== 'function' ||
        !cryptoApi || !cryptoApi.subtle || typeof cryptoApi.subtle.digest !== 'function') {
      throw new Error('Word capture is unavailable.');
    }
    // An actual Office FileType.Compressed read; no snapshot, reviewer status or
    // CaseProof server operation is implied by these local bytes.
    const bytes = await reader.readDocx(office, MAX_BYTES);
    if (!(bytes instanceof Uint8Array) || bytes.length < 4 || bytes.length > MAX_BYTES ||
        bytes[0] !== 80 || bytes[1] !== 75) {
      throw new Error('Word returned an unsupported or oversized candidate.');
    }
    const hashBytes = await cryptoApi.subtle.digest('SHA-256', bytes);
    const sha256 = Array.from(new Uint8Array(hashBytes), value =>
      value.toString(16).padStart(2, '0')).join('');
    if (!/^[0-9a-f]{64}$/.test(sha256)) {
      throw new Error('The edited document digest is unavailable.');
    }
    return {
      bytes,
      sha256,
      byte_length: bytes.length,
      captured_from: 'Word.FileType.Compressed',
      persisted: false,
      activated: false,
      requires_authorized_import_and_recheck: true
    };
  }

  return { capture, MAX_BYTES };
});
