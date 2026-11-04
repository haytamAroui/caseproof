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

/** Display supplied reasons without treating them as new verification decisions. */
export function findingReasons(
  finding: DossierView['findings'][number],
): Array<[string, string]> {
  const result: Array<[string, string]> = [];
  const add = (label: string, value: unknown) => {
    if (typeof value === 'string' && value.length > 0 && value.length <= 1000)
      result.push([label, value]);
  };
  const reason = (value: unknown): unknown =>
    value && typeof value === 'object' && !Array.isArray(value)
      ? (value as Record<string, unknown>).reason
      : undefined;
  add('Identity', finding.identity_reason);
  add('Page mapping', finding.page_mapping_reason);
  add('Literal assessment', reason(finding.literal_assessment));
  add('Visual assessment', reason(finding.visual_assessment));
  if (finding.translation_review_required === true)
    result.push(['Translation', 'Human review required']);
  return result;
}
