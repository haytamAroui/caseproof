/** A bounded read-only view of the server's DOCX coverage ledger. */
export type CoverageRegion = {
  part: string;
  kind: string;
  status: string;
  reason: string;
};

export function coverageRegions(coverage: Record<string, unknown>): {
  regions: CoverageRegion[];
  limited: boolean;
  invalid: boolean;
  unknown: boolean;
} {
  const manifest = coverage.docx_regions;
  if (!manifest || typeof manifest !== 'object' || Array.isArray(manifest)) {
    return { regions: [], limited: false, invalid: false, unknown: true };
  }
  const data = manifest as Record<string, unknown>;
  if (!Array.isArray(data.regions)) {
    return { regions: [], limited: false, invalid: true, unknown: true };
  }
  let invalid = false;
  const regions: CoverageRegion[] = [];
  for (const value of data.regions.slice(0, 1000)) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      invalid = true;
      continue;
    }
    const row = value as Record<string, unknown>;
    if (
      !['part', 'kind', 'status', 'reason'].every(
        (key) =>
          typeof row[key] === 'string' &&
          (row[key] as string).length > 0 &&
          (row[key] as string).length <= 1024,
      )
    ) {
      invalid = true;
      continue;
    }
    regions.push({
      part: row.part as string,
      kind: row.kind as string,
      status: row.status as string,
      reason: row.reason as string,
    });
  }
  return {
    regions,
    limited: data.regions.length > 1000,
    invalid,
    unknown: data.coverage_unknown !== false,
  };
}

export type CoveragePage = {
  versionId: string;
  sha256: string;
  page: number;
  method: 'OCR_LOCAL_WORKER' | 'FAILED' | 'NOT_PROCESSED';
  reason: string | null;
};

export function coveragePages(coverage: Record<string, unknown>): {
  pages: CoveragePage[];
  limited: boolean;
  invalid: boolean;
  unknown: boolean;
} {
  const values = coverage.source_pages;
  if (!Array.isArray(values))
    return {
      pages: [],
      limited: false,
      invalid: values !== undefined,
      unknown: true,
    };
  let invalid = false;
  const pages: CoveragePage[] = [];
  for (const value of values.slice(0, 1000)) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      invalid = true;
      continue;
    }
    const row = value as Record<string, unknown>;
    if (
      typeof row.version_id !== 'string' ||
      !row.version_id ||
      row.version_id.length > 128 ||
      typeof row.original_sha256 !== 'string' ||
      !/^[0-9a-f]{64}$/.test(row.original_sha256) ||
      typeof row.pdf_page !== 'number' ||
      !Number.isInteger(row.pdf_page) ||
      row.pdf_page < 1 ||
      row.pdf_page > 100000 ||
      (row.method !== 'OCR_LOCAL_WORKER' &&
        row.method !== 'FAILED' &&
        row.method !== 'NOT_PROCESSED') ||
      (row.reason !== null &&
        (typeof row.reason !== 'string' || row.reason.length > 1024))
    ) {
      invalid = true;
      continue;
    }
    pages.push({
      versionId: row.version_id,
      sha256: row.original_sha256,
      page: row.pdf_page,
      method: row.method,
      reason: row.reason,
    });
  }
  const total = coverage.source_pages_total;
  const validTotal =
    typeof total === 'number' && Number.isSafeInteger(total) && total >= 0;
  const inconsistent = validTotal && total !== values.length;
  return {
    pages,
    limited: values.length > 1000,
    invalid: invalid || inconsistent,
    unknown: !validTotal || inconsistent,
  };
}
