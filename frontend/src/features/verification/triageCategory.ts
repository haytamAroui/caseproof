import type { DossierView, FindingView } from '../../shared/api';
import type { ResultCategory } from '../../shared/i18n';
import { coveragePages, coverageRegions } from './coverageRegions';

/**
 * Pure read-only UI triage projection (ADR 0038 / UI-01, UI-02).
 *
 * Groups backend four-dimension findings into the four lawyer-facing triage
 * categories without mutating, recomputing, or upgrading any backend state.
 * A finding reaches `correspondance` only when all four backend dimensions are
 * explicitly resolved/mapped/exact_match/supported.
 */
export function triageCategoryOf(finding: FindingView): ResultCategory {
  if (
    finding.identity === 'not_in_inventory' ||
    finding.page_mapping === 'conflicting' ||
    finding.fidelity === 'quote_not_found' ||
    finding.fidelity === 'representation_conflict' ||
    finding.support === 'contradicted'
  ) {
    return 'ecart';
  }
  if (
    finding.identity === 'source_missing' ||
    finding.identity === 'ambiguous' ||
    finding.identity === 'not_assessed' ||
    finding.page_mapping === 'unmapped' ||
    finding.fidelity === 'ocr_unreliable' ||
    finding.fidelity === 'not_assessed'
  ) {
    return 'impossible';
  }
  if (
    finding.fidelity === 'translation_review_required' ||
    finding.fidelity === 'multiple_matches' ||
    finding.support === 'not_assessed' ||
    finding.support === 'qualified'
  ) {
    return 'appreciation';
  }
  return 'correspondance';
}

export const TRIAGE_PRIORITY: Record<ResultCategory, number> = {
  ecart: 0,
  impossible: 1,
  appreciation: 2,
  correspondance: 3,
};

export const TRIAGE_TONE: Record<ResultCategory, string> = {
  ecart: 'error',
  impossible: 'impossible',
  appreciation: 'warning',
  correspondance: 'success',
};

export const TRIAGE_ICON: Record<ResultCategory, string> = {
  ecart: '✕',
  impossible: '⊘',
  appreciation: '!',
  correspondance: '✓',
};

export type TriageCounts = Record<ResultCategory, number>;

export function countByTriageCategory(
  findings: readonly FindingView[],
): TriageCounts {
  const counts: TriageCounts = {
    ecart: 0,
    impossible: 0,
    appreciation: 0,
    correspondance: 0,
  };
  for (const finding of findings) {
    counts[triageCategoryOf(finding)] += 1;
  }
  return counts;
}

export type ReportFailureBannerKind =
  | 'inventory_unconfirmed'
  | 'pagination_unmapped'
  | 'ocr_unreliable'
  | 'partial_coverage';

export type ReportFailureBanner = {
  kind: ReportFailureBannerKind;
  count: number;
  tone: 'error' | 'impossible' | 'warning';
  filterCategory?: ResultCategory;
};

/**
 * Surfaces first-class fail-closed operational warnings directly from the
 * canonical report payload so partial/unmapped/unreadable inputs never look
 * silently clean (ADR 0038 Section 4.1).
 */
export function collectReportFailureBanners(
  report: Pick<DossierView, 'findings' | 'coverage'>,
): ReportFailureBanner[] {
  const banners: ReportFailureBanner[] = [];

  const unconfirmedInventory = report.findings.filter(
    (f) => f.identity === 'not_assessed',
  ).length;
  if (unconfirmedInventory > 0) {
    banners.push({
      kind: 'inventory_unconfirmed',
      count: unconfirmedInventory,
      tone: 'impossible',
      filterCategory: 'impossible',
    });
  }

  const unmappedPagination = report.findings.filter(
    (f) => f.page_mapping === 'unmapped' || f.page_mapping === 'conflicting',
  ).length;
  if (unmappedPagination > 0) {
    banners.push({
      kind: 'pagination_unmapped',
      count: unmappedPagination,
      tone: report.findings.some((f) => f.page_mapping === 'conflicting')
        ? 'error'
        : 'warning',
      filterCategory: report.findings.some(
        (f) => f.page_mapping === 'conflicting',
      )
        ? 'ecart'
        : 'impossible',
    });
  }

  const ocrIssues = report.findings.filter(
    (f) =>
      f.fidelity === 'ocr_unreliable' ||
      f.fidelity === 'representation_conflict',
  ).length;
  const failedPages = coveragePages(report.coverage).pages.filter(
    (p) => p.method === 'FAILED' || p.method === 'NOT_PROCESSED',
  ).length;
  if (ocrIssues > 0 || failedPages > 0) {
    banners.push({
      kind: 'ocr_unreliable',
      count: Math.max(ocrIssues, failedPages),
      tone: 'impossible',
      filterCategory: 'impossible',
    });
  }

  const regionInfo = coverageRegions(report.coverage);
  const unprocessedRegions = regionInfo.regions.filter(
    (r) => r.status !== 'scanned' && r.status !== 'processed',
  ).length;
  if (unprocessedRegions > 0 || regionInfo.invalid) {
    banners.push({
      kind: 'partial_coverage',
      count: Math.max(unprocessedRegions, regionInfo.invalid ? 1 : 0),
      tone: 'warning',
    });
  }

  return banners;
}
