/** Memory-only, read-only return navigation. Never retain arbitrary URL values. */
export function recoveryDestination(
  pathname: string,
  search: string,
): string | null {
  const uuid =
    '[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}';
  const matter = new RegExp(`^/matters/${uuid}$`, 'i');
  const report = new RegExp(`^/matters/${uuid}/briefs/${uuid}$`, 'i');
  if (matter.test(pathname)) return pathname;
  if (!report.test(pathname)) return null;
  const params = new URLSearchParams(search);
  const snapshot = params.get('snapshot');
  if (!snapshot || !/^[0-9a-f]{64}$/.test(snapshot)) return null;
  // Selection, arbitrary query parameters and all form values are discarded.
  return `${pathname}?snapshot=${snapshot}`;
}
