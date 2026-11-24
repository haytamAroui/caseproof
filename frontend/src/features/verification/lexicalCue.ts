export type LexicalCueFlag =
  | {
      kind: 'status_mismatch';
      draftCue: string;
      sourceCue: string;
    }
  | {
      kind: 'omitted_reservation';
      draftCue: string;
      sourceCue: string;
    };

const ASSERTED_SIGNED =
  /(?<![\p{L}])(sign[ée]e?s?|conclu(?:e|s)?|ondertekend(?:e)?|signed|executed)(?![\p{L}])/iu;
const SOURCE_UNSIGNED_PRIMARY =
  /(?<![\p{L}])(envoy[ée]e?\s+pour\s+signature|pour\s+signature|non\s+sign[ée]e?|ter\s+ondertekening|niet\s+ondertekend|sent\s+for\s+signature|unsigned|draft\s+only)(?![\p{L}])/iu;
const SOURCE_UNSIGNED_ALL =
  /(?<![\p{L}])(envoy[ée]e?\s+pour\s+signature|pour\s+signature|non\s+sign[ée]e?|projet\s+d['’]avenant|ter\s+ondertekening|niet\s+ondertekend|ontwerp|sent\s+for\s+signature|unsigned|draft\s+only)(?![\p{L}])/giu;
const OPENING_RESERVATION =
  /(?<![\p{L}])(sous\s+r[ée]serve(?:\s+de)?|onder\s+voorbehoud(?:\s+van)?|behoudens|sauf\s+accord|subject\s+to)(?![\p{L}])/iu;

/**
 * Targeted deterministic FR/NL/EN lexical cues for lawyer appraisal in
 * ReportScreen. Strictly advisory (! Appréciation requise): never alters
 * finding status and never claims semantic verification.
 */
export function detectLexicalCue(
  draftQuote: string | null | undefined,
  sourceContext: string | null | undefined,
): LexicalCueFlag | null {
  const draft = typeof draftQuote === 'string' ? draftQuote.trim() : '';
  const source = typeof sourceContext === 'string' ? sourceContext.trim() : '';
  if (!draft || !source) return null;

  const draftSigned = ASSERTED_SIGNED.exec(draft);
  const sourceUnsigned =
    SOURCE_UNSIGNED_PRIMARY.exec(source) ??
    new RegExp(SOURCE_UNSIGNED_ALL.source, 'iu').exec(source);
  if (
    draftSigned &&
    sourceUnsigned &&
    !new RegExp(SOURCE_UNSIGNED_ALL.source, 'iu').test(draft) &&
    !ASSERTED_SIGNED.test(source.replace(SOURCE_UNSIGNED_ALL, ' '))
  ) {
    return {
      kind: 'status_mismatch',
      draftCue: draftSigned[0],
      sourceCue: sourceUnsigned[0],
    };
  }

  const idx = source.toLocaleLowerCase().indexOf(draft.toLocaleLowerCase());
  if (idx > 0) {
    const prefix = source.slice(Math.max(0, idx - 120), idx);
    const reservation = OPENING_RESERVATION.exec(prefix);
    if (reservation && !OPENING_RESERVATION.test(draft)) {
      return {
        kind: 'omitted_reservation',
        draftCue: draft.slice(0, 80),
        sourceCue: prefix.trim(),
      };
    }
  }
  return null;
}
