import capacity from '../../shared/api/capacity-policy.json';

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
export type IntakeFileIssue = {
  filename: string;
  role: string;
  code: string;
  message: string;
};

export class IntakeValidationError extends Error {
  constructor(
    message: string,
    public readonly fileErrors: IntakeFileIssue[],
    public readonly validFiles: string[],
  ) {
    super(message);
  }
}

export async function prepareFiles(files: File[], signal: AbortSignal) {
  if (
    files.length !== capacity.source_count ||
    new Set(files.map((f) => f.name)).size !== 4 ||
    files.reduce((n, f) => n + f.size, 0) > capacity.max_intake_bytes
  ) {
    const oversized = files
      .map((file, index) => ({ file, slot: slots[index] }))
      .filter(
        ({ file, slot }) =>
          slot != null &&
          (file.size > capacity.max_source_bytes ||
            (slot.role === 'inventory' &&
              file.size > capacity.max_inventory_bytes)),
      )
      .map(({ file, slot }) => ({
        filename: file.name,
        role: slot!.role,
        code: 'OVERSIZED_FILE',
        message: `Exceeds the per-file size limit for ${slot!.label}.`,
      }));
    const validNames = files
      .map((f) => f.name)
      .filter((name) => !oversized.some((err) => err.filename === name));
    throw new IntakeValidationError(
      `Choose ${capacity.source_count} uniquely named files, up to ${capacity.max_intake_bytes} bytes combined.`,
      oversized,
      validNames,
    );
  }
  const fileErrors: IntakeFileIssue[] = [];
  const validFiles: string[] = [];
  for (const [index, file] of files.entries()) {
    const slot = slots[index]!;
    if (file.size < 1) {
      fileErrors.push({
        filename: file.name,
        role: slot.role,
        code: 'EMPTY_FILE',
        message: `${slot.label} is empty.`,
      });
    } else if (
      file.size > capacity.max_source_bytes ||
      (slot.role === 'inventory' && file.size > capacity.max_inventory_bytes)
    ) {
      fileErrors.push({
        filename: file.name,
        role: slot.role,
        code: 'OVERSIZED_FILE',
        message: `${slot.label} exceeds the intake size limit.`,
      });
    } else if (
      file.name.length > 128 ||
      /[\\/:]/.test(file.name) ||
      Array.from(file.name).some(
        (c) => c.charCodeAt(0) < 32 || c.charCodeAt(0) === 127,
      ) ||
      file.name.normalize('NFKC') !== file.name ||
      file.name.trim() !== file.name
    ) {
      fileErrors.push({
        filename: file.name,
        role: slot.role,
        code: 'FILENAME_INVALID',
        message: `${slot.label} has an unsupported filename.`,
      });
    } else if (!file.name.toLowerCase().endsWith(slot.accept)) {
      fileErrors.push({
        filename: file.name,
        role: slot.role,
        code: 'MEDIA_TYPE_MISMATCH',
        message: `${slot.label} must end with ${slot.accept}.`,
      });
    } else {
      validFiles.push(file.name);
    }
  }
  if (fileErrors.length > 0) {
    throw new IntakeValidationError(
      'One or more selected files failed intake validation; no originals were written.',
      fileErrors,
      validFiles,
    );
  }
  const result = [];
  for (const [index, file] of files.entries()) {
    const slot = slots[index]!;
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
