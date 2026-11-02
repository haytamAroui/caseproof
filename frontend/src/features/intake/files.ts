const DOCX =
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
export const slots = [
  { label: 'DOCX draft', role: 'draft', media: DOCX, accept: '.docx' },
  {
    label: 'UTF-8 inventory',
    role: 'inventory',
    media: 'text/plain',
    accept: '.txt',
  },
  {
    label: 'First PDF exhibit',
    role: 'exhibit',
    media: 'application/pdf',
    accept: '.pdf',
  },
  {
    label: 'Second PDF exhibit or scan',
    role: 'exhibit',
    media: 'application/pdf',
    accept: '.pdf',
  },
] as const;
export async function prepareFiles(files: File[], signal: AbortSignal) {
  if (
    files.length !== 4 ||
    new Set(files.map((f) => f.name)).size !== 4 ||
    files.reduce((n, f) => n + f.size, 0) > 12_000_000
  )
    throw Error('Choose four uniquely named files, up to 12 MB combined.');
  const result = [];
  for (const [index, file] of files.entries()) {
    const slot = slots[index]!;
    if (
      file.size < 1 ||
      file.size > 5_242_880 ||
      file.name.length > 128 ||
      /[\\/:]/.test(file.name) ||
      Array.from(file.name).some(
        (c) => c.charCodeAt(0) < 32 || c.charCodeAt(0) === 127,
      ) ||
      file.name.normalize('NFKC') !== file.name ||
      file.name.trim() !== file.name ||
      !file.name.toLowerCase().endsWith(slot.accept)
    )
      throw Error(
        `Replace ${slot.label}: invalid name, type or size (5 MiB maximum).`,
      );
    const bytes = new Uint8Array(await file.arrayBuffer());
    signal.throwIfAborted();
    const sha256 = Array.from(
      new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)),
      (b) => b.toString(16).padStart(2, '0'),
    ).join('');
    let binary = '';
    for (let start = 0; start < bytes.length; start += 16384)
      binary += String.fromCharCode(...bytes.subarray(start, start + 16384));
    result.push({
      role: slot.role,
      filename: file.name,
      media_type: slot.media,
      byte_length: file.size,
      sha256,
      content_base64: btoa(binary),
    });
  }
  signal.throwIfAborted();
  return result;
}
