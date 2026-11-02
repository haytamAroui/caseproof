/** Display existing canonical page_spaces; never calculate an offset or mapping. */
export function pageSpaceLabel(
  value: unknown,
  space: 'printed' | 'bundle',
  mappedPdfPage: number | null,
): string {
  if (!value || typeof value !== 'object') return 'Not supplied';
  const rows = value as Record<string, unknown>;
  const pdf = rows.pdf;
  if (
    !pdf ||
    typeof pdf !== 'object' ||
    (pdf as Record<string, unknown>).state !== 'mapped' ||
    (pdf as Record<string, unknown>).value !== mappedPdfPage ||
    mappedPdfPage === null
  )
    return 'Not assessed';
  const entry = rows[space];
  if (!entry || typeof entry !== 'object') return 'Not supplied';
  const row = entry as Record<string, unknown>;
  if (
    row.state === 'mapped' &&
    typeof row.value === 'string' &&
    /^\d{1,6}$/.test(row.value)
  )
    return row.value;
  if (row.value === null && row.state === 'conflicting')
    return 'Conflicting labels';
  if (row.value === null && row.state === 'unmapped') return 'Unmapped';
  return 'Not assessed';
}
