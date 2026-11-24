import { describe, expect, it } from 'vitest';
import { detectLexicalCue } from './lexicalCue';

describe('detectLexicalCue (FE-01)', () => {
  it('flags FR signé vs envoyé pour signature', () => {
    const flag = detectLexicalCue(
      "L'avenant a été signé le 14 mars 2026",
      "Projet d'avenant envoyé pour signature le 14 mars 2026.",
    );
    expect(flag).toEqual({
      kind: 'status_mismatch',
      draftCue: 'signé',
      sourceCue: 'envoyé pour signature',
    });
  });

  it('flags NL ondertekend vs ter ondertekening', () => {
    const flag = detectLexicalCue(
      'De overeenkomst werd ondertekend op 14 maart 2026',
      'Overeenkomst verzonden ter ondertekening op 14 maart 2026.',
    );
    expect(flag).toEqual({
      kind: 'status_mismatch',
      draftCue: 'ondertekend',
      sourceCue: 'ter ondertekening',
    });
  });

  it('flags omitted opening reservation clause immediately before quote', () => {
    const flag = detectLexicalCue(
      'le locataire peut céder son droit au bail',
      "Sous réserve de l'accord écrit du bailleur, le locataire peut céder son droit au bail.",
    );
    expect(flag?.kind).toBe('omitted_reservation');
    expect(flag?.sourceCue).toContain('Sous réserve');
  });

  it('returns null when no targeted lexical trap is present', () => {
    expect(
      detectLexicalCue(
        'Le contrat a été signé le 14 mars 2026',
        'Le présent contrat a été signé le 14 mars 2026.',
      ),
    ).toBeNull();
  });
});
