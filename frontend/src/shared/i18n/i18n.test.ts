import { describe, expect, it } from 'vitest';
import { detectInitialLocale } from './index';

describe('i18n locale detection', () => {
  it('honors explicit ?lang=fr|nl|en query override', () => {
    expect(detectInitialLocale('?lang=fr', 'en-US')).toBe('fr');
    expect(detectInitialLocale('?lang=nl', 'en-US')).toBe('nl');
    expect(detectInitialLocale('?lang=en', 'fr-BE')).toBe('en');
  });

  it('falls back to browser language for Belgian FR/NL and EN otherwise', () => {
    expect(detectInitialLocale('', 'fr-BE')).toBe('fr');
    expect(detectInitialLocale('', 'nl-BE')).toBe('nl');
    expect(detectInitialLocale('', 'en-US')).toBe('en');
    expect(detectInitialLocale('?lang=de', 'en-GB')).toBe('en');
  });
});
