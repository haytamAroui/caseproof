import type { DossierView } from '../../shared/api';

/** Counts describe each snapshot independently; they do not pair findings. */
export function comparisonCounts(report: DossierView) {
  return {
    references: report.findings.length,
    identityResolved: report.findings.filter((f) => f.identity === 'resolved')
      .length,
    pageMapped: report.findings.filter((f) => f.page_mapping === 'mapped')
      .length,
    exactText: report.findings.filter((f) => f.fidelity === 'exact_match')
      .length,
    fidelityUnassessed: report.findings.filter(
      (f) => f.fidelity === 'not_assessed',
    ).length,
    ocrUnreliable: report.findings.filter(
      (f) => f.fidelity === 'ocr_unreliable',
    ).length,
    representationConflict: report.findings.filter(
      (f) => f.fidelity === 'representation_conflict',
    ).length,
    supportUnassessed: report.findings.filter(
      (f) => f.support === 'not_assessed',
    ).length,
  };
}
